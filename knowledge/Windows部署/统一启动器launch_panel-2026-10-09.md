# Windows 一键启动：统一启动器 launch_panel.py（2026-10-09，取代多跳链路）

> 取代《一键启动免管理员自注册-2026-10-09》里 quant://→VBS→bat→python 的多跳方案。多跳链路在最后一跳失败时错误被隐藏窗口吞没，表现为“黑窗一闪即退、无提示”。

## 统一入口
所有启动方式都调用 `scripts/launch_panel.py`：
- index.html 绿色按钮 → quant://start-backend
- 计划任务 QuantPanelGuard（登录30秒 + 每5分钟）
- 启动器文件 `启动AI量化面板.bat`（=scripts/start_panel_quiet.bat）/ `启动AI量化面板.command`

## launch_panel.py 行为
1. 文件锁 logs/launch_panel.lock（msvcrt/fcntl 非阻塞），拿不到锁说明另一实例在负责，直接退出。
2. GET http://127.0.0.1:8000/api/v1/health，200 即“已在运行”，退出码 0。
3. 未运行：解释器选同目录 python.exe（协议处理器是 pythonw.exe 时换算成 python.exe），
   以 DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP|CREATE_NO_WINDOW（Windows）或 start_new_session（Mac）
   拉起 `python -u api/real_data_server_v2.py`，cwd=项目根，stdout/stderr 追加 logs/backend_boot.log。
4. 每 2 秒探活，最多 90 秒；200 退出码 0；超时/异常用 MessageBoxW 弹框并给出日志路径，退出码 1/2。

## 注册（win_self_register.py）
- self_register_if_windows(root=None, highest=False)，仅 win32。
- 解释器：Path(sys.executable).with_name('pythonw.exe')。
- quant 协议 HKCU\Software\Classes\quant\shell\open\command 默认值：
  `"<root>\venv\Scripts\pythonw.exe" "<root>\scripts\launch_panel.py" "%1"`（普通权限 HKCU，无需管理员）。
- QuantPanelGuard 任务 XML：Exec Command=pythonw、Arguments=launch_panel.py；
  RunLevel = HighestAvailable（安装器 highest=True）或 LeastPrivilege（后端运行时自注册）；
  LogonTrigger 延迟30秒 + 每5分钟、IgnoreNew、ExecutionTimeLimit PT5M。
- 结果写 logs/self_register.log；异常不阻断后端。
- setup.py 第5步直接 import win_self_register 并 highest=True（删除内联 reg/XML，单一真相）。

## 后备文件
- scripts/panel_guard.vbs：仅在旧注册仍指向 wscript 时兜底，内容改为无窗运行 venv pythonw launch_panel.py（纯 ASCII）。
- scripts/start_panel_quiet.bat：手动双击兜底，venv python 跑 launch_panel.py，失败 pause（纯 ASCII）。
- 启动AI量化面板.command：Mac 双击，venv python 跑 launch_panel.py 后 open 实盘网址。

## 排障（Windows）
- 点按钮无反应/闪退：先看 D:\quant-monitor\logs\backend_boot.log（启动全过程与报错），
  再看 logs\self_register.log（协议/任务注册结果，应为 quant-protocol=ok）。
- 若协议仍指向旧 VBS：确认后端已用新代码重启过一次（重启即自注册改绑 pythonw）；
  或管理员重跑 install_v9.bat（setup.py 第5步 highest 注册）。
- 兜底：开机交易任务 QuantDailyTrade 的 step_restart_panel 本就会起面板。

## 验证
- Mac：停服后运行 launch_panel.py 能 detached 拉起后端、health=2000、日志完整；launchd 已恢复常驻。
- Windows 真机 pythonw/schtasks 行为未在 Mac 验证，依赖弹窗+日志+开机任务三重兜底。
