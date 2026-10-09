# -*- coding: utf-8 -*-
"""
Windows 运行时自我注册（普通用户权限、幂等、绝不阻断面板启动）。

面板后端每次启动时调用一次 self_register_if_windows()，完成两件事：
  1) 注册自定义协议 quant://（写入 HKCU 注册表，普通权限即可，无需管理员），
     使 index.html 页面里的“一键启动数据后台”按钮能经 quant://start-backend
     调起 scripts\\panel_guard.vbs，从而在页面内启动后台。
  2) 创建当前用户的计划任务 QuantPanelGuard（登录后 30 秒首次运行、之后每
     5 分钟确保 8000 端口在听，后台崩了自动拉起）。普通权限创建失败时静默
     跳过（仍有开机交易任务兜底起面板）。

任何异常都只写入 logs/self_register.log，不影响面板本身启动。
其它平台调用为 no-op。
模拟盘、本机真实撮合，绝不连接任何券商真实账号/资金账号。
"""

import sys
import subprocess
import tempfile
from pathlib import Path


def _run(args, timeout=25):
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(args, capture_output=True, text=True,
                          timeout=timeout, creationflags=creationflags)


def _register_protocol(root):
    vbs = root / "scripts" / "panel_guard.vbs"
    proto = r"HKCU\Software\Classes\quant"
    command_val = f'wscript.exe "{vbs}" "%1"'
    _run(["reg", "add", proto, "/ve", "/d", "URL:Quant Panel Launch", "/f"])
    _run(["reg", "add", proto, "/v", "URL Protocol", "/d", "", "/f"])
    _run(["reg", "add", proto + r"\shell\open\command", "/ve",
          "/d", command_val, "/f"])
    return True


def _register_guard_task(root):
    vbs = root / "scripts" / "panel_guard.vbs"
    # 当前用户、LeastPrivilege：普通权限即可创建自己的登录任务。
    xml = (
        '<?xml version="1.0" encoding="UTF-16"?>\r\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\r\n'
        '  <RegistrationInfo><Description>Quant panel guard: keep Flask backend on port 8000 alive (simulation only, no broker).</Description></RegistrationInfo>\r\n'
        '  <Triggers>\r\n'
        '    <LogonTrigger>\r\n'
        '      <Enabled>true</Enabled>\r\n'
        '      <Delay>PT30S</Delay>\r\n'
        '      <Repetition><Interval>PT5M</Interval><Duration>P3650D</Duration><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>\r\n'
        '    </LogonTrigger>\r\n'
        '  </Triggers>\r\n'
        '  <Principals>\r\n'
        '    <Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal>\r\n'
        '  </Principals>\r\n'
        '  <Settings>\r\n'
        '    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\r\n'
        '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\r\n'
        '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\r\n'
        '    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>\r\n'
        '    <Enabled>true</Enabled>\r\n'
        '  </Settings>\r\n'
        '  <Actions Context="Author">\r\n'
        '    <Exec>\r\n'
        '      <Command>wscript.exe</Command>\r\n'
        f'      <Arguments>"{vbs}"</Arguments>\r\n'
        f'      <WorkingDirectory>{root}</WorkingDirectory>\r\n'
        '    </Exec>\r\n'
        '  </Actions>\r\n'
        '</Task>\r\n'
    )
    xml_path = Path(tempfile.gettempdir()) / "quant_panel_guard.xml"
    xml_path.write_text(xml, encoding="utf-16")
    try:
        r = _run(["schtasks", "/create", "/tn", "QuantPanelGuard",
                  "/xml", str(xml_path), "/f"])
        return (r.returncode == 0), (r.stderr or r.stdout or "")
    finally:
        try:
            xml_path.unlink()
        except OSError:
            pass


def self_register_if_windows(root=None):
    """仅 Windows 生效；返回 True 表示执行了注册尝试，False 表示非 Windows。"""
    if sys.platform != "win32":
        return False
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    log_path = root / "logs" / "self_register.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    import datetime
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        _register_protocol(root)
        guard_ok, guard_msg = _register_guard_task(root)
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{stamp} quant-protocol=ok panel-guard="
                        f"{'ok' if guard_ok else 'fail: ' + guard_msg.strip()[:160]}\n")
        except Exception:
            pass
    except Exception as exc:  # 自我注册永远不能拖垮面板启动
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{stamp} self-register error: {exc}\n")
        except Exception:
            pass
    return True


if __name__ == "__main__":
    self_register_if_windows()
