# 记忆：「唤醒即继续」调度增强 + 当日收盘自动成交（2026-10-16）

- **用户铁律（最高优先）**："不让电脑休眠或黑屏是不可能的，永远做不到。" 程序不能依赖电脑一直醒着，必须**唤醒即继续**：用户按键唤醒后立刻侦测到，并立即继续未完成任务（尤其收盘后自动成交/补记），不靠人手动双击或盯时间。
- **新计划任务 QuantWakeResume（已开发推送，待 Windows 注册）**：
  - EventTrigger 订阅 System 日志 Microsoft-Windows-Kernel-Power：**107**（睡眠/休眠恢复，传统 S3）、**507**（退出新式待机）、**566**（现代待机 S0 恢复）——三种电源状态全覆盖；
  - SessionStateChangeTrigger=**SessionUnlock**（解锁）+ LogonTrigger 延迟 15 秒；
  - 动作 pythonw launch_panel.py，唤醒后立即跑完整总控。
  - 设 WakeToRun=false（不主动唤醒，只响应用户唤醒）、StartWhenAvailable=true。
- **三层保障**：①唤醒/解锁事件立即触发（"立刻"）；②收盘窗口高频兜底（QuantPanelGuard 5→2 分钟、QuantTradeGuard 15:30–17:30 10→2 分钟，15:00–15:30 本就 2 分钟）；③全部任务 StartWhenAvailable=true，睡眠错过的唤醒后补跑。
- **正确性保障**：daily/<today>/<sid>.json 已存在则 run_once 返回 already（幂等，不重复成交）；唤醒后窗口内未成交则收盘后现价=收盘价立即撮合；唤醒后网络未就绪则三源（东财→腾讯→新浪）持续重试（前 3 轮快速、之后 10 分钟），绝不用旧价/伪造。
- **注册结果留痕**：guard_register.json 新增 wake_resume_ok/wake_resume_detail；self_register 日志新增 wake-resume；verify_windows_sync 的 REQUIRED_TASKS 加 QuantWakeResume。
- **当日（10-16）成交**：6/6 done，15:20:02 收盘后自动完成（无人工），daily 六策略齐全；trades_total=0（信号未变，持仓/观望正常）。合计资产 58140.27，累计 -1859.73（-3.10%）；goldcombo 当日 -206.13（-2.06%，海外/商品真实回调）。
- **版本**：代码 master = `022bb18`（win_self_register + verify_windows_sync，已 push）；Windows 当时仍停旧版 50ffdb0（心跳 15:20:05）。
- **Mac 校验**：py_compile 通过；捕获 XML 验证三触发器齐全、Subscription 解码为合法 QueryList、事件 ID 与 SessionUnlock 正确。
- **Windows 注册路径**：推荐唤醒后双击一次桌面"AI量化面板"（立即更新+注册，最快）；否则旧版 QuantPanelGuard 唤醒后下一个周期自动更新（旧版未绑唤醒，最坏等 5 分钟）。注册后心跳 tasks_all_Quant 出现 QuantWakeResume，此后永久生效。
- **教训**：① 不要反复要求"保持开机别休眠"，用户做不到，正确做法是把"唤醒后立即续跑"做进系统；② 电源事件须同时覆盖 S3/新式待机 S0/休眠（107/507/566），只绑一个会漏；③ 事件触发 + 高频兜底 + 补跑缺一不可，单一机制在部分 Windows 上可能不生效。
- **待办**：Windows 双击后远程确认 QuantWakeResume 注册（#74）；其余 UI 走查（#35）。
- **日常**：每个交易日双击桌面"AI量化面板"即全自动（唤醒后也会自动续跑）；全程模拟盘、本机真实撮合，不接券商真实/资金账号。
