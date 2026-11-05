# AGENTS.md

面向自动化 agent / 后续维护者的工程说明。**使用者向的安装与用法在 [`README.md`](./README.md)，本文件不重复。**

---

## 1. 项目定位

单进程 Python CLI，把雨课堂（`changjiang.yuketang.cn`）课程目录里的视频 / 图文节点，按模拟心跳的方式上报学习进度到服务端。

- **无服务端、无数据库、无状态持久化**：所有状态都在服务端，本地只有 `.env` 配置和 `.run*.log` 日志。
- **单文件主程序**：`main.py` 承载全部业务逻辑（约 1450 行），三个辅助脚本通过 `from main import YuketangHeartbeat` 复用。
- **零 Web 依赖**：纯 `requests` 直接打接口，不使用浏览器自动化执行业务。

---

## 2. 环境与解释器

| 项 | 约定 |
|---|---|
| Python | 3.8+，实测 3.10.6。`main.py` 已用 `py_compile` 校验 3.10 兼容 |
| 依赖 | `requests`、`python-dotenv`（其余 `requirements.txt` 条目为上游历史依赖，可运行但非必需） |
| Node | 仅 `.ykt_env_from_browser.mjs` 需要 18+（依赖内置 `fetch` / `WebSocket`），不引入 npm 依赖 |
| Shell | Windows 上默认 Git Bash；**不要**假设 `cmd` |

**解释器选择**：本机可能存在多个 Python，PATH 上的 `python` 未必装了依赖。执行前先确认：

```bash
python -c "import requests, dotenv; print('ok')"
```

失败时换用已装依赖的解释器（例如绝对路径调用），**不要**为此在脚本里硬编码解释器路径。

**编码**：Windows 终端中文乱码时先 `chcp 65001`；脚本内部已 `warnings.filterwarnings("ignore")` 屏蔽 urllib3 版本告警，属预期行为。

---

## 3. 命令速查

```bash
# 依赖
pip install -r requirements.txt

# 只读：配置体检 + 登录态验证 + 课程清单
python check.py

# 主流程（参数全部来自 .env）
python main.py

# 只读：逐视频回读服务器真实完成率，退出码 0=全满 / 1=有未满
python verify.py

# 定点补跑，参数为视频名称前缀（可多个）
python fixup.py 3.3 6.1

# 语法自检
python -m py_compile main.py check.py verify.py fixup.py
```

**绕开失效代理**（本环境常见故障，见 §7）：

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy python main.py
```

**临时切课**（不改 `.env`）：

```bash
CLASSROOM_ID=12345678 UNIVERSITY_ID=1234 SIGN= python main.py
```

---

## 4. 文件职责

| 文件 | 职责 | 是否写状态 |
|---|---|---|
| `main.py` | 心跳类 `YuketangHeartbeat`、接口封装、并发调度、CLI 入口 | 只写服务端 |
| `check.py` | 5 项配置校验（占位符 / 纯数字）+ 登录态探测 + 清单打印 | ❌ 只读 |
| `verify.py` | 遍历全部视频，调 `auto_configure_from_ids` + `get_current_progress_info` 回读 `rate` | ❌ 只读 |
| `fixup.py` | 按名称前缀命中视频，绕过 90% 判定，从 `last_point - 10` 续播 | ✅ 唯一显式补漏入口 |
| `.ykt_env_from_browser.mjs` | 连 CDP `127.0.0.1:<port>`，读 URL/`sign`/`localStorage`/全部 Cookie，按行改写 `.env` | 只写本地 `.env` |

**约定：标 ❌ 的脚本必须保持只读。** 新增诊断脚本时沿此约定，并在 docstring 首行注明「只读」。

---

## 5. `main.py` 结构地图

`class YuketangHeartbeat`（约 L35 起），按调用层次：

**构造与参数**
- `__init__(cookies)` — 注入 Cookie 字典（键名固定：`csrftoken`/`sessionid`/`uv_id`/`university_id`/`classroomId`/`classroom_id`/`xtbz`/`platform_id`/`platform_type`/`login_type`/`django_language`）
- `create_worker_instance()` — 克隆会话，供并发 worker 使用
- `set_video_params(...)` / `auto_configure_from_ids(classroom_id, leaf_id, sign)` — 拉取 leaf 详情并填充 `user_id`/`course_id`/`video_id`/`sku_id` 等心跳必需字段

**接口层（只读）**
- `get_course_chapters(classroom_id, sign)` — 课程目录，入口接口
- `get_video_leaf_list(...)` / `get_richtext_leaf_list(...)` — 按 `leaf_type` 过滤（`0`=视频，`3`=图文）
- `get_leaf_info` / `get_video_info_alternative` / `get_video_play_url` / `get_classroom_info` / `get_watermark_config` / `get_video_drag_permission` / `get_current_progress_info`
- `find_video_in_course_structure` / `debug_video_ids` — 调试辅助

**上报层（写）**
- `create_heartbeat_data(event_type, current_position, ...)` — 构造心跳体
- `send_heartbeat(heart_data_list)`
- `simulate_video_watching(total_duration, speed, interval, start_position)` — 核心循环，按 `interval` 推进 `current_position`
- `view_richtext` / `batch_view_richtexts` — 图文完成上报

**调度层**
- `smart_watch_video(speed, interval)` — 单视频 + **90% 阈值判定**（见 §7.1）
- `watch_single_video_worker(...)` — 线程体
- `concurrent_watch_videos(...)` — `ThreadPoolExecutor`，读 `MAX_CONCURRENT_VIDEOS`
- `batch_watch_videos(...)` — 串行兜底

**入口**
- `main()` — 读环境变量 → 组 cookies → 选择并发/串行 → 打印汇总

---

## 6. 关键接口

| 用途 | 路径 |
|---|---|
| 课程目录 | `/mooc-api/v1/lms/learn/course/chapter?cid=<cid>&classroom_id=<cid>&term=latest` |
| 目录（新版 KG） | `/mooc-api/v1/lms/kg/student_learn_chapter/?cid=<cid>&classroom_id=<cid>` |
| 课程列表 | `/v2/api/web/courses/list?identity=2`（取 `classroom_id`、`course.name`） |
| 心跳上报 | 见 `send_heartbeat` 内常量 |
| 图文完成 | `user_article_finish`（见 `view_richtext`） |

请求统一带 `xtbz: ykt`、`platform-id: 3`、`Accept: application/json`，会话级靠 `sessionid` Cookie 鉴权。`sign` 为页面级签名参数，**实测非必需**。

---

## 7. 必须知道的坑

### 7.1 90% 阈值会漏补
`smart_watch_video` 中 `if rate >= 0.9: return True`，把 90~99% 的视频当已完成 → 永久跳过，重跑无效。
**改动前须知**：这是上游行为，被多个调用点依赖；调严到 `0.999` 会让"接近完成"的视频全量重播，成本剧增。需要精确补齐走 `fixup.py`，不要随手改阈值。

### 7.2 `SIGN` 不是硬依赖
章节接口不带 `sign` 也能返回完整数据。`check.py` 把 `SIGN` 列为必填项是历史遗留——某些课堂可以完全留空。遇到「拿不到章节」先怀疑 `sessionid` 过期，再怀疑 `sign`。

### 7.3 两种 URL 形态
- 旧版：`/pro/livecast/<cid>?sign=...`（地址栏可见 sign）
- 新版：`/ai-workspace/lms-graph/<cid>/video/<leaf_id>?node_id=...`（**地址栏无 sign**，sign 只在 XHR 里）

提取板书 id 时两种都要兼容（参考 `.ykt_env_from_browser.mjs` 的正则双分支）。

### 7.4 代理会让整批瞬间失败
沙箱/系统代理失效时，`requests` 在每个视频的"配置参数"阶段即抛 `ProxyError`，特征是日志里短时间内大量同一错误、进程提前退出。
**排查顺序**：先 `curl --noproxy '*' https://127.0.0.1:<port>/json/version` 确认本地回环可用 → 再 `env -u ... python main.py` 直连重跑。

