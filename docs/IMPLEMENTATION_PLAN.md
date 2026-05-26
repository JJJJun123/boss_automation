# 实现计划 — 云端多用户 SaaS 改造

> 对应 `design.md`。本期改造完成后此文档作废，相关决策吸收进 `ARCHITECTURE.md` 的 ADR-7~。

## 改造范围对照

| design.md 项 | 现状                               | 改造内容                                                                           |
| ------------ | ---------------------------------- | ---------------------------------------------------------------------------------- |
| F1 简历上传  | 全局 `_current_resume` + 调试落盘  | SQLite 按 `user_id` TTL 24h 存储；删除 `debug_resume_text.txt` 落盘；拒绝 TXT 格式 |
| F2 求职意向  | 无                                 | 新增前端表单：目标方向 + Hard filters + Soft preferences；搜索前必须完成           |
| F3 QR 透传   | 无（依赖 macOS 扫码）              | 新增 7 状态登录流程机，QR 截图 → WebSocket 推前端                                  |
| F4 岗位搜索  | 默认 14 上限无明确                 | 默认 30 上限 50；5 分钟超时；只暴露状态不暴露失败原因                              |
| F5 两阶段 AI | 单一 prompt                        | 总模板 + 类型权重表 + few-shot + JSON schema 校验（6 类岗位）                      |
| F6 结果展示  | 卡片展示 OK；亮点/差距藏在展开面板 | 卡片默认显示评分 + 亮点 + 差距 + summary；按 task_id 刷新恢复                      |
| 隔离与并发   | 单 profile 全局共享                | per-user UUID profile + 互斥锁 + 全局并发 ≤ 3；任务 deadline + finally 释放锁      |
| 限流         | 无                                 | SQLite 持久化：单用户每月 10 次搜索 / 单次 50 岗位 / 全局日预算 ¥4                 |
| 日志记录     | journald 单线 + debug 落盘泄漏     | journald + JSONL 双写 + 4 级粒度 + 简历正文不落盘                                  |
| 用户身份     | 无                                 | 邀请码 / 一次性 token URL → user_id（无密码无邮箱，防枚举）                        |
| WebSocket    | 全局广播（多用户串数据）           | task-scoped Socket.IO room + 所有请求校验 task 属于当前 user                       |
| 状态层       | 进程内 dict（重启全丢）            | **SQLite + WAL + TTL**：users / profiles / tasks / rate_limits / quotas            |
| 生产安全基线 | 缺                                 | SECRET_KEY 环境变量 / CORS 白名单 / Cookie 安全标志 / 错误脱敏 / 防枚举            |

---

## 实现顺序

按依赖关系排序。每项独立可测、可回滚。**总预估 100-140 工时 ≈ 13-17 工作日**（含联调测试与压测）。

### 阶段 0：基础设施与安全基线（先行）

| #   | 任务                                                                 | 预估 | 依赖 |
| --- | -------------------------------------------------------------------- | ---- | ---- |
| 0.1 | **SQLite 状态层初始化**（schema、migration、TTL worker）             | 6h   | 无   |
| 0.2 | 引入 `user_id` 模型 + 邀请码登录（URL `?invite=` → Cookie）          | 4h   | 0.1  |
| 0.3 | **删除 `debug_resume_text.txt` 落盘代码**（已完成）                  | -    | -    |
| 0.4 | 生产安全基线：SECRET_KEY env、CORS 白名单、Cookie 安全标志、错误脱敏 | 5h   | 0.2  |
| 0.5 | 邀请码防枚举（连续失败 IP 临时黑名单）                               | 3h   | 0.2  |
| 0.6 | 日志双写基础设施（JSONL + journald，敏感字段脱敏）                   | 4h   | 无   |
| 0.7 | 拒绝 TXT 简历上传（前后端 MIME + 扩展名双校验，MAX_CONTENT_LENGTH）  | 2h   | 无   |

### 阶段 1：隔离 + 并发 + WS 安全

