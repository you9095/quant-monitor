# Windows 实盘端首次部署操作清单（照着做即可）

> 目标：让 Windows 机器每天工作日 15:30 自动更新代码、跑实盘引擎、上传数据到 GitHub。
> 全程约 20 分钟，只做一次。以后全自动，不用再手动拷文件。

---

## 准备：你需要有的东西

| 项目 | 说明 |
|---|---|
| GitHub 账号 | 用户名 `you9095`，已登录浏览器 |
| Windows 机器 | 能上网，已解压最新部署包 |
| 部署包 | v4.2 `windows_deploy.zip`，解压后目录里有 `deploy_all.bat`、`start.bat` |

---

## 第 1 步：在 GitHub 建私有数据仓库（2 分钟）

这是存实盘数据的仓库，**只存数据不存代码**。

1. 浏览器打开：**https://github.com/new**
2. **Repository name** 填：`quant-monitor-live-data`
3. 选 **Private**（私有，务必选这个，不要选 Public）
4. **不要勾选** "Add a README file"、".gitignore"、"license"——全部留空
5. 点绿色按钮 **Create repository**
6. 建好后页面会显示一个空仓库。**这一步到此为止，先别关页面**，下一步要用

✅ **验证**：页面顶部显示 `you9095/quant-monitor-live-data`，且标有 "Private" 橙色标签。

⚠️ **避坑**：
- 名字必须一字不差是 `quant-monitor-live-data`，否则脚本连不上
- 必须是 Private，实盘数据不公开
- 不要加 README，否则仓库非空，首次 push 会冲突

---

## 第 2 步：Windows 装 Git for Windows（5 分钟）

1. Windows 浏览器打开：**https://git-scm.com/download/win**
2. 会自动开始下载 64-bit Git for Windows Setup
3. 双击安装包，**一路点 Next 默认安装即可**，只有两处注意：
   - 安装路径默认 `C:\Program Files\Git` 就行
   - 遇到 "Adjusting your PATH environment" 这步，选 **Git from the command line and also from 3rd-party software**（默认选中的就是这个）
4. 其他全部默认，点 Install 完成

✅ **验证**：安装完后，在 Windows 开始菜单搜 "Git Bash"，能打开一个黑色命令行窗口。

⚠️ **避坑**：
- 不要装到中文路径或带空格的路径
- 安装时如果杀毒软件弹窗拦截，选"允许"

---

## 第 3 步：Windows 生成 SSH 密钥并加到 GitHub（5 分钟）

1. 打开 **Git Bash**（开始菜单搜）
2. 复制粘贴下面这行，回车：
   ```bash
   ssh-keygen -t ed25519 -C "you9095"
   ```
3. 提示 "Enter file in which to save the key"——**直接回车**（用默认路径）
4. 提示 "Enter passphrase"——**直接回车**（不设密码，自动化才不会卡住）
5. 再回车确认一次
6. 然后执行下面这行，打印公钥：
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
7. 输出一长串，以 `ssh-ed25519` 开头、`you9095` 结尾。**整行复制**

8. 回到浏览器（第 1 步那个 GitHub 页面），打开新标签页访问：**https://github.com/settings/ssh/new**
9. **Title** 随便填，比如：`Windows实盘机`
10. **Key type** 保持 `Authentication Key`
11. **Key** 框里粘贴刚才复制的整行公钥
12. 点 **Add SSH key**

✅ **验证**（在 Git Bash 里执行）：
```bash
ssh -T git@github.com
```
第一次会问 `Are you sure you want to continue connecting`，输入 `yes` 回车。
看到 `Hi you9095! You've successfully authenticated...` 就说明通了。

⚠️ **避坑**：
- 公钥必须整行复制，不能换行、不能漏开头的 `ssh-ed25519`
- 如果 `ssh -T` 显示 Permission denied，多半是公钥没贴全，回第 3 步重新复制
- passphrase 一定要留空，否则每天自动任务会卡在输密码

---

## 第 4 步：告诉我数据仓库建好了（macOS 端我来配）

完成第 1-3 步后，跟我说一句"仓库建好了"。

我会在 macOS 上执行：
- 把数据仓库 clone 到 `live-data/`
- push 一个初始骨架（空目录结构）
- 验证双向连通

这一步我做，你不用操作。

---

## 第 5 步：Windows 首次部署（5 分钟）

1. 把最新 `windows_deploy.zip` 解压到一个**纯英文路径**，比如：
   ```
   C:\quant-monitor\
   ```
   ⚠️ 不要解压到桌面、下载文件夹、中文路径，不要放 `Program Files`。

2. 进入解压后的 `windows` 目录
3. **右键** `deploy_all.bat` → **以管理员身份运行**
4. 这个脚本会自动：
   - 检查 Python 3.11 是否装好
   - 创建虚拟环境
   - 安装所有依赖（flask、akshare 等）
   - 自动关联 GitHub 两个仓库
   - 注册 Windows 每日定时任务（工作日 15:30）

5. 等它跑完，看到 "部署完成" 提示

✅ **验证**：脚本最后会打印部署目录路径。

⚠️ **避坑**：
- 第一次装依赖可能要等 2-3 分钟（下载 flask/akshare），耐心等
- 如果提示 "Python 未安装"，去 https://www.python.org/downloads/release/python-3119/ 下载 3.11 版本，安装时**勾选 "Add Python to PATH"**

---

## 第 6 步：启动面板（每天手动开一次）

1. 在 `windows` 目录里，**双击 `start.bat`**
2. 会弹出一个黑色窗口，显示：
   ```
   启动 AI量化监控系统（模拟盘）
   访问地址: http://localhost:8000/
   ```
3. 浏览器打开 **http://localhost:8000/** 就能看到面板
4. 这个黑窗口要一直开着，关掉面板就停了

✅ **验证**：面板顶部右上角应该显示红色"模拟盘"按钮，点一下切到"实盘"。

---

## 之后每天自动发生什么（你什么都不用做）

每个工作日下午 **15:30**（A 股收盘后），Windows 自动：

```
15:30  git pull 拉最新代码（我在 macOS 更新的版本自动下来）
15:31  跑实盘引擎：拉行情 → 决策 → 真实撮合买卖 → 结算
15:35  把当天实盘数据 push 到 GitHub 数据仓库
15:36  重启面板
```

- 周末、晚上、早上**不跑**（硬限制 15:00-17:00 窗口）
- 我在 macOS 上想看 Windows 实盘数据，执行 `python3 scripts/sync_live_data.py pull`，面板切"实盘"就能看到

---

## 常见问题

| 问题 | 解决 |
|---|---|
| `deploy_all.bat` 闪退乱码 | 用管理员身份运行；确认解压路径是纯英文 |
| `ssh -T` 报 Permission denied | 回第 3 步重新复制完整公钥 |
| 面板打开 404 | 确认黑窗口在跑，地址是 `http://localhost:8000/` |
| 每天任务没跑 | Windows 任务计划程序里找 "QuantDaily"，手动运行一次看报错 |
| akshare 拉数据失败 | 脚本已带 3 次重试 + 本地缓存，偶发失败第二天自动恢复 |

---

## 你现在要做的就三件事

1. ✅ GitHub 建私有仓库 `quant-monitor-live-data`
2. ✅ Windows 装 Git for Windows + 配 SSH 公钥
3. ✅ 做完跟我说"好了"，我配 macOS 端，然后你解压新包跑 `deploy_all.bat`