### 7.5 不能只看脚本自报
`main()` 的汇总统计是本地流程结果，不代表服务端完成率。**改动任何上报逻辑后，必须跑 `verify.py` 复核**，这是唯一可信的验收标准。

### 7.6 新版前端 SPA 不吃合成点击
`/v2/web/classroom/<cid>` 会跳错误页；`Input.dispatchMouseEvent` 对路由无效（路由不在 `<a href>` 上）。需要页面态时用 `Page.navigate` 直连真实 URL，不要试图模拟点击。

---

## 8. 维护约定

**提交纪律**

1. `.env`、`.run*.log`、`__pycache__/`、`.workbuddy/` 一律不入库（已由 `.gitignore` 覆盖）。**任何提交前先 `git status` 确认没有 `.env`。**
2. 日志里可能出现 `sign`、Cookie 片段——不要把日志内容粘进 commit message、issue 或 README。
3. 输出凭证时统一打码（前 4 + `*` + 后 4），`check.py` 与 `.mjs` 已实现，新增脚本沿用。
4. 路径不写死绝对路径：`.env` 一律用 `process.cwd()` / `load_dotenv()` 相对解析，解释器路径不写进 docstring。

**代码约定**

- 不新增运行时依赖。够用的场景用标准库（`ThreadPoolExecutor`、`argparse` 亦可，现有脚本用 `sys.argv` 保持轻量）。
- 新增 CLI 脚本必须：有 `#!/usr/bin/env python3` 与 `# -*- coding: utf-8 -*-`、docstring 写明用途与用法、用 `sys.exit()` 表达结果、只读脚本注明只读。
- 异常处理以"能续跑"为原则：单个 leaf 失败不应终止整批（`watch_single_video_worker` 已如此）。
- 打印风格保持中文、分节用 `"=" * 60`，与现有脚本一致。

**改动后的验收清单**

```bash
python -m py_compile main.py check.py verify.py fixup.py   # 1. 语法
python check.py                                            # 2. 登录态与清单仍可读
TEST_MODE=true TEST_VIDEO_COUNT=1 python main.py           # 3. 单视频链路
python verify.py                                           # 4. 服务器侧真实完成率
```

**边界**

- 本项目不实现、不协助实现课后测验 / 考试的题目抓取与答案生成。涉及 `leaf_type=6`（习题节点）时，`get_video_leaf_list` / `get_richtext_leaf_list` 会自然过滤掉，**不要**为其新增采集逻辑。
- 不实现绕过平台字体混淆、反作弊 SDK 的抓取路径。

---

## 9. 排障决策树

```
check.py 失败
├─ [未填写]/[格式错] → .env 未存盘 / ID 含非数字
└─ 拿不到章节
   ├─ SESSION_ID 过期（最常见）→ 重新登录取值
   ├─ SIGN 失效 → 置空先试
   └─ CLASSROOM_ID 不匹配账号 → 核对课程页

main.py 跑完但有失败
├─ 大量 ProxyError → 剥代理直连重跑
├─ getaddrinfo failed → 直接重跑（SKIP_COMPLETED 续）
└─ 零星 ❌ → 定位名称用 fixup.py 补

verify.py 报未满
├─ 90~99% → fixup.py <前缀>
└─ 取不到 → 单独跑 check.py 确认该 leaf 是否还存在（可能已下架）
```
