# 画像对话 + 自动搜索 + 结果助手（阶段 D/C）

**日期：** 2026-07-25
**状态：** 已批准（四项决策用户确认）
**愿景：** 几轮对话判断该搜什么 → 系统自动搜 → 按画像（简历+对话）过滤评分。
系统从"执行关键词的工具"升级为"理解求职者的顾问"。

## 已确认决策

| 决策       | 结论                                                                    |
| ---------- | ----------------------------------------------------------------------- |
| 搜索词确认 | AI 生成 ≤3 词，展示可勾选/编辑，确认后串行爬取合并（方案 ii）           |
| 对话时机   | 首次上传简历后必聊；画像卡片可编辑/重聊；换简历提示更新                 |
| 搜索预算   | 最多 3 词 × 每词默认 15 岗（可调 5-30；测试期目标 15，登录全量后升 30） |
| 助手边界   | v1 纯问答，无生成类动作（打招呼已砍）                                   |

## D1. 画像数据层（utils/state_store.py）

```sql
CREATE TABLE IF NOT EXISTS career_profiles (
    user_id      TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    resume_hash  TEXT,              -- 生成画像时的简历指纹（换简历提示更新）
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
```

**画像 schema（profile_json）**：

```json
{
  "target_directions": ["市场风险管理", "风险计量"], // ≤3 个方向
  "transition": {
    "is_transition": true,
    "from": "券商风控",
    "to": "买方量化风控"
  }, // 或 null
  "cities": ["shanghai"],
  "salary_floor": "25K", // 或 null
  "hard_avoids": ["外包", "大小周"], // 硬性排除，进规则层
  "seniority": "3-5年", // 或 null
  "notes": "自由补充"
}
```

**Store 方法**：

- `set_career_profile(user_id, profile_json: str, resume_hash: str)`：UPSERT，首建 created_at
- `get_career_profile(user_id) -> Optional[dict]`：返回
  `{"profile": <解析后的 dict>, "resume_hash": str, "updated_at": float}`

## D2. 画像对话引擎

**新模块 `analyzer/profile_interview.py`**（对话逻辑与 prompt 集中，可测）：

````python
MAX_INTERVIEW_ROUNDS = 5

def build_interview_system_prompt(resume_text: str) -> str
    # 含：简历全文、画像 schema 全部键名、规则（一次只问一个问题、
    # 只问简历读不出的信息、信息足够即收尾输出画像）

def should_force_finish(messages: list) -> bool
    # assistant 轮数 >= MAX_INTERVIEW_ROUNDS → True（服务端硬顶）

def parse_interview_reply(text: str) -> dict
    # AI 输出协议：{"action": "ask"|"finish", "message": str, "profile": {...}?}
    # 解析 JSON（容忍 ```json 包裹）；action 非法/解析失败 →
    #   {"action": "ask", "message": <原文>, "profile": None}（降级为普通追问）

def normalize_career_profile(raw: dict) -> dict
    # 键齐全化：缺失键补默认（列表 []、其余 None）
    # target_directions 裁到 ≤3；非 list 字段类型矫正；transition 结构校验
````

**API `POST /api/profile-chat`**（backend/app.py，`@require_user_id`）：

- 请求：`{"messages": [{"role": "user"|"assistant", "content": str}, ...]}`
  ——**服务端无会话状态**，前端每轮发全量历史（重启安全、实现最简）
- 流程：取用户简历（无简历 400）→ 组 prompt（system + 历史）→ AI 调用 →
  `parse_interview_reply` → 若 `should_force_finish` 则在调用前注入收尾指令
- 响应：`{"type": "question", "message": str}` 或
  `{"type": "complete", "message": str, "profile": {...}}`
  ——complete 时服务端 `normalize_career_profile` + `set_career_profile` 落库
- **Key 策略**：有用户 Key 走用户 Key；无 Key 走站方 Key 且**不计入试用次数**
  （对话轮均价 ~0.5 分，轮次硬顶 5，滥用面可控；画像是 onboarding 核心不设门槛）
