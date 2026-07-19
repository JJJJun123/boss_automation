# 批量分析管线升级（阶段 P）— discard 可见化 + Machine Summary + 岗位落库

**日期：** 2026-07-19
**状态：** 已批准（借鉴 career-ops 批量漏斗，用户逐条确认）
**范围确认**：深度评估（单岗 A-G 作战包）明确不做。

## 背景与决策

career-ops 批量漏斗的三条精髓映射到我们：

| 决策           | 结论                                                                         |
| -------------- | ---------------------------------------------------------------------------- |
| 初筛要不要打分 | 不打分（现状已是二分类，维持）；但被筛掉的必须可见                           |
| 阶段二产物     | 自由 JSON → Machine Summary 结构化 schema                                    |
| 岗位数据       | 落库；事实（JD）全局共享缓存，判断（评分）按 user+简历缓存；搜索列表永远实时 |

## P1. Discard 可见化

**现状**：阶段 0（hard_filter，已返回 `dropped`）与阶段 1（类型二分类）踢掉的岗位无声消失。

**实现契约**：

- `EnhancedJobAnalyzer.analyze_jobs()` 执行后，实例属性 `self.discarded_jobs: List[dict]` 可读，
  每项：`{"title": str, "company": str, "stage": "hard_filter"|"screening", "reason": str}`
  - hard_filter：reason 来自规则命中说明（apply_hard_filters 已产出 dropped，转换并入）
  - screening：reason 固定格式 `"类型不符：<AI 一句话判定>"` 或规则回退时的规则说明
- 每次 `analyze_jobs()` 调用开头重置该属性（不跨任务累积）
- `_run_job_search_task` 的 `result_payload` 新增：
  `"discarded": [...]`（同上结构）、`"discarded_count": int`
- 前端：结果区加折叠块"已过滤 N 个岗位 ▸"，展开逐条显示 标题 · 公司 · 理由（实现时做，无 JS 单测）

## P2. Machine Summary（阶段二结构化产物）

**新模块 `analyzer/machine_summary.py`**：

```python
VALID_DECISIONS = {"apply", "consider", "research", "skip"}
VALID_DISCARD_REASONS = {
    "salary_too_low", "seniority_mismatch", "domain_mismatch",
    "location_mismatch", "company_type_mismatch", "workload_mismatch", "other",
}

def normalize_machine_summary(raw: dict, job: dict) -> dict:
    """归一化 AI 输出的 machine summary 字段
    - final_decision 不在枚举内 → "consider"（并 warning 日志）
    - discard_reasons 未知 slug → 替换为 "other"（保留合法项）
    - hard_stops / soft_gaps 缺失或非 list → []
    - advertised_comp 缺失/空 → 回退 job.get("salary") 原文（再缺 → ""）
    返回：仅含上述 5 个键的 dict
    """
```

**阶段二 prompt**（`analyzer/prompts/job_match_prompts.py`）：输出 JSON 增加字段——
`final_decision`（四枚举，含中文释义映射说明）、`hard_stops`（硬伤列表，不可缓解才算）、
`soft_gaps`（软伤列表，可解释/可补）、`discard_reasons`（仅当 decision=skip，从固定 slug 枚举选）、
`advertised_comp`（逐字抄 JD/列表页薪资，禁止改写换算）。模板文本必须包含全部 5 个键名
（test_prompts 风格校验）。

**解析整合**：阶段二解析后，岗位 dict 并入归一化的 5 个字段（经 `normalize_machine_summary`）。
旧字段（score / reason / 亮点 / 不足）全部保留——前端与既有测试零破坏。

**前端**（实现时）：卡片显示决策徽标（投/考虑/再研究/跳过）与 hard_stops 首条；
"全部岗位"视图可按决策分组。

## P3. 岗位落库 + 双层缓存

### 表结构（utils/state_store.py）

```sql
CREATE TABLE IF NOT EXISTS jobs (
    job_id      TEXT PRIMARY KEY,   -- Boss URL 内全局唯一 ID（spider._job_id_from_url 已有）
    title       TEXT, company TEXT, salary TEXT, city TEXT,
    url         TEXT, jd TEXT,
    first_seen  REAL NOT NULL, last_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS job_analyses (
    user_id     TEXT NOT NULL,
    job_id      TEXT NOT NULL,
    resume_hash TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    created_at  REAL NOT NULL,
    PRIMARY KEY (user_id, job_id, resume_hash)
);
```

### Store 方法契约

