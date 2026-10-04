# Windows 实盘端部署运维手册（v9 定型）

> 最后更新：2026-10-04
> 适用：AI 量化监控项目，Windows 实盘端（主机名"钧泽"）首次成功部署后

## 1. 架构分工
- **macOS**：设计 / 开发 / 数据诊断 / 调试 / 面板（localhost:8000）。
- **Windows**：实盘撮合运行。**不接任何券商真实账号、无资金账号**；"实盘"指本机撮合引擎按真实行情成交、真实记账（佣金/印花税/滑点/T+1）。
- 双向同步：GitHub 两个仓库中转，无人肉搬运。
  - 代码 `you9095/quant-monitor`（master）
  - 数据（私有）`you9095/quant-monitor-live-data`（master，唯一分支）

## 2. 一键安装器形态（v9）
- 单文件 `install_v9.bat`：第 1 行 cmd 钥匙，第 2 行起全 Python（`python -x` 执行）。
- 下载：仓库页 `install_v9.bat` → Download raw file；**每版换新文件名**避免缓存。
- 失败自愈：顶层异常捕获 → 桌面 `quant-install-log.txt` → 记事本打开 → 等待按键，绝不闪退。
- 网络通道：SSH `ssh.github.com:443` → SSH22 → HTTPS；自动探测本地代理。

## 3. Windows 目录与任务
- 代码：`D:\quant-monitor`；安装期数据通道：`D:\_qm_live`；日志：`D:\quant-monitor-install.log`。
- 三计划任务（schtasks，当前用户）：
  - QuantExecuteTask（成交）
  - QuantDecideTask（决策+更新代码）
  - QuantBootCheck（开机自检+上报）
- 启动面板：`D:\quant-monitor\start.bat` → http://localhost:8000

## 4. 观察 Windows 的唯一方法
在 macOS 的 `live-data/` 目录：
```
git fetch origin && git ls-tree -r --name-only origin/master _install_status/ _deploy_status/
git show origin/master:_install_status/<COMPUTERNAME>.txt
git show origin/master:_deploy_status/<hostname>.json
```
- `_install_status/`：安装期心跳（ONLINE/CODE_READY/SETUP_START/SUCCESS/FAILED）。
- `_deploy_status/<hostname>.json`：运行期心跳（依赖、venv、三任务是否 REGISTERED、code_commit）。
- 连不上 GitHub 前是物理盲区，此时看 Windows 桌面自动弹出的诊断文件。

## 5. 已知整改（10-07 前）
- **调度改开机触发**：电脑只在交易日 13:00–17:00 开机，废弃 09:35 固定成交，改开机即跑当日 decide+按最新价/收盘价成交。
- **10-06 17:00 归零**：`reset_accounts.py` 重置六策略账本为空仓各 1 万；不删 K 线缓存。
- Mac 面板启动/定时 `pull` 数据仓库，网页即显 Windows 实盘。

## 6. 红线
- 永远模拟盘，不接券商。
- 任何数据必须标注性质（模拟/实盘/回测）；未启动策略留空，不用回测值冒充。
- 时间窗口固定在交易日盘中/下午，不 7×24。
