# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

Boss直聘智能求职助手：Python Flask 后端 + Jinja2 前端，通过 Playwright 爬取岗位信息，再用多 AI 模型两阶段评分筛选（类型过滤 → 简历匹配）。

## 项目结构

```
boss_automation_dev/
├── backend/                    # Flask 后端
│   ├── app.py                  # 入口：Flask + SocketIO WebSocket
│   ├── services/job_service.py # 业务逻辑：协调爬虫和分析器
│   ├── templates/index.html    # Jinja2 前端主页
│   └── static/                 # CSS / JS 静态资源
├── crawler/                    # 爬虫模块
│   ├── unified_crawler_interface.py  # 对外主接口 unified_search_jobs()
│   ├── real_playwright_spider.py     # Playwright 浏览器自动化
│   ├── enhanced_extractor.py         # HTML 信息提取
│   └── session_manager.py            # 登录会话持久化
├── analyzer/                   # AI 分析模块
│   ├── enhanced_job_analyzer.py      # 核心：两阶段分析引擎
│   ├── ai_client_factory.py          # 工厂：创建各 AI 客户端
│   ├── clients/                      # 各 AI 提供商实现（HTTP + SDK）
│   ├── prompts/                      # 所有 prompt 模板（修改逻辑改这里）
│   └── resume/resume_parser_v2.py    # 简历解析（PDF/DOCX）
├── config/                     # 配置管理
│   ├── config_manager.py             # 统一加载三层配置
│   ├── app_config.yaml               # 应用级配置
│   ├── user_preferences.yaml         # 用户搜索偏好
│   └── secrets.env                   # API 密钥（不提交 Git）
├── tests/                      # 测试套件
├── run_web.py                  # 启动脚本（含依赖检查）
└── requirements.txt
```

## 安装与启动

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 安装 Playwright 浏览器（首次必须）
playwright install chromium

# 3. 创建 secrets.env（必须）
# config/secrets.env 模板：
# DEEPSEEK_API_KEY=sk-xxx
# CLAUDE_API_KEY=sk-ant-xxx
# GEMINI_API_KEY=AIzaSy-xxx
# GLM_API_KEY=xxx
# OPENAI_API_KEY=sk-xxx

# 4. 启动服务
python run_web.py
```

**访问地址**：http://localhost:5000

> 首次使用需在浏览器中手动扫码登录 Boss 直聘，会话保存于 `crawler/sessions/`。

## 配置管理

三层配置，启动前必须存在所有文件：

| 文件                           | 用途                                  |
| ------------------------------ | ------------------------------------- |
| `config/secrets.env`           | API 密钥（不提交 Git）                |
| `config/app_config.yaml`       | 应用级配置（爬虫参数、AI 默认提供商） |
| `config/user_preferences.yaml` | 用户搜索偏好（关键词、城市、数量）    |

`ConfigManager` (`config/config_manager.py`) 统一加载三层配置，通过 `get_app_config(key, default)` 读取。

## 架构概览

```
请求链路：
浏览器 <--WebSocket--> Flask/SocketIO (backend/app.py)
                          ↓
                  JobSearchService (backend/services/job_service.py)
                          ↓
         UnifiedCrawlerInterface (crawler/unified_crawler_interface.py)
                          ↓
              real_playwright_spider.py  (Playwright 爬虫)
                          ↓
              EnhancedJobAnalyzer (analyzer/enhanced_job_analyzer.py)
                   ↓                        ↓
         第一阶段：GLM-4.5 快速类型筛选    第二阶段：主力模型简历匹配评分
         (extraction_provider)             (analysis_provider, 1-10分)
```

### 关键模块说明

- **`backend/app.py`**：Flask 入口，SocketIO 发送实时进度 (`emit_progress`)，前端用 Jinja2 模板渲染。

- **`crawler/unified_crawler_interface.py`**：统一爬虫接口，`unified_search_jobs()` 是对外主函数，内部调用 `real_playwright_spider.py`。

- **`analyzer/enhanced_job_analyzer.py`**：两阶段分析器：
  1. **类型筛选**（GLM-4.5，廉价快速）：过滤明显不符岗位
  2. **简历匹配**（主力模型）：按用户简历评分（1-10分）+ 匹配亮点 + 不足

- **`analyzer/ai_client_factory.py`**：工厂模式，根据 `provider` 参数创建对应 AI 客户端。支持官方 SDK 和 HTTP 两种方式。

- **`analyzer/prompts/`**：所有 prompt 模板集中管理，修改分析逻辑只需改此目录。

## 测试

```bash
pytest                                          # 运行所有测试
pytest tests/test_prompts.py                   # 提示词模板验证
pytest tests/test_enhanced_job_analyzer.py     # 分析器单元测试
python tests/integration_test_crawl.py         # 集成测试（需手动登录）
```

| 测试文件                        | 覆盖内容                           |
| ------------------------------- | ---------------------------------- |
| `test_prompts.py`               | prompt 占位符完整性、JSON 格式验证 |
| `test_enhanced_job_analyzer.py` | 筛选、排序、匹配输出格式           |
| `test_app_no_market.py`         | 代码静态检查（已废弃功能未残留）   |
| `integration_test_crawl.py`     | 爬虫全流程（需扫码，手动运行）     |

> 新功能必须先补充测试再实现（TDD）。

## AI 提供商接入

新增 AI 提供商时：

1. 在 `analyzer/clients/` 下创建客户端（继承 `base_client.py`）
2. 在 `AIClientFactory.create_pure_client()` 添加 provider 分支
3. 在 `config/app_config.yaml` 的 `ai.providers` 中注册

支持的提供商：`deepseek`、`claude`、`gemini`、`glm`、`gpt`
