# Boss 直聘智能求职助手

通过 Playwright 自动爬取 Boss 直聘岗位，再用多 AI 模型**两阶段评分**（DeepSeek V4-Flash 两阶段：筛选 thinking=off + 匹配 thinking=on），帮你在大量搜索结果中快速判断投递优先级。

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
#   OPENAI_API_KEY=sk-xxx

# 4. 首次生成并持久保存两个运行时密钥（生产请写入 systemd EnvironmentFile）
export FLASK_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export APP_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

# 5. 启动
python run_web.py
```

`APP_ENCRYPTION_KEY` 用于加密用户保存的模型 Key，必须与 Flask 会话密钥分开，
并且在服务重启后保持不变；更换它会使已有密文无法解密，用户需要重新配置模型 Key。

生产环境使用 Gunicorn 单进程多线程，避免内存中的任务状态、Socket.IO 房间和
Chrome 并发信号量被多个 worker 拆散：

```bash
gunicorn --bind 127.0.0.1:3001 --worker-class gthread --workers 1 \
  --threads 16 --timeout 120 'backend.app:create_app_for_gunicorn()'
```

仓库内提供 `deploy/boss-automation.service` 和每日 04:00 的
`deploy/boss-state-backup.cron`。安装前按服务器实际目录调整路径；备份使用
SQLite 在线快照、gzip 压缩并保留最近 14 份。

邀请码由服务器 CLI 管理：

```bash
python scripts/invite.py generate [--count 3]
python scripts/invite.py list [--status unused]
python scripts/invite.py revoke <code>
```

服务器可持久安装短命令（比 shell alias 更不依赖登录环境）：

```bash
sudo ln -sfn /var/www/boss_automation/scripts/invite /usr/local/bin/invite
invite generate
```

访问 **http://localhost:3001**（默认端口；可在 `config/app_config.yaml` 的 `web.port` 调整。注意 macOS 26 的 5000 端口被 AirPlay 占了，本项目避开了）。首次使用会弹出浏览器，**扫码登录 Boss 直聘**（登录态持久化保存，下次免登）。

## 使用流程

1. 上传简历（PDF/DOCX，仅 session 内临时存储）
2. 输入关键词、城市、数量
3. 等待：爬取 → DeepSeek 筛选 → DeepSeek thinking 模式匹配评分
4. 查看按分数降序排列的岗位卡片

## 测试

> ⚠️ `tests/` 已加入 `.gitignore`，不上传 GitHub。本地保留供 TDD 开发，新机器 clone 后没有该目录。

```bash
pytest tests/ --ignore=tests/integration_test_crawl.py   # 单元测试
python tests/integration_test_crawl.py                   # 集成测试（需手动扫码）
```

## 技术栈

Python 3.12 · Flask + SocketIO · **patchright**（反检测 Playwright）· 多 AI 提供商（DeepSeek / Claude / GPT）

> 环境踩坑（macOS 26 需 playwright≥1.60、依赖清单等）见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 的「环境注意事项」。
