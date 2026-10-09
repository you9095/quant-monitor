# 单文件记忆：统一启动器 launch_panel.py（2026-10-09）

## 核心经验
- “点按钮黑窗一闪即退、无任何提示”= 跨进程隐藏启动链最后一跳失败、错误被隐藏窗口吞没。
  解决铁律：**任何代用户静默拉起的程序，stdout/stderr 必须落日志文件，失败必须有可见弹窗**。
- 启动链路越短越可靠：浏览器 quant:// 直接绑 `pythonw.exe launch_panel.py`，不要经 VBS→bat→python 多跳。
  - pythonw.exe 无控制台（不闪黑窗）；需要控制台版时用同目录 python.exe + CREATE_NO_WINDOW。
  - DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW + close_fds，stdout 指向打开的日志文件句柄。
- 幂等 + 防并发：先探 /api/v1/health；文件锁（Windows msvcrt.locking / POSIX fcntl.flock LOCK_NB）防计划任务与点击重复拉起。
- 失败可观测：ctypes.windll.user32.MessageBoxW 弹框并给出日志绝对路径；轮询给足时间（首次 git 同步慢，90s）。
- 系统配置（注册表 quant 协议、计划任务）让常驻后端启动时用普通权限自我注册（HKCU 可写、当前用户 LeastPrivilege 任务通常可建），不依赖用户管理员跑安装器。

## 文件
- scripts/launch_panel.py（统一启动器，跨平台，非 win 也能用于幂等拉起）。
- scripts/win_self_register.py（self_register_if_windows(root, highest=False)，绑定 pythonw launch_panel.py）。
- setup.py 第5步改为 import 并 highest=True；real_data_server_v2 __main__ 运行时普通权限自注册。
- 日志：logs/backend_boot.log（启动全过程）、logs/self_register.log（注册结果）、logs/launch_panel.lock。

## Mac 测试注意
- 停 launchd 服务做拉起测试后，trap 恢复要确认 `launchctl list | grep ai.quant.flask` 有 PID 且 health=200；
  bootstrap 可能因服务仍 loaded 而不生效，必要时先 bootout 再 bootstrap，再 kickstart -k。
