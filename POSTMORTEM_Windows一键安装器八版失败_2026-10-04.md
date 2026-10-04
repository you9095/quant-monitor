# POSTMORTEM：Windows 一键安装器连续八版失败、v9 改 Python 后一次成功 (2026-10-04)

> 类型：工程事故复盘（部署工具链，非策略数据事故）
> 影响：Windows 实盘端首次成功部署（`钧泽`，win32 / Python 3.11.9）
> 状态：v9（commit `e08053e`）一次跑通，全链路闭环，三计划任务 REGISTERED
> 铁律关联：不涉及规则2/5/7的策略数据事故；但"反复拿用户当测试员"属流程事故，留痕。

---

## 一句话结论

v1–v8 全部用 **Windows cmd 批处理**写安装逻辑，而 cmd 既脆弱、又无法在 macOS 端运行验证——Agent 只能静态检查，实际是用户在 Windows 上当编译器。v9 把结构改成 **一行 cmd 钥匙 + 主体全 Python**（`python -x` polyglot），Python 在 Mac 上可真实运行、有全局异常捕获，于是一次成功。**失败原因逐版不同，但底层是同一个方法论错误。**

---

## 一、用户三连问的直接回答

### Q4.1 为什么 v9 不用 BAT、改用了什么？
不是 JSON（口误），是 **Python**。v9 是一个单文件 `install_v9.bat`：
- 物理第 1 行是一行最朴素的 cmd（找 Python 来运行自己、末尾强制 `pause`）；
- 从第 2 行起**全部是 Python 代码**，靠 `python -x`（标准库参数，跳过源文件第 1 行）执行。
- cmd 只执行第 1 行就 `exit /b`，后面的 Python 它根本不解析；Python 主体包在顶层 `try/except` 里，任何错误都会打印 traceback、写桌面诊断、弹记事本、`input()` 等待，**物理上不可能静默闪退**。

### Q4.2 v9 成功的核心原因
1. **可在 macOS 真机验证**：Agent 用 `python3 -x install_v9.bat --selftest` 在本机真实跑通核心逻辑（找到 git、探测到本地代理 7890、`ssh.github.com:443` 认证返回 `Hi you9095! successfully authenticated`），并**注入一个致命异常**验证它被捕获、写桌面诊断、以可控码退出。不再靠用户试错。
2. **消除闪退这一致命症状**：全局异常保护 + 双保险等待（Python `input` + cmd `pause`）。
3. **新文件名 `install_v9.bat`**：GitHub 上全新 URL，绕开浏览器 raw 缓存和下载目录里的旧文件混淆（v8 一直失败的隐藏原因就是用户双击的还是缓存的 v7）。
4. **沿用 v6 以来正确的网络决策**：SSH 走 `ssh.github.com:443` 首选 → SSH22 → HTTPS（+自动探测本地代理）。

### Q4.3 v1–v8 失败原因是否相同？——不相同，逐版不同，但同根
| 版本 | 当次的直接故障 | 故障类别 |
|---|---|---|
| v1–v2 | bat 含中文/非 ASCII 或 LF 换行 → cmd 乱码（"'t' 不是内部命令"） | 编码 / 换行 |
| v3 | 无超时 `import akshare` 卡死，setup 黑窗口直接消失、无 pause | 缺超时 / 无异常兜底 |
| v4–v5 | `Start-Process -Verb RunAs` 自动提权，双击时两个窗口并存被误判"另一个程序正在运行" | UAC / 双开 |
| v6 | 国内运营商封 SSH 22 端口、HTTPS 被 SSL 重置，数据仓库零心跳 | 网络通道（漏了 443） |
| v7 | 全新 Git 缺 `user.name/email` 致 commit 失败；残留锁 30 分钟内判 fresh 挡住重跑 | 身份 / 锁设计 |
| v8 | 用户实际双击的还是缓存的 v7；锁"8 秒自动关闭"；cmd 嵌套解析陷阱导致十几秒闪退 | 缓存 / 锁 / cmd 脆弱性 |

**两个贯穿始终的底层根因：**
- **根因 A（方法论）**：用 cmd 写复杂逻辑，而 macOS 无法运行 cmd 做验证，只能"括号配平/纯 ASCII"这种静态猜测，等于让用户替 Agent 当编译器。
- **根因 B（物理盲区）**：在"连上 GitHub 之前"任何失败都是静默的——Windows 在用户家中主动外连，数据仓库是唯一远程通道，连不上时 Agent 完全瞎。v8/v9 用"失败自动写桌面诊断 + 弹记事本"把盲区补上。

---

## 二、时间线（2026-10-04）

- 20:12:56 Windows `钧泽` 第一条 `ONLINE`（SSH443，auth=ok，代理 7897）
- 20:13:12 `CODE_READY`，代码 clone 到 `D:\quant-monitor`，版本 `e08053e`
- 20:13:21 `SETUP_START`
- 20:13:45 `deploy heartbeat`：venv_exists=true，依赖 flask/akshare/pandas/numpy/requests 全装好
- 20:13:54 `SUCCESS`，setup rc=0，三计划任务 QuantExecuteTask/QuantDecideTask/QuantBootCheck 全部 REGISTERED

## 三、可复用经验（写进后续所有部署工具）
1. **跨平台部署逻辑一律用 Python 写**，cmd 只做"找解释器 + pause"的一行钥匙；绝不写嵌套括号/for-f 套 PowerShell。
2. **先在开发机真机跑通核心路径再交付**（`--selftest` 模式），不交付未在本机验证过的脚本。
3. **每版用新文件名**，杜绝浏览器 raw 缓存把旧版当新版。
4. **失败必须可观测**：顶层异常捕获 + 桌面诊断文件 + 记事本自动打开，消除"连不上 GitHub"时的物理盲区。
5. **防双开锁只保留语义、绝不阻塞用户**：残留锁（手动关窗/闪退/重启）一律自动接管，不 8 秒退出。
6. 国内连 GitHub：SSH 走 `ssh.github.com:443` 首选；自动探测 Clash/v2ray 本地端口并配置 git 代理。

## 四、遗留（需后续处理）
- **[P0] 调度与开机时间不匹配**：现 QuantExecuteTask 定在工作日 09:35 按开盘价成交，但用户 Windows 只在交易日 13:00–17:00 开机，09:35 任务永不触发 → 成交全部缺席。需改为"开机即跑当日 decide+成交"。详见同日工作日志。
- 10-06 17:00 账户归零、10-07 实盘第一天从零开始（用户明确指令，合规）。
