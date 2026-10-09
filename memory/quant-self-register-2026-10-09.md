# 单文件记忆：一键启动 quant 协议免管理员自注册（2026-10-09）

## 关键结论
- 网页按钮不能直接启动本机程序；唯一合规桥接是自定义协议 quant://，但必须先在系统注册。
- 注册不能只放在“管理员安装器”里（用户不一定跑），应让**后端启动时自我注册**：
  - HKCU 注册表普通权限即可写，**无需管理员**；
  - 当前用户 onlogon 计划任务用 RunLevel=LeastPrivilege 通常普通权限可建，失败静默。
- 文件：`scripts/win_self_register.py`（仅 win32，幂等，logs/self_register.log，不阻断）；
  在 `api/real_data_server_v2.py` 的 `__main__` app.run 前调用。
- 前端触发自定义协议优先用**隐藏 iframe**（src=quant://...，3秒后移除），比 location.href 更不易在未注册时卡死页面；之后轮询 /api/v1/strategies 判定是否起来。
- 遮罩备用入口必须是真正 `<a>`：网址用 http://localhost:8000/?data_mode=... target=_blank；
  本地启动器文件用“页面目录 + encodeURIComponent(文件名)”拼 file 链接（浏览器对 .bat/.command 可能改为下载，需提示点下载项运行）。

## 教训
- “重新连接”不能只 location.reload()：后台没起时刷新仍是遮罩，用户感知为无反应；要带轮询和文字反馈。
- 任何要求用户额外“管理员跑一次安装器”的步骤都可能被跳过——能随常驻程序自动完成的系统配置，就不要依赖一次性人工授权。
- Mac 无法验证 Windows reg/schtasks；须明确告知未在真机验证，并保证失败有兜底（开机交易任务 step_restart_panel 也会起面板）。
