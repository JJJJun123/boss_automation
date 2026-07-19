# BYOK（用户自带 API Key）设计文档

**日期：** 2026-07-18
**状态：** 已批准（用户确认方案 1 + 全走用户 provider + 试用 3 次后必填 + 三家全开）
**需求来源：** ~/.claude/office-hours-docs/20260718-byok-and-chat.md

## 目标

用户在设置面板填入自己的 AI API Key（DeepSeek / Claude / GPT 三选一），此后其搜索任务的两阶段 AI 分析全部走用户自己的 Key。新用户可免费试用 3 次（走站方 Key），超限后必须配置。站方模型成本归零。

## 非目标

- 不做多 Key 共存（一个用户同时存多家 Key）——一人一条，换 provider 覆盖
- 不做用量统计/账单展示（后续阶段）
- 不做自定义 base_url 中转接入（后续可扩）

## 核心决策

| 决策         | 结论                                          | 理由                                                                                              |
| ------------ | --------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Key 注入方式 | 参数透传（app → analyzer → factory → client） | 显式、可测、并发安全；contextvars 在 threading+asyncio 混合环境有传播风险；改环境变量并发会串 key |
| 双阶段费用   | 两阶段都走用户 provider                       | 阶段一映射到该家便宜模型；站方彻底零成本                                                          |
| 无 Key 策略  | 试用 3 次后 402 强制                          | 成功任务才计数；有 Key 用户永不扣                                                                 |
| 加密         | Fernet + 独立 `APP_ENCRYPTION_KEY` 环境变量   | 与 FLASK_SECRET_KEY 分离，轮换互不影响                                                            |
| Key 验证     | 存库前 `GET /models`（三家通用、免费）        | 10s 超时；失败不透传原始报错                                                                      |

## 组件设计

### 1. `backend/key_vault.py`（新）

```
encrypt_key(plain: str) -> str          # Fernet 加密，密钥从 APP_ENCRYPTION_KEY 派生
decrypt_key(token: str) -> str          # 解密；密钥错/数据损坏抛 KeyVaultError
mask_key(plain: str) -> str             # "sk-***ab12"，只露尾 4 位；短 key 全掩
validate_api_key(provider, key) -> bool # GET /models 打真实验证，10s 超时
load_encryption_key() -> bytes          # 缺 APP_ENCRYPTION_KEY 时 fail-fast（同 FLASK_SECRET_KEY 模式）
```

验证端点：deepseek `https://api.deepseek.com/models`；openai `https://api.openai.com/v1/models`；claude `https://api.anthropic.com/v1/models`（header `x-api-key` + `anthropic-version`）。

### 2. `utils/state_store.py`（扩展）

```sql
CREATE TABLE IF NOT EXISTS user_api_keys (
    user_id          TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    provider         TEXT NOT NULL,          -- deepseek | claude | gpt
    key_encrypted    TEXT NOT NULL,
    created_at       REAL NOT NULL,
    last_verified_at REAL
);
-- users 表迁移：ALTER TABLE users ADD COLUMN trial_searches_used INTEGER NOT NULL DEFAULT 0
```

方法：

- `set_user_api_key(user_id, provider, key_encrypted)`：UPSERT（换 provider 覆盖旧条目）
- `get_user_api_key(user_id) -> Optional[dict]`：{provider, key_encrypted, last_verified_at}
- `delete_user_api_key(user_id) -> bool`
- `get_trial_usage(user_id) -> int` / `increment_trial_usage(user_id) -> int`
- 迁移函数 `_migrate_users_table`：老库补 `trial_searches_used` 列（模式同 `_migrate_tasks_table`）

### 3. `analyzer/` 改造（参数透传链）

