# 长江雨课堂 视频 / 图文 自动学习工具

面向个人学习辅助的雨课堂（changjiang.yuketang.cn）课程任务自动化脚本：自动遍历课程目录，按真实心跳节奏完成视频观看与图文阅读，把学习进度同步到服务器。

> ⚠️ **使用前必读**：本工具通过模拟客户端心跳上报学习进度，本质上是在伪造"观看时长"这一数据。雨课堂课程接口带有 `anti_brushing`（防刷）标记，学校侧可能据此判定异常账号。**请自行评估风险，勿用主账号试跑**，并遵守所在学校的规定。详见文末[免责声明](#免责声明)。

---

## 功能特性

**核心能力（继承自上游项目）**

- 🎥 **视频自动观看**：发送标准播放事件序列（`loadstart` / `play` / `playing` / `videoend`）与定时心跳，服务端完成率真实递增
- 📄 **图文自动阅读**：识别课程中的图文节点并调用完成接口打卡
- ⚡ **并发处理**：`ThreadPoolExecutor` 多路并发，默认 3 路
- 📈 **断点续看**：读取服务器已上报进度，从上次位置继续
- ⏭️ **智能跳过**：已完成的任务自动跳过
- 🎛️ **参数可调**：倍速、心跳间隔、并发数、停留时长全部走环境变量

**本仓库新增的工程化工具**

| 脚本 | 作用 |
|---|---|
| `check.py` | **配置体检**。只读校验 5 个配置项格式与登录态，列出视频/图文清单，不产生任何学习记录 |
| `verify.py` | **结果核验**。逐个向服务器回读真实完成率，输出满进度 / 未满 / 取不到三档，退出码可用于 CI |
| `fixup.py` | **定点补跑**。按名称前缀指定视频，绕过主程序的 90% 判定，从 `last_point - 10s` 续播到 100% |
| `.ykt_env_from_browser.mjs` | **免手抄取凭证**。从本机开着调试端口的 Chrome 读取登录态与 `classroom_id`/`sign`，按行写入 `.env`（屏幕只打印打码值） |

---

## 环境要求

| 项 | 要求 | 备注 |
|---|---|---|
| Python | 3.8+ | 实测 3.10.6；3.13 亦可，但需自行装好依赖 |
| 依赖 | 见 `requirements.txt` | 核心仅 `requests` + `python-dotenv`，其余为上游历史依赖 |
| Node.js | 18+（可选） | 仅 `.ykt_env_from_browser.mjs` 需要；用了内置 `fetch` 与 `WebSocket` |
| 浏览器 | Chrome / Edge | 仅取凭证时用，需支持 `--remote-debugging-port` |

---

## 安装

```bash
git clone https://github.com/sxllp/yuketang.git
cd yuketang
pip install -r requirements.txt
cp .env.example .env      # Windows: copy .env.example .env
```

国内网络若 `pip` 慢，可加镜像：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 配置 `.env`

需要 5 个值，全部写在项目根目录的 `.env` 里。`.env` 已被 `.gitignore` 忽略，**不要提交、不要外发**。

| 键 | 含义 | 来源 |
|---|---|---|
| `CLASSROOM_ID` | 课堂 ID（纯数字） | 课程页 URL 或课程列表接口 |
| `SIGN` | 页面请求里的 `sign` 参数 | **可以留空**（实测非必需，见[已知坑](#已知的坑)） |
| `UNIVERSITY_ID` | 学校 ID（纯数字） | Cookie `uv_id` / `university_id` |
| `CSRF_TOKEN` | CSRF 令牌 | Cookie `csrftoken` |
| `SESSION_ID` | **登录凭证** | Cookie `sessionid`（HttpOnly，Console 读不到） |

### 方式一：手动复制（最稳，凭证不经第三方）

1. 浏览器登录雨课堂，进入目标课程，点开任意一节课。
2. `F12` → **Application / 应用程序** → 左侧 **Cookies** → `https://changjiang.yuketang.cn`，复制 `csrftoken`、`sessionid`、`university_id`（没有则用 `uv_id`）。
3. `CLASSROOM_ID`：新版页面 URL 形如 `/ai-workspace/lms-graph/<课堂ID>/video/<视频ID>`，中间那串数字即课堂 ID。
4. `SIGN`：新版页面地址栏**没有** `sign`，在 Network 面板找 `.../course/chapter?cid=...&sign=...` 请求即可；拿不到就留空先试。

### 方式二：脚本自动读取（省事）

```bash
# 1) 用独立配置启动一个带调试端口的 Chrome（不干扰日常浏览器）
chrome --remote-debugging-port=9223 --user-data-dir=/tmp/ykt-cdp-profile https://changjiang.yuketang.cn/

# 2) 在该窗口里手动登录，并点进目标课程的一节课

# 3) 读取并写入 .env（只打印打码后的值）
node .ykt_env_from_browser.mjs 9223
```

用完关掉那个窗口即可（`--user-data-dir` 目录可留作下次复用登录态）。

### 方式三：临时覆盖（多门课切换）

不想反复改 `.env` 时，直接用环境变量覆盖，配置文件保持不动：

```bash
CLASSROOM_ID=12345678 UNIVERSITY_ID=1234 SIGN= python main.py
```

---

## 使用方法

推荐按「体检 → 小样 → 全量 → 核验 → 补跑」五步走，任何一步失败都能定位到具体环节。

```bash
# 1. 体检：验证配置与登录态，列出课程清单（只读，无副作用）
python check.py

# 2. 小样：先在 .env 里设 TEST_MODE=true、TEST_VIDEO_COUNT=1，跑 1 个验证链路
python main.py

# 3. 全量：确认无误后设 TEST_MODE=false，正式跑全部
python main.py

# 4. 核验：直接问服务器要真实完成率，别只看脚本自己的汇总
python verify.py

# 5. 补跑：把 verify.py 报出来的未满项逐个补到 100%
python fixup.py 3.3 6.1
```

`verify.py` 的退出码：全部满进度返回 `0`，存在未满或取不到返回 `1`，便于脚本串联。

---

## 配置参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `VIDEO_SPEED` | 视频播放倍速 | `1.5` |
| `HEARTBEAT_INTERVAL` | 心跳上报间隔（秒） | `5` |
| `MAX_CONCURRENT_VIDEOS` | 最大并发视频数 | `3` |
| `USE_CONCURRENT` | 是否启用并发（仅视频） | `true` |
| `SKIP_COMPLETED` | 是否跳过已完成任务 | `true` |
| `TEST_MODE` | 测试模式，只处理前 N 个视频 | `false` |
| `TEST_VIDEO_COUNT` | 测试模式视频数量 | `5` |
| `AUTO_RICHTEXT` | 是否自动阅读图文 | `false`（代码默认） |
| `RICHTEXT_STAY_SECONDS` | 每篇图文模拟停留（秒） | `3` |
| `RICHTEXT_SKIP_DELAY` | 篇间间隔（秒） | `1` |
| `DEBUG` | 输出调试日志 | `false` |

---

## 常见故障排查

| 现象 | 大概率原因 | 处理 |
|---|---|---|
| `[未填写]` / `[格式错]` | `.env` 未保存，或 ID 里混了字母空格 | 重新保存，ID 必须是纯数字 |
| `check.py` 拿不到章节，提示 1 | `SESSION_ID` / `CSRF_TOKEN` 过期 | 重新登录后重新取值 |
| `check.py` 拿不到章节，提示 2 | `SIGN` 失效 | 重开课程页取新 `sign`，或直接留空 |
| `check.py` 拿不到章节，提示 3 | `CLASSROOM_ID` 不属于该账号 | 核对课程页 URL |
| `ProxyError('Cannot connect to proxy.' ... 502)` | 环境里有失效的 HTTP 代理 | 剥掉代理变量直连，见下 |
| `getaddrinfo failed` | DNS 抖动 | 直接重跑，`SKIP_COMPLETED` 会续上 |
| 视频显示"已完成"但进度只有 9x% | 主程序按 `rate >= 0.9` 判定完成 | 用 `fixup.py` 定点补跑 |
| 终端中文乱码（Windows） | 代码页不是 UTF-8 | `chcp 65001` |

**绕开失效代理**（Bash / Git Bash）：

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy python main.py
```

PowerShell 下：

```powershell
$env:HTTP_PROXY=''; $env:HTTPS_PROXY=''; python main.py
```

---

## 已知的坑

这几条是实际踩出来的，改代码前建议先看：

1. **`smart_watch_video` 的 90% 阈值**。`if rate >= 0.9: return True` 会把卡在 90~99% 的视频永久跳过，重跑也补不满。需要精确补齐时用 `fixup.py`，它绕开该判断并从 `last_point - 10` 续播。
2. **`SIGN` 并非接口硬要求**。章节接口不带 `sign` 也能返回完整数据，某些课堂（如工程伦理）可以完全留空。先试空值，失败再去取。
3. **`verify.py` 才是真账**。主程序汇总里的"成功"只代表本地流程走完，服务器完成率必须单独回读。
4. **并发数不等于安全**。3 路并发是默认值，短时间高密度上报更容易被风控标记，按需调低。
5. **凭证有效期**。`sessionid` 随登录态失效，`sign` 可能短时有效；过期后重跑 `.ykt_env_from_browser.mjs` 刷新即可，`SKIP_COMPLETED` 保证不重复刷。

---

## 项目结构

```
yuketang/
├── main.py                      # 主程序：心跳类 + 并发调度 + CLI 入口
├── check.py                     # 配置体检（只读）
├── verify.py                    # 完成率核验（只读）
├── fixup.py                     # 定点补跑到 100%
├── .ykt_env_from_browser.mjs    # 从 CDP 读登录态写入 .env
├── requirements.txt             # Python 依赖
├── .env.example                 # 配置模板（可提交）
├── .env                         # 实际配置（git 忽略，含凭证）
├── .gitignore
├── README.md                    # 本文（面向使用者）
└── AGENTS.md                    # 面向 agent 的开发与维护约定
```

各文件职责、模块边界与维护约定见 [`AGENTS.md`](./AGENTS.md)。

---

## 免责声明

- 本工具仅用于个人学习与技术研究，**不得用于商业用途**。
- 使用本工具产生的任何后果（包括但不限于账号被标记、成绩被取消、学校纪律处分）由使用者自行承担。
- 请勿将本工具用于代替他人完成学习任务，或规避应当真实参与的考核环节。
- 本工具不提供任何课后测验 / 考试的答案或代答能力。