| #   | 任务                                                                              | 预估 | 依赖     |
| --- | --------------------------------------------------------------------------------- | ---- | -------- |
| 1.1 | 简历存储改造（`user_id` 隔离 + SQLite TTL）                                       | 4h   | 0.1, 0.2 |
| 1.2 | UUID profile 目录 + per-profile 互斥锁（dict + threading.Lock）                   | 5h   | 0.1, 0.2 |
| 1.3 | 全局并发队列（信号量限 3）                                                        | 3h   | 1.2      |
| 1.4 | **任务 deadline（5 分钟）+ cancel + partial result + finally 释放锁**             | 6h   | 1.2, 1.3 |
| 1.5 | **WebSocket task-scoped Socket.IO room + 所有事件校验 task 归属用户**             | 5h   | 0.2      |
| 1.6 | 任务结果 SQLite 持久化 24h + 按 task_id 刷新页面恢复                              | 3h   | 0.1      |
| 1.7 | **F2 求职意向表单**（目标方向 + Hard filters + Soft preferences），搜索前必须完成 | 5h   | 0.2      |
| 1.8 | Hard filters 后端过滤（爬虫后、AI 前），节省 API 成本                             | 4h   | 1.7      |

### 阶段 2：QR 透传 + 7 状态流程机

| #   | 任务                                                                                                                           | 预估 | 依赖     |
| --- | ------------------------------------------------------------------------------------------------------------------------------ | ---- | -------- |
| 2.1 | Chrome 登录页 QR 区域元素截图                                                                                                  | 3h   | 1.2      |
| 2.2 | WebSocket 推 QR base64 到前端（task room 内）                                                                                  | 2h   | 2.1, 1.5 |
| 2.3 | **7 状态登录流程机**（qr_ready / qr_expired / login_pending / security_check / login_success / login_failed / user_cancelled） | 8h   | 2.1      |
| 2.4 | "删除 Boss 登录态" 按钮 + 后端清 profile                                                                                       | 2h   | 1.2      |
| 2.5 | profile 30 天 last_access 自动清理 worker                                                                                      | 3h   | 0.1      |

### 阶段 3：AI 评分优化 + 成本监控（成本监控前置）

| #   | 任务                                                                         | 预估 | 依赖 |
| --- | ---------------------------------------------------------------------------- | ---- | ---- |
| 3.1 | **DeepSeek token usage accounting**（每次调用记入 SQLite quotas 表）         | 3h   | 0.1  |
| 3.2 | 全局日 API 预算监控 + 80% 预警（journald warning + admin 状态页）+ 100% 拒绝 | 4h   | 3.1  |
| 3.3 | 单用户月搜索次数限流（SQLite rate_limits 表）                                | 3h   | 0.1  |
| 3.4 | **第一阶段 prompt 加岗位类型分类输出 + JSON schema 校验**（6 类岗位枚举）    | 4h   | 无   |
| 3.5 | 第二阶段总 prompt + 类型权重表（避免维护 6 套独立 prompt 模板）              | 5h   | 3.4  |
| 3.6 | Few-shot 锚定（创始人挑 4-6 个示例 + 另外 10 个 holdout 验收集，防过拟合）   | 4h   | 3.5  |
| 3.7 | Soft preferences 注入 prompt                                                 | 1h   | 3.5  |

### 阶段 4：日志细化 + 监控完善

| #   | 任务                                                           | 预估 | 依赖 |
| --- | -------------------------------------------------------------- | ---- | ---- |
| 4.1 | 任务级 JSONL 输出（task_id / 耗时 / 关键词）                   | 2h   | 0.6  |
| 4.2 | 阶段级耗时 + token 用量落 JSONL                                | 2h   | 0.6  |
| 4.3 | 评分级 prompt 摘要 + score 落 JSONL（不含原文）                | 3h   | 3.5  |
| 4.4 | 错误日志（堆栈 + Boss 反爬上下文 + AI raw response 前 200 字） | 2h   | 0.6  |
| 4.5 | Admin 状态页（当日成本 / 活跃 task / 内存使用 / 失败率）       | 4h   | 4.1  |

### 阶段 5：压测 + 上线手册

| #   | 任务                                                                        | 预估 | 依赖 |
| --- | --------------------------------------------------------------------------- | ---- | ---- |
| 5.1 | **生产同规格压测**：2-3 并发用户 × 50 岗位，记 RSS / swap / p95 / 失败率    | 4h   | 全部 |
| 5.2 | Boss 反爬监控：搜索失败率 > 30% 告警；VPS IP 切换预案                       | 2h   | 4.5  |
| 5.3 | **首个用户运行手册**（部署/邀请码生成/日志查看/故障重启/成本查看/回滚步骤） | 3h   | 全部 |
| 5.4 | 一键部署脚本 `deploy.sh`（git pull + restart + smoke test）                 | 2h   | 全部 |

---

## 关键技术决策

### TD-1：邀请码即 user_id（无密码无邮箱）

