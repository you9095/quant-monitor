# -*- coding: utf-8 -*-
"""
Windows 运行时自我注册（普通用户权限、幂等、绝不阻断面板启动）。

面板后端每次启动时调用 self_register_if_windows()，完成：
  1) 注册自定义协议 quant://（HKCU，普通权限即可，无需管理员），
     index.html 的“一键启动数据后台”经 quant://start-backend 直接调
     pythonw.exe scripts/launch_panel.py（统一启动器，无黑窗、带日志/错误弹窗）；
  2) 创建当前用户计划任务 QuantPanelGuard（登录 30 秒后、每 5 分钟跑一次
     launch_panel.py，后台没在就拉起，已在就退出）。
任何异常只写 logs/self_register.log，不影响面板启动；非 Windows 为 no-op。
模拟盘、本机真实撮合，绝不连接任何券商真实账号/资金账号。
"""

import sys
import base64
import subprocess
import tempfile
import datetime
from pathlib import Path


def _run(args, timeout=25):
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(args, capture_output=True, text=True,
                          timeout=timeout, creationflags=creationflags)


def _pythonw():
    """与当前后端同目录的 pythonw.exe（无控制台，点击协议时不弹黑窗）。"""
    exe = Path(sys.executable)
    cand = exe.with_name("pythonw.exe")
    return str(cand if cand.exists() else exe)


def _register_protocol(root, launcher, pythonw):
    proto = r"HKCU\Software\Classes\quant"
    command_val = f'"{pythonw}" "{launcher}" "%1"'
    _run(["reg", "add", proto, "/ve", "/d", "URL:Quant Panel Launch", "/f"])
    _run(["reg", "add", proto, "/v", "URL Protocol", "/d", "", "/f"])
    _run(["reg", "add", proto + r"\shell\open\command", "/ve",
          "/d", command_val, "/f"])
    return command_val


def _register_guard_task(root, launcher, pythonw, highest):
    run_level = "HighestAvailable" if highest else "LeastPrivilege"
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
        f'    <Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>{run_level}</RunLevel></Principal>\r\n'
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
        f'      <Command>"{pythonw}"</Command>\r\n'
        f'      <Arguments>"{launcher}"</Arguments>\r\n'
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


def _create_desktop_shortcut(root, launcher, pythonw):
    """在当前用户桌面创建“AI量化面板”快捷方式（普通权限、幂等）。

    双击它 = pythonw.exe launch_panel.py --open：无黑窗、后台没起就静默拉起，
    就绪后自动用默认浏览器打开 http://localhost:8000/ 同源面板。
    PowerShell 用 -EncodedCommand(UTF-16LE base64) 传参，规避中文/GBK 编码雷。
    """
    ps = (
        "$ws = New-Object -ComObject WScript.Shell\n"
        "$desktop = [Environment]::GetFolderPath('Desktop')\n"
        "$lnk = Join-Path $desktop 'AI量化面板.lnk'\n"
        f"$s = $ws.CreateShortcut($lnk)\n"
        f"$s.TargetPath = '{pythonw}'\n"
        f"$s.Arguments = '\"{launcher}\" --open'\n"
        f"$s.WorkingDirectory = '{root}'\n"
        "$s.WindowStyle = 7\n"
        "$s.Description = 'AI Quant Panel (simulation, local matching, no broker)'\n"
        "$s.Save()\n"
        "Write-Output $lnk\n"
    )
    enc = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
    r = _run(["powershell", "-NoProfile", "-NonInteractive",
              "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc], timeout=30)
    out = (r.stdout or r.stderr or "").strip()
    return (r.returncode == 0 and out.endswith(".lnk")), out


def self_register_if_windows(root=None, highest=False):
    """返回 True 表示在 Windows 上执行了注册尝试；非 Windows 返回 False。"""
    if sys.platform != "win32":
        return False

    root = Path(root) if root else Path(__file__).resolve().parent.parent
    log_path = root / "logs" / "self_register.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        launcher = root / "scripts" / "launch_panel.py"
        pythonw = _pythonw()
        command_val = _register_protocol(root, launcher, pythonw)
        guard_ok, guard_msg = _register_guard_task(root, launcher, pythonw, highest)
        sc_ok, sc_msg = _create_desktop_shortcut(root, launcher, pythonw)
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{stamp} quant-protocol=ok handler='{command_val}' "
                        f"panel-guard={'ok' if guard_ok else 'fail: ' + guard_msg.strip()[:160]} "
                        f"desktop-shortcut={'ok' if sc_ok else 'fail: ' + sc_msg.strip()[:160]}\n")
        except Exception:
            pass
    except Exception as exc:  # 自我注册永远不能拖垮面板
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{stamp} self-register error: {exc}\n")
        except Exception:
            pass
    return True


if __name__ == "__main__":
    self_register_if_windows()