- `resume_fingerprint(resume_text: str) -> str`：模块级函数，sha256 hex；同文本恒同值
- `upsert_job(job: dict)`：以 `job_id` 为键 UPSERT；首见写 first_seen，每次更新 last_seen 与字段；
  无 job_id 的岗位静默跳过（不抛）
- `get_fresh_job(job_id, max_age_seconds) -> Optional[dict]`：last_seen 距今 ≤ 阈值才返回
- `set_cached_analysis(user_id, job_id, resume_hash, analysis_json)`：UPSERT
- `get_cached_analysis(user_id, job_id, resume_hash) -> Optional[dict]`（解析 JSON 返回）；
  user/job/resume_hash 任一不同 → None（简历一改缓存自动失效）

### 任务链路（backend/app.py `_run_job_search_task`）

1. **爬取前**：无候选 job_id（列表实时爬），不查库
2. **爬取后**：全部岗位 `upsert_job`
3. **分析前**：对每个岗位算 `job_id`（复用 `_job_id_from_url`）+ 当前简历指纹查
   `get_cached_analysis` → 命中的岗位**不送 analyzer**，直接用缓存分析结果；
   未命中的送 `analyze_jobs`
4. **分析后**：新分析的岗位逐个 `set_cached_analysis`（含 Machine Summary 字段的完整岗位 dict）
5. 合并 缓存命中 + 新分析 → 按 score 降序 → result_payload（新增 `"cache_hits": int` 供前端提示
   "N 个岗位复用历史分析"）

### 详情页抓取跳过（爬虫层）

- `unified_search_jobs(..., job_detail_cache: Optional[dict] = None)` → SearchParams →
  `RealPlaywrightBossSpider(job_detail_cache=...)`（模式同 profile_dir/qr_callback 透传链）
- cache 形如 `{job_id: {"jd": ..., "salary": ..., ...}}`；`_fetch_job_details` 对命中且字段完整的
  岗位跳过详情页点击，直接回填缓存字段
- app 构造 cache：列表爬完后（早期快照含 URL）… **v1 简化**：app 在任务开始前无法预知 job_id，
  故 v1 由 spider 内部查询回调 `detail_cache_lookup: Callable[[str], Optional[dict]]`
  （app 传 `lambda jid: store.get_fresh_job(jid, 48*3600)`），spider 在点击每个详情页前调用；
  线程安全：SQLite 连接在爬虫线程内新建（store._connect 每调用新连接，安全）
- 新鲜度阈值常量 `JOB_DETAIL_FRESH_SECONDS = 48 * 3600`（backend/app.py）

## 测试计划（TDD，先红后绿）

`tests/test_discard_visibility.py`

- hard_filter 踢掉 → discarded_jobs 含 stage=hard_filter + reason
- 阶段一判"否" → stage=screening 条目
- 连续两次 analyze_jobs → 第二次不含第一次的条目（重置）
- app：result_json 含 discarded / discarded_count（mock analyzer 注入属性）

`tests/test_machine_summary.py`

- normalize：合法透传；decision 非法→consider；未知 slug→other（合法项保留）；
  列表字段缺省 []；advertised_comp 回退 job.salary
- prompt 模板含 5 个键名
- 集成：fake AI 返回完整 JSON → analyze_jobs 产出岗位 dict 含 5 字段且归一化生效

`tests/test_jobs_store.py`

- upsert 首见/再见（first_seen 不变、last_seen 更新、字段覆盖）
- get_fresh_job 新鲜命中 / 过期 None / 不存在 None
- 无 job_id upsert 不抛
- 分析缓存 roundtrip；user / job / resume_hash 任一不同 → miss
- resume_fingerprint 确定性 + 不同文本不同值

`tests/test_analysis_cache_flow.py`（复用 test_app_byok fixture 模式）

- 首次搜索：任务成功后 jobs 表有记录、job_analyses 有记录
- 预置缓存后再搜同岗位：analyzer 收到的列表不含命中岗位；结果含缓存岗位；cache_hits 正确
- 简历变更（不同指纹）后：缓存未命中，岗位重新送 analyzer
- unified_search_jobs 收到可调用的 detail_cache_lookup kwarg

## 工作量

2-3 天：store + machine_summary 0.5 天 → analyzer 改造 0.5 天 → app 链路 0.5 天 →
爬虫跳过 + 前端折叠区/徽标 0.5 天 → review 修复 0.5 天

## 不做（本期）

- 单岗深度评估（A-G 作战包）——用户明确砍掉
- 搜索列表缓存（列表永远实时爬）
- 跨用户分析共享（评分永远按本人简历算）
- NL 偏好写回 user_preferences（下一批）