- 形态：URL `?invite=<8字符随机>`，首次访问写 Cookie 记 `user_id = sha256(invite)[:16]`
- 邀请码持久化到 SQLite `invites` 表（status: unused / used / revoked）
- 防枚举：同 IP 连续 5 次失败邀请码 → IP 临时黑名单 10 分钟
- Cookie 标志：`Secure + HttpOnly + SameSite=Lax`

### TD-2：SQLite + WAL 作为状态层（替代进程内 dict）

- 文件：`data/state.db`，启动时 `PRAGMA journal_mode=WAL`
- 5 张表：`users` / `profiles`（user_id→uuid + last_access）/ `tasks`（含 status / result_json / expires_at）/ `rate_limits`（user_id + month + count）/ `quotas`（date + tokens_used + cost_cny）+ `invites`
- TTL worker：每小时跑一次清过期 task；每天 0:00 清过期简历 + 旧月 rate_limits
- 备份：每周 cron `cp data/state.db data/backups/state-$(date +%F).db`
- 不引入 Redis（除非并发 > 5 或多 worker 部署需要）

### TD-3：WebSocket 隔离用 Socket.IO room

- 每个 task_id 创建独立 room；只有任务所属 user 加入该 room
- 所有 WS 事件携带 task_id；后端校验 `task.user_id == request.user_id`
- 不再 `socketio.emit(broadcast=True)`

### TD-4：QR 截图方式

- 用 patchright `page.locator('.qr-img-box img').screenshot()` 直接截 QR 区域元素
- 不截全屏；Boss 登录页 DOM 结构稳定（已验证）
- 备份方案：找不到选择器时截整个登录区域，附 DOM 选择器漂移告警

### TD-5：per-profile 互斥锁

- Python `threading.Lock`（同进程内）；用 dict `{uuid: Lock}` 按需创建
- 锁通过 `with` 语句自动释放，任务超时也走 `finally` 路径释放
- gunicorn 多 worker 部署时改用 `filelock` 库（文件锁跨进程）；本期单 worker，threading.Lock 足够

### TD-6：AI prompt 策略 — 总模板 + 类型权重表

- 不维护 6 套独立 prompt（漂移成本高）
- 一份总模板 + 一张类型权重表（算法岗：技术栈 40% + 项目 30% + 行业 10% + 年限 20%；销售岗：行业 40% + KPI 30% + 客户网络 20% + 学历 10% ...）
- 第一阶段输出 JSON schema：`{relevant: bool, job_type: enum, reason: str, confidence: float}` 注入第二阶段
- 第二阶段输出 JSON schema：`{score: int 1-10, match_highlights: [str], gaps: [str], summary: str}` + schema 校验，解析失败走 fallback 提示

### TD-7：成本监控前置（不放到日志阶段）

- token usage accounting 在阶段 3 启动 AI 改造**之前**完成
- 每次 DeepSeek 调用记 `response.usage.total_tokens` + 单价 → SQLite `quotas` 表
- 80% 预警 = journald warning + 写 `data/budget_alert.flag` 文件 + admin 状态页醒目显示
- 100% 拒绝 = 新任务直接返回限流错误，已运行任务不强杀

### TD-8：任务 deadline + 资源回收

- 任务包装在 `asyncio.wait_for(coro, timeout=300)` 内
- `try/finally` 确保 profile 锁 + 全局信号量 + WS room 都被释放
- 部分结果通过 checkpoint 写入 SQLite tasks 表，超时时返回已抓到的
- 用户主动取消通过 `task.cancel_event.set()` 触发清理流程

---

## TDD 测试覆盖计划

测试代码进 git（`.gitignore` 只忽略 fixtures、screenshots、真实简历、运行产物）。

