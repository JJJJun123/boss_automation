# Boss 直聘智能求职助手

通过 Playwright 自动爬取 Boss 直聘岗位，再用多 AI 模型**两阶段评分**（GLM 类型筛选 → 主力模型简历匹配），帮你在大量搜索结果中快速判断投递优先级。

- 平台只给岗位列表；本工具对每个岗位给出 **1–10 分匹配评分** + 匹配亮点 / 差距 / 一句话总结。
- 跨关键词统一排序，实时进度推送（WebSocket）。

> 详细需求见 [design.md](design.md)；架构与技术决策见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 快速开始

```bash
# 1. 环境（推荐 conda，python 3.12）
conda create -n boss_dev python=3.12 && conda activate boss_dev
pip install -r requirements.txt

# 2. 安装浏览器（用 patchright 的反检测 Chrome —— 关键，普通 playwright 会被反爬拦截）
patchright install chrome

# 3. 配置 API 密钥：创建 config/secrets.env
#   DEEPSEEK_API_KEY=sk-xxx
#   CLAUDE_API_KEY=sk-ant-xxx
#   GEMINI_API_KEY=AIzaSy-xxx
#   GLM_API_KEY=xxx
#   OPENAI_API_KEY=sk-xxx

# 4. 启动
python run_web.py
```

访问 **http://localhost:5000**。首次使用会弹出浏览器，**扫码登录 Boss 直聘**（登录态持久化保存，下次免登）。

## 使用流程

1. 上传简历（PDF/DOCX，仅 session 内临时存储）
2. 输入关键词、城市、数量
3. 等待：爬取 → GLM 类型筛选 → 主力模型简历匹配评分
4. 查看按分数降序排列的岗位卡片

## 测试

```bash
pytest tests/ --ignore=tests/integration_test_crawl.py   # 单元测试
python tests/integration_test_crawl.py                   # 集成测试（需手动扫码）
```

## 技术栈

Python 3.12 · Flask + SocketIO · **patchright**（反检测 Playwright）· 多 AI 提供商（DeepSeek / Claude / Gemini / GLM / GPT）

> 环境踩坑（macOS 26 需 playwright≥1.60、依赖清单等）见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 的「环境注意事项」。
