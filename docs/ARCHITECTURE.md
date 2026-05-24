# 技术架构文档

> 反映**当前**代码现状。代码变更时同步更新本文。决策类内容见末尾「关键决策记录」（写完冻结，不回改）。

## 系统概览

单机 Web 应用：浏览器前端 ↔ Flask/SocketIO 后端 → Playwright 爬虫 → 多 AI 模型两阶段评分。无数据库，简历仅 session 内临时存储，每次搜索独立。

## 请求数据流

```
浏览器 ──WebSocket──> Flask + SocketIO (backend/app.py)
                          │  /api/jobs/search 后台任务直接编排爬取+分析，emit 实时进度
                          ▼
        UnifiedCrawlerInterface (crawler/unified_crawler_interface.py)
                          ▼
            RealPlaywrightBossSpider (crawler/real_playwright_spider.py)
              · patchright 启动真实 Chrome、持久化登录态
              · 会话失效 → settle 轮询 → 引导扫码 → 重新抓取
              · 列表提取 + 点击卡片读详情面板拿 JD
                          ▼
            EnhancedJobAnalyzer (analyzer/enhanced_job_analyzer.py)
              第一阶段：DeepSeek V4-Flash（thinking=off）类型筛选（廉价快速，过滤不相关岗位）
              第二阶段：DeepSeek V4-Flash（thinking=on）简历×JD 匹配评分（1–10 分 + 亮点/差距/总结）
                          ▼
                  按分数降序返回 → 前端卡片展示
```

## 模块职责