- 5 个 client（deepseek / claude / claude_sdk / gpt / gpt_sdk）：`__init__(model_name=None, api_key=None)`，内部 `self.api_key = api_key or os.getenv(...)`——不传参行为与现状完全一致
- `AIClientFactory.create_client / create_pure_client` 加 `api_key=None` 参数，透传给 client 构造
- `EnhancedJobAnalyzer.__init__` 加 `api_key=None`，传给 extraction_service 与 JobAnalyzer
- `JobAnalyzer.__init__` 加 `api_key=None`，透传其内部 client 创建

### 4. 双阶段模型映射（`config/app_config.yaml`）

```yaml
ai:
  byok:
    trial_limit: 3
    provider_models:
      deepseek: { screening: deepseek-v4-flash, analysis: deepseek-v4 }
      claude: { screening: claude-haiku-4-5, analysis: claude-sonnet-5 }
      gpt: { screening: gpt-5-mini, analysis: gpt-5.2 }
```

任务启动时按用户 provider 查表得两阶段模型名；无 Key 试用期沿用现有 DeepSeek 配置。

### 5. API 层（`backend/app.py`）

- `POST /api/settings/api-key`：{provider, api_key} → 校验 provider 合法 → `validate_api_key` 真实验证 → 加密落库 → 200 {masked}；验证失败 400 {"error": "Key 验证失败，请检查"}
- `GET /api/settings/api-key`：200 {provider, masked, last_verified_at} 或 404
- `DELETE /api/settings/api-key`：200
- 三个路由都挂 `@require_user_id` + same-origin 检查（与现有写路由一致）
- `POST /api/jobs/search` 入口新增配额门：
  1. 有 Key → 解密放入任务参数，放行
  2. 无 Key 且 `trial_searches_used < trial_limit` → 站方 Key，放行
  3. 无 Key 且超限 → 402 {"error": "试用次数已用完，请配置你的 API Key", "code": "byok_required"}
- `_run_job_search_task`：任务成功且本次走站方 Key → `increment_trial_usage`（失败/取消不计）

### 6. 前端（新版 UI；风格回迁为独立工作项）

- 设置区新增"模型 Key"卡片：provider 下拉（默认 DeepSeek 置顶 + "推荐"标）、key 输入框、"验证并保存"按钮、状态行（已配置 `sk-***ab12` · provider / 未配置）、删除按钮
- 顶部/搜索按钮附近显示试用剩余次数（无 Key 时）
- 搜索返回 402 `byok_required` → 弹引导浮层（含 DeepSeek 注册充值指引链接）

### 实现契约（测试依赖，不可偏离）

- `backend/app.py` 必须以 `from backend.key_vault import validate_api_key` 方式引入（测试 mock 目标是 `backend.app.validate_api_key`）
- `backend/key_vault.py` 不得在模块级缓存 Fernet 实例/密钥——每次调用读 `APP_ENCRYPTION_KEY`（测试用 `importlib.reload` 验证密钥轮换行为，模块级缓存会导致 reload 语义错乱）
- 解密失败（`KeyVaultError`）在搜索入口视为"无 Key"，走配额门；绝不能抛 500

### 7. 错误处理

- 任务运行中用户 Key 失效（401/403/insufficient balance）：捕获后任务标 failed，`result_json` 带 `{"code": "user_key_invalid"}`，前端文案"你的 API Key 已失效，请到设置更新"
- `APP_ENCRYPTION_KEY` 变更导致解密失败：视为无 Key（提示重新配置），不崩任务
- 日志脱敏：`task_logger` 敏感字段集已含 `api_key`；新增 `key_encrypted` 到掩码集

## 安全清单

- Key 密文落库（Fernet）；掩码回显；永不回显全文；不写入任何日志
- 验证调用失败不透传 provider 原始响应（防 key 有效性探测通道）
- `APP_ENCRYPTION_KEY` 缺失时启动 fail-fast（生产）；测试注入临时密钥
- systemd drop-in 已有 FLASK_SECRET_KEY 先例，部署时同法追加

## 测试计划（TDD，先红后绿）

