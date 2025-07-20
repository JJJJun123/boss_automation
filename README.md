# Boss直聘智能求职助手 - Web版本

基于现代Web技术的Boss直聘智能岗位筛选系统，融合双引擎爬虫和多AI模型分析，为求职者提供精准的岗位匹配服务。

**专为以下岗位类型优化**：市场风险管理、咨询相关、AI/人工智能、金融科技

## ✨ 核心特性

- 🌐 **现代化Web界面**: Apple风格UI + 实时进度显示
- 🎭 **双引擎爬虫**: Selenium(稳定) + Playwright MCP(AI驱动)
- 🤖 **多AI模型支持**: DeepSeek/Claude/Gemini智能分析
- 📊 **智能评分系统**: 1-10分精准匹配度评估
- ⚡ **实时通信**: WebSocket实时进度和状态更新
- ⚙️ **动态配置**: Web界面直接调整搜索参数
- 🏙️ **多城市支持**: 上海、北京、深圳、杭州可选

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <your-repo-url>
cd boss_automation

# 安装Python依赖
pip install -r requirements.txt

# 安装Playwright MCP (通过Claude Code)
claude mcp add playwright npx -- @playwright/mcp@latest
```

### 2. 配置API密钥

创建 `config/secrets.env` 文件并添加你的API密钥：

```bash
# AI模型API密钥 (至少需要一个)
DEEPSEEK_API_KEY=sk-xxx    # 推荐，性价比高
CLAUDE_API_KEY=sk-ant-xxx  # 可选，分析质量优秀
GEMINI_API_KEY=xxx         # 可选，Google出品
```

**获取API Key**:
- **DeepSeek**: [平台链接](https://platform.deepseek.com/) - 便宜实用
- **Claude**: [控制台](https://console.anthropic.com/) - 高质量分析
- **Gemini**: [AI Studio](https://aistudio.google.com/) - Google产品

### 3. 启动应用

```bash
# 启动Web版本 (推荐)
python run_web.py

# 或启动CLI版本
python main.py
```

**访问地址**: http://localhost:5000

### 4. 使用流程

#### Web版本 (推荐)
1. **打开浏览器**: 访问 http://localhost:5000
2. **配置搜索**: 选择城市、关键词、爬虫引擎
3. **开始搜索**: 点击"开始搜索"按钮
4. **实时查看**: 进度和结果实时显示
5. **查看详情**: 点击"完整信息"查看岗位详情

#### CLI版本 (传统)
1. **启动程序**: 自动打开浏览器窗口
2. **手动登录**: 在Boss直聘完成登录
3. **自动处理**: 程序自动搜索和AI分析
4. **查看结果**: 控制台显示 + 文件保存

## ⚙️ 配置说明

### 配置文件结构

项目采用三层配置管理：

```bash
config/
├── secrets.env              # API密钥 (不提交到Git)
├── app_config.yaml         # 应用级配置
└── user_preferences.yaml   # 用户偏好配置
```

### Web界面配置 (推荐)

直接在Web界面调整：
- **搜索关键词**: 如"市场风险管理"、"数据分析"
- **目标城市**: 上海、北京、深圳、杭州
- **搜索数量**: 总搜索岗位数 (1-100)
- **分析数量**: AI分析岗位数 (1-50)
- **爬虫引擎**: Selenium 或 Playwright MCP

### 文件配置方式

**1. API密钥配置** (`config/secrets.env`):
```bash
DEEPSEEK_API_KEY=sk-xxx
CLAUDE_API_KEY=sk-ant-xxx
GEMINI_API_KEY=xxx
```

**2. 用户偏好** (`config/user_preferences.yaml`):
```yaml
search:
  keyword: "市场风险管理"
  max_jobs: 20
  max_analyze_jobs: 10
  spider_engine: "selenium"    # selenium 或 playwright_mcp

ai_analysis:
  provider: "deepseek"         # deepseek/claude/gemini
  min_score: 6