| 模块        | 职责                                            | 关键文件                                                                                                                                                               |
| ----------- | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/`  | Flask 入口、REST + SocketIO、搜索编排、简历会话 | `app.py`（路由 + `/api/jobs/search` 后台任务内联编排爬取与两阶段分析）                                                                                                 |
| `crawler/`  | patchright 爬取、登录/会话、HTML 提取、重试     | `real_playwright_spider.py`（核心）、`unified_crawler_interface.py`（对外 `unified_search_jobs()`）、`enhanced_extractor.py`、`session_manager.py`、`retry_handler.py` |
| `analyzer/` | 两阶段 AI 分析、多提供商客户端、prompt 模板     | `enhanced_job_analyzer.py`（`analyze_jobs()`）、`ai_client_factory.py`（工厂）、`clients/*`、`prompts/*`                                                               |
| `config/`   | 三层配置统一加载                                | `config_manager.py` + `secrets.env` / `app_config.yaml` / `user_preferences.yaml`                                                                                      |

**新增 AI 提供商**：`analyzer/clients/` 加客户端（继承 `base_client.py`）→ `AIClientFactory` 加分支 → `app_config.yaml` 注册。

## 环境注意事项

- 用 conda `boss_dev`（python 3.12）。**macOS 26 须 playwright≥1.60**（旧版 chromium 启动即 SIGSEGV）。
- 浏览器用 `patchright install chrome`（反检测，见 ADR-1）。
- 登录态持久化在 Chrome profile：`~/Library/Application Support/boss_automation/browser_profile/boss_zhipin/`。
  `app_config.yaml: crawler.browser.use_persistent_context: true` 必须保持启用（ADR-5），否则每次扫码。
- `tests/` 不上 GitHub（`.gitignore`）；本地保留供 TDD。

---

## 关键决策记录（ADR）

> 格式：背景 / 决策 / 备选 / 后果。**写完不改**；决策若反转，新增一条并标注取代关系。决策较多后再拆到 `docs/decisions/`。

### ADR-1：用 patchright 替代 playwright + playwright_stealth（2026-05-22）

- **背景**：登录页被 Boss 反爬关进重定向死循环（`/web/geek/jobs?_security_check ↔ /web/user/ ↔ security.html?code=37`，~2 次/秒），二维码一闪即逝，无法扫码。
- **决策**：改用 **patchright**（Playwright 反检测分支，驱动层不发 `Runtime.enable` CDP 命令）。启动用干净配置 `channel="chrome", no_viewport=True`，**删除所有自定义 args / user_agent / stealth**。
- **备选**：① 继续调 `playwright_stealth`——**已验证无效**（只补 navigator 表面层，反爬测的是 CDP 协议层）；② rebrowser-patches——少维护；③ curl_cffi——仅 HTTP，拿不到登录态。
- **后果**：需 `patchright install chrome`；其它模块仍用 `playwright.async_api` 的类型提示（运行时兼容）。实测登录稳定、可扫码、端到端跑通。

### ADR-2：详情页 JD 用「点击卡片读面板」而非 goto 详情 URL（2026-05-22）

- **背景**：`/web/geek/jobs` 是左列表+右面板 SPA。直接 `page.goto('/job_detail/<id>')` 常被反爬静默弹回列表页（goto 不报错但 URL 没变），导致 JD 抓不到。
- **决策**：点击列表卡片（`a.job-name[href*=<id>]`）让 SPA 就地在 `.job-detail-box` 面板加载详情，再从面板提取。JD 选择器 `.job-detail-box .desc`，公司 `.boss-info-attr`。
- **后果**：用 `inner_text()`（非 innerHTML）提取——自动剔除 Boss 注入的隐藏水印 span（直聘/kanzhun），得干净文本。

### ADR-3：会话恢复用 settle 轮询而非单点检测（2026-05-22）

- **背景**：反爬重定向是异步的，导航后页面数秒内在多个 URL 间切换；"某一瞬间用 URL 判断登录态"是移动靶，会漏判（出现过恢复不触发、或过早判定登录又被弹回）。
- **决策**：`_classify_page_state()`（按路径判 login/security/blank/results）+ `_wait_until_page_settled()`（把 security/blank 当"继续等"，稳定到确定态再决策）。提取为空后才触发恢复；登录后**不主动 goto**（靠 SPA 按 fromUrl 自落结果页）。

### ADR-4：两阶段评分（廉价筛选 + 主力匹配）

- **背景**：50–100 个岗位全量送昂贵模型成本不现实。
- **决策**：第一阶段用廉价快速模型做类型筛选（不比对简历，只判岗位类型是否相关），过滤后通常剩 30–60 个，再送主力模型做简历×JD 深度匹配评分。
- **2026-05-23 更新**：最初选 GLM+Claude；后切到 DeepSeek V4-Flash 单一 provider 跑两阶段——同一模型用 thinking 开关切换"快/省"和"细致打分"，简化依赖+省 ~25× 成本。
- **2026-05-24 更新**：实测「全部 jobs 解析失败 + score=0」根因为 thinking 模式 `max_tokens` 默认 1000 被 reasoning 吃光导致 content JSON 截断。决议：Stage 2 显式传 `max_tokens=6000`；解析失败时把 raw response 前 200 字落 warning 日志便于诊断。详见 `~/.claude/knowledge/llm-thinking-mode-tokens.md`。
- **后果**：显著降本；筛选模型可经 `app_config.yaml` 配置（不再硬编码）；thinking 截断诊断闭环。

### ADR-5：会话恢复登录后必校验 query 匹配（2026-05-24，取代 ADR-3 末尾「不主动 goto」规则）

- **背景**：ADR-3 决策「登录后不主动 goto，靠 SPA 按 fromUrl 自落结果页」对反爬死循环时代成立，但反爬有时把 fromUrl 落到错关键词页或上次搜索残留页（实测搜「AI算法工程师」拿到「ai产品经理」一页结果）。原代码只判 `'/web/geek/jobs' in url` 就跳过重导航，导致前端展示错关键词结果。
- **决策**：新增 `_url_matches_search_target(current_url, search_url)` 静态工具，同时校验：① host 一致；② path 严格等于 `/web/geek/jobs`（去尾斜杠归一化，避免 `/web/geek/jobs-old` 类后缀误判）；③ query 参数 `query` 与 `city` 都匹配。`_recover_session_if_needed` 的两条恢复路径（`settled='results'` 与「登录后」）都调用此工具，不匹配时强制 `_navigate_to_search_page(search_url)`。
- **备选**：①「登录后总是重 goto」——风险高，可能触发反爬安全校验把页面弹回登录页（ADR-1 时代实证）；② 改 `_ensure_search_page_ready` 加 query 校验——风险更高，可能死循环。
- **后果**：覆盖了 ADR-1 时代「不敢动」的恢复路径；持久化 profile（ADR-1 + `use_persistent_context: true`）+ 此校验形成双重保障——cookie 持久 + 落点矫正。

### ADR-6：详情面板薪资抓取与格式校验（2026-05-24）

- **背景**：列表卡片在反爬/未登录态常拿不到薪资，统一兜底为「薪资面议」。原 `_extract_job_detail_page` 只抓 JD/公司/地址不抓薪资，所以前端永远展示「薪资面议」即便面板上 Boss 真给了。
- **决策**：新增 `_extract_panel_salary()`，按候选选择器 `.job-detail-box .salary` → `.job-detail-box .job-banner .salary` 顺序尝试；每次命中用正则 `\d.*[Kk万薪元]` 校验格式后才采纳，避免命中 tip/wrapper/说明节点把垃圾文本写进 `result['salary']` 反而覆盖列表卡片真实值；非空 `salary` 才写入返回 dict，调用方按 `{**job, **details}` 合并覆盖列表兜底。
- **备选**：① 用宽选择器 `[class*="salary"]`——Codex review 指出会误命中「薪资范围说明」类节点，反而比保留兜底更坏；② 在 `enhanced_extractor.py` 列表阶段重抓——Boss 列表反爬常隐藏薪资，重抓也拿不到。
- **后果**：薪资抓取脆弱性收敛到「面板真给但 DOM 类名变体」一种场景；列表层兜底保留作为 fallback。