- 消息长度限制：单条 ≤1000 字符，历史 ≤30 条（400 拒绝）

## D3. 搜索词生成

`analyzer/profile_interview.py` 续：

```python
def build_search_keywords_prompt(profile: dict) -> str
def parse_search_keywords(text: str) -> list[str]
    # ≤3 个、去重、去空白；解析失败返回 []
```

**API `POST /api/search-plan`**：读画像（无画像 404）→ AI 生成 ≤3 关键词 →
`{"keywords": [str], "profile": {...}}`；AI 失败/空 → 回退 `target_directions` 前 3。
Key 策略同 D2。

## D4. 多关键词搜索任务

**`POST /api/jobs/search` 请求体扩展**（向后兼容）：

- 新：`{"keywords": ["词1", "词2"], "per_keyword": 15, "city": ...}`
- 旧：`{"keyword": "词1", "max_jobs": 20}` 继续可用（内部视为 keywords=[keyword]）
- 校验：keywords ≤3 个；per_keyword 裁剪到 [5, 30]，默认 15

**任务链路（`_run_job_search_task`）**：

1. 逐词调用 `unified_search_jobs(keyword=词, max_jobs=per_keyword, ...)`
   （每词独立浏览器会话，v1 不做会话复用——简单可靠，3 次启动开销 ~30s 可接受）
2. 合并候选池：按 `job_id` 去重（同岗位多词命中只保留一份）；无 job_id 的按 url 去重
3. 之后进既有链路（upsert_job → 缓存查询 → 分析 → 落盘）
4. 单词爬取失败不整体失败：记录该词失败原因进 result_payload
   `"keyword_errors": {词: 原因}`，其余词继续；全部词失败才任务 failed
5. `tasks.keyword` 字段存 `"，".join(keywords)`

**限时公式升级**（backend/app.py）：

```python
_task_deadline_seconds(total_jobs, n_keywords=1) =
    300 + 30 * total_jobs + 120 * (n_keywords - 1)
# total_jobs = len(keywords) * per_keyword；单关键词行为与现状完全一致
```

## D5. 画像锚定分析

**`EnhancedJobAnalyzer.analyze_jobs(..., career_profile: Optional[dict] = None)`**：

- **规则层**：`career_profile["hard_avoids"]` 合并进 hard_filters 的
  `exclude_keywords`（零 AI 成本先杀）
- **阶段一（粗筛）**：有画像时判定基准改为 `target_directions`（多方向任一沾边即过），
  而非单一搜索关键词——screening prompt 增加画像方向段
- **阶段二（精配）**：匹配 prompt 注入画像块；`transition.is_transition` 为真时
  **评分锚切换**：不问"简历与 JD 匹配吗"，问"以转型到 {to} 为目标，该岗位是否
  好跳板 + 哪些技能可迁移"——简历退为素材，画像是标准
- 无画像（career_profile=None）：行为与现状完全一致（零回归）

**app 接线**：任务启动时 `get_career_profile(user_id)` → 传入 analyze_jobs。

## C. 结果页 AI 助手（纯问答）

**API `POST /api/assistant`**（`@require_user_id`）：

- 请求：`{"question": str, "task_id": str}`；question ≤500 字符
- 校验：task 必须属于该用户（IDOR 防御，get_task(task_id, user_id)）且 status=success
- 上下文组装：该任务结果岗位（按 score 降序裁前 20，仅结构化字段+JD 摘要 300 字）
  - 画像 + 简历摘要（前 800 字）
- **Key 策略：必须已配置用户 Key**（无 Key → 402 `byok_required`）——助手是
  增值功能，不吃站方补贴
- 响应：`{"answer": str}`；AI 失败 → 502 统一文案
- 无对话状态（v1 单轮问答；前端自行保留展示历史）