```

### AI模型选择

- **DeepSeek**: 性价比最高，推荐日常使用
- **Claude**: 分析质量优秀，适合重要岗位
- **Gemini**: Google产品，平衡性能和成本

## 输出示例

```
📋 岗位 #1
🏢 公司: 某某金融公司
💼 职位: 市场风险管理专员
💰 薪资: 15-25K
⭐ AI评分: 8.5/10 (推荐)
💡 分析: 高度匹配的风险管理岗位
📝 理由: 岗位要求与求职者背景高度匹配...
```

## 📁 项目结构

```
boss_automation/
├── backend/                    # Web后端
│   └── app.py                 # Flask应用 + 嵌入式前端
├── crawler/                    # 双引擎爬虫模块
│   ├── boss_spider.py         # Selenium爬虫引擎
│   ├── playwright_spider.py   # Playwright MCP引擎
│   └── browser_manager.py     # 浏览器管理
├── analyzer/                   # AI分析模块
│   ├── deepseek_client.py     # DeepSeek客户端
│   ├── claude_client.py       # Claude客户端
│   ├── gemini_client.py       # Gemini客户端
│   ├── ai_client_factory.py   # AI模型工厂
│   └── job_analyzer.py        # 统一分析器
├── config/                     # 分离式配置管理
│   ├── config_manager.py      # 配置管理器
│   ├── app_config.yaml        # 应用配置
│   ├── user_preferences.yaml  # 用户偏好
│   └── secrets.env           # API密钥
├── data/                      # 数据输出
│   ├── jobs_results.json     # 搜索结果
│   └── jobs_analysis.txt     # 分析报告
├── frontend/                  # 前端开发目录(预留)
├── .gitignore                # Git忽略文件
├── requirements.txt          # Python依赖
├── main.py                   # CLI版本入口
├── run_web.py               # Web版本启动脚本
├── design.md                # 设计文档
└── README.md                # 项目说明
```

## 注意事项

1. **合规使用**: 请遵守Boss直聘的使用条款
2. **频率控制**: 程序内置了延迟机制，避免过频请求
3. **隐私保护**: 登录信息仅用于本地访问，不会上传
4. **API费用**: DeepSeek API按使用量计费，请注意控制成本

## 故障排除

1. **爬虫启动失败**: 检查Chrome浏览器是否正确安装
2. **登录问题**: 建议使用扫码登录方式
3. **API调用失败**: 检查AI API Key是否正确配置
4. **岗位提取失败**: 可能是网站结构变化，已内置多重策略
5. **公司/薪资信息获取失败**: 程序会输出调试信息帮助定位问题

## AI评分机制

**评分标准 (1-10分)**:
- **岗位类型匹配度**: 是否符合求职意向（风险管理、咨询、AI、金融）
- **技能要求匹配度**: 技能要求与背景的契合程度  
- **薪资合理性**: 薪资是否在期望范围内
- **公司背景适合度**: 公司规模、行业是否符合期望

**推荐逻辑**:
- 8-10分: 强烈推荐 ⭐⭐⭐
- 6-7分: 推荐 ⭐⭐  
- <6分: 不推荐（被过滤）

## 性能优化建议

1. **减少AI分析数量**: 调整 `MAX_ANALYZE_JOBS` 参数
2. **提高筛选标准**: 调整 `MIN_SCORE` 参数  
3. **选择合适AI模型**: DeepSeek最便宜，Claude质量最高
4. **控制搜索范围**: 调整 `MAX_JOBS` 参数

## 快速开始 (Web版本) 🌟

### 方式一：一键启动 (推荐)

```bash
# 启动Web版本
python run_web.py
```

### 方式二：分别启动

```bash
# 启动后端服务
cd backend
python app.py

# 启动前端 (可选，如果需要开发)
cd frontend
npm install
npm start
```

**访问地址**: http://localhost:5000

## Web版本特性

- 🎨 **苹果风格UI**: 现代化界面设计，支持暗色主题
- ⚡ **实时进度**: WebSocket实时显示搜索和分析进度
- 🔧 **动态配置**: 网页界面直接调整搜索参数
- 📊 **数据可视化**: 结果统计和进度展示
- 📱 **响应式设计**: 支持桌面和移动设备

## 📈 版本更新

### v2.0 Web版本 ✅ (最新)
- ✅ **双引擎爬虫**: Selenium + Playwright MCP双引擎架构
- ✅ **现代Web界面**: Flask + 嵌入式HTML + Apple风格UI
- ✅ **实时通信**: WebSocket双向通信，实时进度显示
- ✅ **智能配置**: 三层配置文件分离，Web界面动态调整
- ✅ **多城市支持**: 上海/北京/深圳/杭州可选
- ✅ **引擎区分**: 明确显示不同爬虫引擎的工作状态
- ✅ **参数传递**: 修复前端参数完整传递到后端
- ✅ **默认详情**: 岗位详细信息默认获取，一键展开

### v1.5 CLI增强版本 ✅
- ✅ **多AI模型**: DeepSeek/Claude/Gemini三种AI支持
- ✅ **智能评分**: 1-10分岗位匹配度评估
- ✅ **配置管理**: YAML + ENV分离式配置
- ✅ **滚动加载**: 支持获取更多岗位信息
- ✅ **多元素定位**: 适应网站结构变化

### v1.0 MVP版本 ✅
- ✅ **基础爬虫**: Selenium自动化爬取
- ✅ **登录辅助**: 手动登录 + Cookie保存
- ✅ **数据导出**: 文本和JSON格式输出
- ✅ **反爬虫机制**: 多重策略避免检测

### v2.1 计划中 ⏳
- 🔄 **邮件通知**: 符合条件岗位邮件推送
- 🔄 **定时任务**: 自动化定时搜索
- 🔄 **数据持久化**: SQLite数据库存储
- 🔄 **用户系统**: 多用户支持和认证
- 🔄 **网站扩展**: 支持更多招聘平台