| 阶段 | 关键测试                                                                                                                       |
| ---- | ------------------------------------------------------------------------------------------------------------------------------ |
| 0.1  | SQLite schema 初始化幂等；TTL worker 真的清过期数据                                                                            |
| 0.2  | 邀请码生成 + user_id 派生；无效邀请码拒绝；已用过的邀请码不能复用                                                              |
| 0.4  | SECRET_KEY 未设环境变量时启动失败（fail-fast）；CORS 拒绝非白名单 origin；Cookie 校验有 3 个安全标志                           |
| 0.5  | 连续 5 次错误邀请码 → 第 6 次 IP 被拒                                                                                          |
| 0.6  | JSONL 输出格式 jq 可解析；敏感字段（简历正文 / Boss cookie）不出现；hash + 长度有                                              |
| 0.7  | 上传 TXT 拒绝；上传 6MB PDF 拒绝；MIME `application/x-msdos-program` 但扩展名 `.pdf` 拒绝                                      |
| 1.1  | 两个 user_id 简历完全隔离；TTL 24h 后自动清；删除简历接口立即清                                                                |
| 1.2  | 同 UUID 两个 task 串行；不同 UUID 并行；锁在异常时也被释放                                                                     |
| 1.3  | 全局信号量限 3：第 4 个任务进队列等待                                                                                          |
| 1.4  | 5 分钟超时触发 task cancel；profile 锁被释放；信号量被释放；partial result 落库                                                |
| 1.5  | 用户 A 不能收到用户 B 的 task 进度事件；伪造 task_id 攻击被拒                                                                  |
| 1.6  | 任务跑完后 24h 内刷新页面能拿到结果；25h 后清掉                                                                                |
| 1.7  | F2 未填写时搜索请求被拒                                                                                                        |
| 1.8  | Hard filter 每项 3 用例（命中/边界/不确定）：薪资门槛、年限、外包、培训、猎头、销售岗别名、学历                                |
| 2.1  | Mock Boss 登录页 DOM → 截图返回非空 PNG；选择器漂移走 fallback 截图                                                            |
| 2.3  | 7 状态全覆盖：qr_ready → expired → 重生；扫码后 security_check 路径；user_cancelled 关 Chrome 但保留 cookie；login_failed 重试 |
| 3.1  | DeepSeek 调用后 SQLite quotas 表有记录；token 数与 response.usage 一致                                                         |
| 3.2  | 日预算到 80% 触发预警（写 flag + journald）；到 100% 新任务被拒                                                                |
| 3.3  | 单用户跑第 11 次搜索 → 限流错误返回                                                                                            |
| 3.4  | 第一阶段输出符合 schema；非枚举的 job_type 触发 schema 校验失败                                                                |
| 3.5  | 算法岗 vs 销售岗的评分维度权重明显不同（mock 同样输入，权重表差异导致结果差异）                                                |
| 3.6  | 4-6 few-shot 锚定后，10 个 holdout 评分与人工判断吻合度 ≥ 70%                                                                  |
| 4.5  | Admin 页能正确显示当日 cost、活跃 task 数、失败率                                                                              |
| 5.1  | 2-3 并发用户 × 50 岗位完整跑：内存 < 80%；p95 < 5 分钟；OOM 后服务自启恢复                                                     |

---

## 风险 + 缓解

| 风险                                               | 优先级 | 缓解                                                                         |
| -------------------------------------------------- | ------ | ---------------------------------------------------------------------------- |
| Boss 反爬识别 Vultr 东京 IP 段批量拉黑             | P0     | 监控搜索失败率；> 30% 时切换 VPS IP（Vultr 销毁重建 $1）；提前买 2 个备用 IP |
| **Boss 账号封禁责任**（用户账号被风控/封禁）       | P0     | 上线前加用户授权说明页明确告知；首批用户当面演示风险；不存自动重登逻辑       |
| **简历正文 / Boss cookie 泄漏**（日志 / 错误响应） | P0     | 日志脱敏测试在 CI 跑；错误堆栈不发前端；敏感字段只记 hash                    |
| **WS 数据串用户**（task-room 隔离漏洞）            | P0     | task room 校验在 WS 中间件做；新增伪造 task_id 攻击测试                      |
| 4GB RAM 跑 3 Chrome 进程 OOM                       | P1     | 阶段 5 压测；超阈值升 8GB（$48/月，仍在预算）                                |
| API 月成本超 ¥100                                  | P1     | 限流 + 80% 预警；如频繁触顶，砍单用户月配额从 10 到 5                        |
| **进程重启状态丢失**（profile 孤儿化、限流绕过）   | P1     | SQLite 持久化（TD-2 已解决）                                                 |
| **Boss DOM 选择器漂移**（QR 截图选择器失效）       | P1     | 截图 fallback + 日志告警；DOM 选择器变化时立即收到告警                       |
| **AI JSON 解析失败率**（thinking 模式截断）        | P1     | schema 校验失败时记 raw response 前 200 字 + max_tokens 已调大到 6000        |
| 创始人维护成本高                                   | P2     | 一键部署脚本 + 实时 JSONL 日志拉取 + admin 状态页；故障复盘走日志而非现场    |
| 朋友拒绝扫码（账号风险顾虑）                       | P2     | 授权说明页 + 强调"代码开源 + 30 天后自动清 cookie"；首批用户当面演示         |

