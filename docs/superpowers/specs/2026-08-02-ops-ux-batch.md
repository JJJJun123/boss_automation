# 运维与体验批量优化方案（阶段 S）

**日期：** 2026-08-02　**状态：** 方案待确认，未实现
**前置结论：** 5 人并发爬虫互踩问题**不存在** —— `backend/profile_manager.py` 已实现 per-user Chrome profile + 全局 BoundedSemaphore(2)。4GB/2核 VPS 上限 2 个并发 Chrome 是实测安全值，第 3 人搜索会排队 30s 后收到"当前繁忙"。无需改动。

---

## A. Key 配置搬家：首页第 IV 节 → 设置抽屉 【P1 · 半天】

**现状问题：** 密钥输入框裸露在主页（演示截屏风险）、打断"简历→画像→搜索"主流程。业界（Vercel/Kilo/Kodus/Copilot BYOK）全部收在 Settings 区 + 情境弹窗引导。

**方案：**

1. masthead 右侧加 ⚙ 按钮 → 右侧滑出抽屉（编辑风：墨线边框、cream 底、Fraunces 标题），首页第 IV 节整体搬入，后续节号上移
2. `#byok-required-modal`（402 情境弹窗）的"去配置"按钮改为直接拉开抽屉
3. 抽屉内加 **Test 按钮**：新端点 `POST /api/user-key/test`，用待存 Key 发一次最小请求（如 max_tokens=1 的 ping），返回可用/失败原因，存前先探测（业界标配）
4. 抽屉预留分区：Key 配置 / （将来）邀请码管理

**触点：** `index.html`、`style.css`、`main.js`、`app.py`（test 端点）
**风险：** 低。测试点：test 端点对无效 Key 返回明确错误且不泄露异常细节；402 流程回归。

---

## B. 生产服务器替换 Werkzeug → gunicorn 【P0 · 半天】

**现状：** systemd 里 `python run_web.py` 起 Werkzeug dev server，日志持续警告，单请求崩溃风险高。

**关键约束（决定方案形态）：**

- `async_mode="threading"`（app.py:298）→ Socket.IO 本来就走长轮询，**没有真 websocket**，换 gunicorn 不损失任何现有能力
- 任务注册表 / ProfileManager 信号量 / SocketIO 房间全是**进程内状态** → 必须 `--workers 1`

**方案：** `gunicorn --worker-class gthread --workers 1 --threads 16 --timeout 120 'backend.app:create_app_for_gunicorn()'`

1. app.py 加一个 gunicorn 入口工厂（复用 create_app，不再调 socketio.run）
2. systemd unit ExecStart 替换；deploy-boss.sh 健康检查逻辑不变
3. run_web.py 保留为本地开发入口

**风险：** gthread 与 patchright 子进程/后台线程兼容性（threading 模式下理论无碍，上线前在本地压一轮搜索任务验证）。**不用 eventlet/gevent** —— monkey-patch 会弄坏 patchright 与线程模型。

---

## C. state.db 每日备份 【P0 · 1 小时】

**方案：** 服务器 cron 每日 04:00 执行 `sqlite3 state.db ".backup /root/backups/state-$(date +%F).db"`（在线原子快照，不锁写），gzip 后保留最近 14 份，超期删除。可选下一步：rclone 推一份到对象存储/网盘（离机容灾），先不做。
**风险：** 几乎无。测试点：备份文件能被 sqlite3 打开且含全部表。

---

## D. 访谈提速：混合档 【P1 · 半天，建议先观望】

**现状：** 全程主力档，每问 10-20s。已用"即时开场问 + 加载卡"缓解感知。

**方案（若朋友反馈仍嫌慢）：** 追问轮用快档（deepseek-v4-flash，~2s），只在收尾出画像那一次用主力档：

- `profile_chat` 路由：`should_force_finish` 为真、或快档回了 `action=finish` 时，**丢弃快档的 profile**，用主力档带完整历史重新生成最终画像（一次调用）
- 画像质量取决于最后的归纳而非中间追问 → 质量基本不损，每次访谈主力档调用从 ~5 次降到 1 次

**触点：** `app.py` profile_chat 路由、`_create_user_or_station_ai_client`（purpose 加档位参数）
**风险：** 快档追问质量略降（问题可能更平庸）。**建议：等朋友试用反馈再决定**，现在不动。

---

## E. 流式输出（助手 + 访谈） 【P1 · 1 天】

**方案：** 复用现有 Socket.IO 长轮询通道，不引 SSE：

1. AI 客户端加 `call_api_stream()`（provider SDK 的 stream=True，逐 chunk yield）
2. 路由改为后台线程消费 stream，每 chunk `socketio.emit("assistant_chunk", {task/round_id, delta}, to=user_id)`，结束发 `done`
3. 前端逐字追加渲染（textContent 拼接，保持 XSS 规则）；HTTP 响应仅返回 round_id
4. 先做结果页助手（回答长、收益最大），访谈问题短、收益小，二期再说

**风险：** 三家 provider 的 stream 事件格式各异（Claude thinking block 交错）需逐家适配；长轮询下 chunk 到达略有批次感（可接受）。

---

## F. per_keyword 15 → 30 【P2 · 10 分钟】

**方案：** `app.py:833` 默认值 15→30（clamp 上限已是 30）。动态 deadline 公式已按 total_jobs 缩放，无需改。前端滑块默认值同步。
**提醒：** 3 词 × 30 岗全新抓取 ≈ 90 岗，单任务约 50-60 分钟、主力档分析成本翻倍 —— 建议朋友试用初期维持 15，你自己先用 30 验证稳定性。

---

## G. 邀请码管理 【P2 · 两级】

- **最小版（10 分钟）：** `scripts/invite.py` CLI（生成/列出/作废），服务器上 alias `invite`，ssh 一行出码
- **进阶版（半天，可并入 A 的抽屉）：** 抽屉加 admin 区（仅你的 user_id 可见），列码/生码/看各账号最近活跃。5 人规模建议只做最小版。

---

## H. P2 遗留（2026-07-26-review-fixes.md 承接）

- Key 解密失败要落日志（部分已修，待核对）
- P3 nits backlog 顺延

---

## 建议实施顺序

**第一批（一个下午）：** B + C（生产稳定性，跟功能无关先落地）
**第二批（一天）：** A（Key 抽屉 + Test 端点）+ G 最小版
**观望：** D（等反馈）、E（助手流式，第二批后做）、F（你自己先试 30）

每批照旧：TDD 测试先行 → 你实现 → 我 review + 部署。
