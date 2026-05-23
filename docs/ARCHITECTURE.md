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
              第一阶段：GLM 类型筛选（廉价快速，过滤不相关岗位）
              第二阶段：主力模型简历×JD 匹配评分（1–10 分 + 亮点/差距/总结）
                          ▼
                  按分数降序返回 → 前端卡片展示
```

## 模块职责

| 模块        | 职责                                            | 关键文件                                                                                                                                                               |
| ----------- | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/`  | Flask 入口、REST + SocketIO、搜索编排、简历会话 | `app.py`（路由 + `/api/jobs/search` 后台任务内联编排爬取与两阶段分析）                                                                                                 |
| `crawler/`  | Playwright 爬取、登录/会话、HTML 提取、重试     | `real_playwright_spider.py`（核心）、`unified_crawler_interface.py`（对外 `unified_search_jobs()`）、`enhanced_extractor.py`、`session_manager.py`、`retry_handler.py` |
| `analyzer/` | 两阶段 AI 分析、多提供商客户端、prompt 模板     | `enhanced_job_analyzer.py`（`analyze_jobs()`）、`ai_client_factory.py`（工厂）、`clients/*`、`prompts/*`                                                               |
| `config/`   | 三层配置统一加载                                | `config_manager.py` + `secrets.env` / `app_config.yaml` / `user_preferences.yaml`                                                                                      |

**新增 AI 提供商**：`analyzer/clients/` 加客户端（继承 `base_client.py`）→ `AIClientFactory` 加分支 → `app_config.yaml` 注册。

## 环境注意事项

- 用 conda `boss_dev`（python 3.12）。**macOS 26 须 playwright≥1.60**（旧版 chromium 启动即 SIGSEGV）。
- 浏览器用 `patchright install chrome`（反检测，见决策 1）。
- 登录态在持久化 Chrome profile：`~/Library/Application Support/boss_automation/browser_profile/`。

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

### ADR-4：两阶段评分（GLM 筛选 + 主力模型匹配）（feature 重构）

- **背景**：50–100 个岗位全量送昂贵模型成本不现实。
- **决策**：第一阶段用廉价快速的 GLM 做类型筛选（不比对简历，只判岗位类型是否相关），过滤后通常剩 30–60 个，再送主力模型（Claude/Gemini/GPT）做简历×JD 深度匹配评分。
- **后果**：显著降本；筛选模型可经 `app_config.yaml` 配置（不再硬编码）。