---

## 验收清单（按阶段 + 总验收）

每阶段完成后跑这套确认才进下一阶段。

### 阶段 0 完成标志

- [ ] SQLite db 文件初始化成功；TTL worker 运行（手动塞过期数据验证清理）
- [ ] 拿到一个邀请码能登录，写 cookie 后刷新页面身份保留
- [ ] 未设 SECRET_KEY 启动失败（fail-fast）；伪 origin 请求被 CORS 拒
- [ ] 连续 5 次错邀请码 → 第 6 次被拒
- [ ] JSONL 文件按天分 + jq 可解析；简历正文不出现
- [ ] TXT 上传被拒；6MB 文件被拒

### 阶段 1 完成标志

- [ ] 两个用户同时点搜索：进度互相不干扰（用户 A 收不到 B 的事件）
- [ ] 伪造 task_id 攻击被拒
- [ ] 同一用户开两个标签页点搜索：第二个进队列等待
- [ ] 任务超时 5 分钟触发 cancel；profile 锁与信号量都被释放
- [ ] 简历上传 24h 后 SQLite 自动清；删除简历按钮立即清
- [ ] F2 未填写时搜索请求被拒
- [ ] Hard filter 排除"外包" 真的过滤 JD 含"外包"字样的岗位
- [ ] 任务跑完 24h 内刷新页面能拿到结果

### 阶段 2 完成标志

- [ ] 创始人点搜索 → 看到 QR → 用手机 Boss App 扫 → 自动进入搜索结果
- [ ] QR 90s 过期重试能正常重生
- [ ] 扫码后 Boss 触发短信验证 → 前端正确显示 security_check 状态
- [ ] 用户取消按钮关闭 Chrome 但保留已扫部分 cookie
- [ ] login_failed 状态显示 + 重试按钮
- [ ] 删除 Boss 登录态按钮真的清空 profile
- [ ] profile 30 天 last_access 后自动清理（手动改时间戳模拟）

### 阶段 3 完成标志

- [ ] DeepSeek 调用后 quotas 表有记录
- [ ] 模拟当日成本到 80% / 100% → 预警 / 拒绝行为正确
- [ ] 单用户跑 11 次搜索：第 11 次被拒绝
- [ ] 第一阶段输出符合 JSON schema（6 类岗位枚举）
- [ ] 算法岗与销售岗的 prompt 评分维度可见差异
- [ ] 4-6 few-shot 锚定后，10 个 holdout 评分与人工判断吻合度 ≥ 70%

### 阶段 4 完成标志

- [ ] 跑一次完整搜索后，JSONL 里能看到全链路日志（任务/阶段/评分/错误）
- [ ] 简历字段不直接出现，只有 hash + 长度
- [ ] `cat logs/tasks/<日期>.jsonl | jq` 可直接分析
- [ ] Admin 状态页能正确显示当日成本、活跃 task 数、失败率

### 阶段 5 完成标志（上线前）

- [ ] 2-3 并发用户 × 50 岗位压测：内存 < 80%；p95 < 5 分钟；OOM 后服务自启恢复
- [ ] Boss 反爬告警机制（失败率 > 30% 触发 journald warning）
- [ ] 一键部署脚本 + smoke test
- [ ] 首个用户运行手册完整

### 上线给第 1 个朋友前的最终 checklist

- [ ] 所有阶段验收通过
- [ ] 创始人自评 10 个熟悉岗位与 AI 评分吻合度 ≥ 70%
- [ ] 当面演示一次完整流程给朋友（含风险授权说明）
- [ ] 备份 SQLite + Chrome profile 目录
- [ ] 创建朋友的专属邀请码

---

## 实施完毕后的清理

- [ ] 更新 `ARCHITECTURE.md` 新增 ADR-7 (SQLite 状态层)、ADR-8 (邀请码身份)、ADR-9 (WS task-room 隔离)、ADR-10 (QR 透传 7 状态机)、ADR-11 (限流与成本模型)
- [ ] 删除本文件 `IMPLEMENTATION_PLAN.md`
- [ ] CLAUDE.md 更新（新模块说明：日志、限流、用户系统、SQLite、安全基线）
- [ ] 邀请第 1 个朋友测试前，跑全套验收清单