`tests/test_key_vault.py`

- 加解密 roundtrip；不同明文不同密文；篡改密文解密抛 KeyVaultError
- mask_key 格式（尾 4 位；短 key 全掩；空串处理）
- 缺 APP_ENCRYPTION_KEY 抛错（fail-fast）
- validate_api_key：mock requests——200 通过 / 401 拒 / 超时拒 / 网络异常拒；三家 URL 与 header 正确

`tests/test_state_store_byok.py`

- set/get/delete roundtrip；UPSERT 覆盖（换 provider）
- 外键级联：删用户连带删 key
- trial：初始 0；increment 递增；老库迁移补列（复用现有迁移测试模式）

`tests/test_factory_key_override.py`

- create_pure_client(api_key=...) → client.api_key 为传入值
- 不传 → 回落 env（monkeypatch 验证）
- 两个实例不同 key 互不污染（并发安全的最小闭环）

`tests/test_app_byok.py`（复用 test_app_integration fixture 模式）

- POST：合法 key（mock validate 通过）→ 200 + 掩码；验证失败 → 400；provider 非法 → 400；未登录 → 401
- GET：未配置 404；已配置回掩码不含全文
- DELETE：删除后 GET 404
- 配额门：无 key 用满 3 次 → 第 4 次搜索 402 code=byok_required；有 key 不受限；任务失败不消耗次数（mock 任务失败路径）
- increment 只在站方 key 成功任务后发生

## 工作量

3-4 天：测试 0.5 天 → key_vault + store 0.5 天 → 透传链 1 天 → API+配额 0.5 天 → 前端 0.5 天 → 两轮 Codex review + 修复 0.5-1 天

---

# 阶段 Q：QR 登录云端透传（云端化首要阻塞）

**状态：** 计划（2026-07-18 追加）
**问题：** Chrome 在服务端以可见模式跑在 xvfb 虚拟显示器上，云端用户看不到浏览器窗口。`_ensure_logged_in()`（`crawler/real_playwright_spider.py:788`）跳到登录页后死等 300 秒人肉扫码——云端永远等不到，任务超时、会话过期后信息抓不全。

**方案：** 爬虫截取登录页二维码图 → base64 → 回调 → SocketIO 推到用户浏览器 → 用户手机扫网页上显示的码 → 爬虫轮询检测登录成功 → 任务继续。**改 `_ensure_logged_in` 一处即覆盖两个触发场景**（首次启动登录 + 会话过期自愈 `_recover_expired_session`，都调它）。

## Q1. 状态机（7 态）

```
INIT → QR_READY → SCANNED → LOGGED_IN          （主路径）
         ↑  ↓
       QR_EXPIRED（Boss 二维码 ~2min 过期，自动重截 → 回 QR_READY）
QR_CAPTURE_FAILED（登录页找不到二维码元素 → 任务 failed）
LOGIN_TIMEOUT（等待超 180s → 任务 failed）
```

- SCANNED：Boss 登录页扫码后出现"已扫描，请在手机上确认"overlay，检测到即推送（用户体验反馈，检测不到不阻塞主路径）
- LOGGED_IN：URL 出现 `/web/geek/`（复用现有 `_is_logged_in_by_url`）

## Q2. 回调通道（爬虫 → 后端 → 前端）

- `unified_search_jobs(..., qr_callback=None)` → `SearchParams.qr_callback` → `RealPlaywrightBossSpider(qr_callback=...)`（模式同已有 `profile_dir` 透传链）
- 回调签名：`qr_callback(event: dict)`，event = `{"state": str, "image_b64": Optional[str], "message": str}`
- `_run_job_search_task` 构造回调：`socketio.emit("qr_update", {**event, "task_id": task_id}, to=user_id)`——沿用现有房间隔离，QR 图只进本人房间
- 回调是同步函数，爬虫 async 循环里直接调（socketio.emit 线程安全，现有 `_emit_progress` 同模式）

