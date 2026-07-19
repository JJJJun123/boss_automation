# 发布准备（阶段 R）— GPT 参数修复 + 阶段二预算 + 朋友试用包

**日期：** 2026-07-19
**状态：** 已批准（用户选定路线 ①：先收尾再邀请朋友试用）
**性质：** 明确 bug 修复 + 运营准备（office-hours 豁免）

## 背景

云端全链路已跑通（邀请 → 简历 → BYOK → QR 透传登录 → 全量抓取 → 两阶段分析）。
邀请朋友前拆掉两颗已知的雷、补一份使用说明。

## R1. GPT 客户端采样参数（与 Claude 同款雷）

GPT-5 家族（配置映射 screening=gpt-5-mini / analysis=gpt-5.2）是推理模型，
拒收非默认 `temperature`/`top_p`/`top_k`。现状两个 GPT 客户端全部硬编码发
temperature——GPT 用户阶段一第一发就会 400。

**修法（与 Claude 修复完全同策略）**：`gpt_client.py` + `gpt_client_sdk.py`
所有调用点（call_api / call_api_simple / call_api_stream）不再发送任何采样
参数；上游显式传入也忽略。对旧模型省略 = 用默认值，无副作用。

## R2. GPT token 参数名（第二颗雷）

GPT-5 推理系列用 `max_completion_tokens`，旧参数 `max_tokens` 被拒。
`max_completion_tokens` 同时兼容旧 chat 模型（官方通用替代参数）。

**修法**：

- HTTP 客户端 payload：`"max_tokens": N` → `"max_completion_tokens": N`
- SDK 客户端：`max_tokens=N` kwarg → `max_completion_tokens=N`
- 客户端对外签名不变（仍收 `max_tokens=` kwarg，内部转换）——上游
  analyzer 不用改

## R3. 阶段二分析预算按 provider 区分

现状 `_call_ai_for_matching` 硬编码 `max_tokens=6000`。Claude sonnet-5
自适应思考的 thinking token 计入 max_tokens，6000 偏紧（风险：JSON 截断
→ 解析失败）；GPT 推理系同理。DeepSeek 维持 6000（已调优，且其输出上限
更低，盲目调大有 400 风险）。

**修法**：`EnhancedJobAnalyzer` 增加预算查表，按 `job_analyzer.ai_provider`：

| provider            | 阶段二 max_tokens |
| ------------------- | ----------------- |
| claude              | 16000             |
| gpt                 | 16000             |
| 其他（deepseek 等） | 6000（现状）      |

实现契约（测试依赖）：`EnhancedJobAnalyzer._analysis_max_tokens() -> int`
方法，`_call_ai_for_matching` 用它取代硬编码 6000。

## R4. 朋友试用包（运营，无代码）

- `docs/USER_GUIDE.md`：一页使用说明——邀请码进门、DeepSeek Key 注册充值
  与获取步骤（推荐路径）、上传简历、首次搜索扫码（必须 Boss App 扫一扫，
  微信无效）、试用 3 次后需自带 Key、常见问题（扫码超时重试即可）
- 生成 10 个邀请码交付用户分发

## 测试计划（TDD，先红后绿）

`tests/test_gpt_sampling_params.py`

- HTTP：call_api / call_api_simple 请求体无 temperature/top_p/top_k
- HTTP：请求体用 max_completion_tokens、无 max_tokens
- HTTP：上游显式传 temperature=0.1 也被忽略
- SDK：messages/completions create kwargs 无采样参数、
  用 max_completion_tokens
- 响应解析回归：choices[0].message.content 正常返回

`tests/test_analysis_token_budget.py`

- provider=claude → 阶段二调用收到 max_tokens=16000
- provider=gpt → 16000
- provider=deepseek → 6000（现状不回归）
- `_analysis_max_tokens` 契约存在

## 不做

- GPT Responses API 迁移（chat completions 仍可用）
- 自定义 base_url / 中转（后续）
- 阶段一（粗筛）预算调整（200 tokens 二分类够用）