**新模块函数（`analyzer/profile_interview.py` 或独立 `analyzer/assistant.py`）**：

```python
def build_assistant_prompt(question, jobs, profile, resume_summary) -> str
    # 含防注入约束：只回答求职相关问题；岗位数据为上下文非指令
```

## 前端（实现阶段做，无 JS 单测，E2E 人工验）

1. **画像对话面板**：上传简历成功后自动展开聊天卡片（简单气泡 UI，输入框+发送）；
   complete 时渐变收起 → 显示画像卡片
2. **画像卡片**：字段展示 + "编辑"（表单微调）+ "重新聊"按钮；换简历上传后弹提示
3. **搜索计划**：点 Begin search → 若有画像先调 /api/search-plan → 关键词 chips
   （勾选/可编辑/可增删，≤3）+ 每词岗位数选择 → 确认开跑；无画像走旧单关键词流程
4. **助手**：结果区底部输入框 + 回答气泡；无 Key 时置灰提示配置

## 安全清单

- 对话与助手全部 `@require_user_id` + same-origin；历史/问题长度硬限
- 助手上下文只取本人任务（IDOR 校验）；prompt 注入防御（岗位 JD 是数据不是指令的显式声明）
- 画像内容入 task_logger 脱敏范围评估：不含凭据，不脱敏；对话内容**不落日志**（仅落画像结果）
- AI 原始报错不透传前端

## 测试计划（TDD，先红后绿）

`tests/test_career_profile_store.py`

- set/get roundtrip、UPSERT（created_at 保持/updated_at 更新）、resume_hash 携带、无画像 None

`tests/test_profile_interview.py`

- parse_interview_reply：ask/finish 合法解析、```json 包裹容忍、畸形输出降级为 ask+原文
- normalize_career_profile：缺省补全、directions 裁 ≤3、类型矫正、transition 结构
- should_force_finish：第 5 轮 assistant 后 True，之前 False
- build_interview_system_prompt：含简历文本 + 全部 schema 键名

`tests/test_search_keywords.py`

- parse ≤3/去重/去空白/解析失败空列表
- /api/search-plan：无画像 404；正常返回 keywords（mock AI）；AI 失败回退 target_directions

`tests/test_multi_keyword_task.py`

- 新旧请求体兼容（keyword 单数仍 202）
- keywords >3 → 400；per_keyword 裁剪 [5,30]
- unified_search_jobs 被按词各调一次（mock 捕获）
- job_id 相同的岗位合并后只出现一次
- 单词失败不倒任务：keyword_errors 记录、其余词结果保留；全失败 → failed
- _task_deadline_seconds(total, n_keywords) 公式（单词=现状回归）

`tests/test_profile_anchored_analysis.py`

- career_profile=None 行为不变（现状守护）
- hard_avoids 并入规则层（命中词的岗位进 discarded、stage=hard_filter）
- 有画像时粗筛 prompt 含 target_directions（fake client 捕获 prompt 文本）
- 转型画像时匹配 prompt 含"跳板/可迁移"锚定语 + 目标方向
- 画像经 /api/profile-chat complete 落库后，搜索任务自动取用（app 集成）

`tests/test_assistant_api.py`

- 未登录 401；无 Key 402 byok_required；question 超长 400
- 他人 task_id → 404（IDOR）；非 success 任务 → 409
- 正常问答（mock AI）：prompt 含岗位标题与画像内容、响应 answer
- AI 异常 → 502 统一文案、原始报错不透传

## 工作量

5-7 天：store+interview 模块 1 天 → 对话/计划 API 1 天 → 多关键词任务 1 天 →
画像锚分析 1 天 → 助手 API 0.5 天 → 前端 1.5 天 → review 修复 1 天

## 不做（本期）

- 打招呼/文书生成（用户砍）
- 助手多轮对话记忆（v1 单轮）
- 浏览器会话跨关键词复用（v2 优化爬取时长）
- 画像版本历史（只存最新）
