# GitHub 双向自动同步部署说明

## 一、整体架构

```
macOS（开发调试端）                     Windows（实盘运行端）
─────────────                       ─────────────
改代码 → git push 代码仓库  ──┐
                              ├─→ git@github.com:you9095/quant-monitor.git（代码仓库）
                              └─→ Windows 工作日15:30 git pull 自动更新代码

Windows 每天15:30 跑实盘 → git push 数据仓库 ──→ git@github.com:you9095/quant-monitor-live-data.git
                                                          │
macOS 执行 scripts/sync_live_data.py pull  ←──────────────┘
→ 面板"实盘"视图展示 Windows 真实运行数据
```

- **代码仓库** `quant-monitor`（已有）：存程序代码，macOS 写 → Windows 拉
- **数据仓库** `quant-monitor-live-data`（新建私有）：只存 Windows 实盘数据

## 二、每天自动发生什么（Windows）

每个工作日 **15:30**（A股收盘后），Windows 任务计划程序自动执行 `daily_task.py`：
1. `git pull` 拉取 macOS 最新代码（**以后不用再手动拷文件/重新打包**）
2. 检查依赖
3. `run_daily.py` 跑当日实盘引擎，生成 `live-data/daily/<今天>/`
4. `sync_live_data.py push` 把实盘数据传到 GitHub
5. 重启面板

**时间窗口硬限制**：仅工作日 15:00–17:00 执行，周末/夜间/早间一律不跑，绝不 7×24。

## 三、你（用户）需要手动做的两步，只做一次

### 第 1 步：在 GitHub 建私有数据仓库
1. 浏览器打开 https://github.com/new
2. Repository name 填：`quant-monitor-live-data`
3. 选 **Private**（私有，重要）
4. 不要勾选 "Add README"，直接点 Create
5. 建好后告诉我，我在 macOS 端把骨架 push 上去

### 第 2 步：Windows 装 Git for Windows 并认证一次
1. Windows 下载安装 Git for Windows：https://git-scm.com/download/win
2. 安装时全部默认下一步即可
3. 安装完打开 Git Bash，执行：
   ```
   ssh-keygen -t ed25519 -C "you9095"
   cat ~/.ssh/id_ed25519.pub
   ```
4. 复制输出的整行公钥，到 https://github.com/settings/ssh/new 添加（Title 随便填）
5. 完成后 Windows 就能读写两个仓库了

## 四、之后怎么用

- **macOS 改了新版本**：`git push` → 第二天 Windows 15:30 自动更新，无需任何手动操作
- **macOS 想看 Windows 实盘数据**：项目目录下执行 `python3 scripts/sync_live_data.py pull`，然后面板切"实盘"
- **首次 Windows 部署**：解压新包 → 双击 `deploy_all.bat`（装环境+自动关联GitHub+注册每日任务）→ 双击 `start.bat`