## Q3. `_ensure_logged_in` 改造

1. 跳登录页（现状保留，不动反爬规避逻辑）
2. 定位二维码元素（Boss 登录页 QR 容器 selector，实现时实测确定；定位失败 → 降级整页截图裁剪；再失败 → `QR_CAPTURE_FAILED`）
3. `element.screenshot()` → bytes → base64 → 回调 `QR_READY`
4. 轮询循环（间隔 3s，总窗 180s）：
   - 截图指纹（md5）变化 → 二维码刷新/过期重发 → 重推 `QR_READY`
   - 检测"已扫描"overlay → 推 `SCANNED`
   - `_is_logged_in_by_url()` → 推 `LOGGED_IN`，返回 True
5. 超时 → 推 `LOGIN_TIMEOUT` → RuntimeError（任务 failed，`result_json` 带 `{"code": "login_timeout"}`）
6. `qr_callback=None` 时行为完全回退现状（本地可见浏览器人肉扫码），不破坏本机使用

## Q4. 任务 deadline 交互

现有 5 分钟任务 deadline 会被登录等待吃掉（最坏 180s 登录 + 爬取 + AI 分析必超时）。决策：**登录完成后 deadline 重新计时**——`LOGGED_IN` 回调时任务线程更新计时起点（`_bail_if_cancelled_or_timeout` 的 `started` 参数改为可更新的引用），登录等待用独立的 180s 预算。

## Q5. 前端

- `#qr-pane` / `#qr-image` / `#qr-state` 已在新版 UI 占位，只需接线
- `socket.on("qr_update")`：QR_READY → 显示 pane + `img.src = "data:image/png;base64," + image_b64`；SCANNED → 状态文案"已扫描，请在手机确认"；LOGGED_IN → 隐藏 pane、恢复进度条；LOGIN_TIMEOUT/QR_CAPTURE_FAILED → 错误文案 + 建议重试
- 校验 event.task_id 等于当前任务，防串台

## Q6. 安全

- QR 图 base64 只 `to=user_id` 房间推送；**不落盘、不入日志**（`task_logger` 敏感字段集新增 `image_b64`）
- QR 图含登录凭据性质（扫了就登录该账号）——泄露即账号被他人绑走，房间隔离是硬要求（已有 join_room 机制）

## Q7. 测试计划（TDD）

`tests/test_qr_passthrough.py`

- 状态机：QR_READY→SCANNED→LOGGED_IN 合法序列；QR_EXPIRED 重截回 QR_READY；超时抛 RuntimeError 且推 LOGIN_TIMEOUT
- 截图指纹变化触发重推（mock page.screenshot 返回不同 bytes）
- `qr_callback=None` 回退现状路径（不截图、不推送、维持原轮询）
- 定位失败降级链：元素 → 整页 → QR_CAPTURE_FAILED

`tests/test_app_qr.py`

- `qr_update` 事件 emit 带 `to=user_id`（房间隔离，mock socketio 捕获参数）
- event 带 task_id；image_b64 不出现在 task_logger 输出（脱敏测试）
- login_timeout 任务标 failed + `result_json.code == "login_timeout"`，试用次数不扣
- deadline 重计时：登录耗时不吞噬爬取/分析预算

## Q8. 工作量与依赖

- 2-3 天；无新 pip 依赖；xvfb 可见模式保留（反检测要求），`page.screenshot` 在 xvfb 下正常工作
- 与 BYOK 无代码耦合，可并行开发；**建议实施顺序：先 QR（云端可用性阻塞）后 BYOK（商业化）**，或按 BYOK 已写好的 54 例测试先做 BYOK——由用户定

## 后续独立工作项（不在本 spec）

- UI 风格回迁：新版编辑风 → 旧版简洁卡片风（用户已选定方向）
- 互动聊天 (a) 搜前画像 + (b) 搜后筛选
- 自定义 base_url 接入
