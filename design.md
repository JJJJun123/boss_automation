# Boss直聘自动化项目设计文档

## 项目概述

基于现代Web技术的Boss直聘(https://www.zhipin.com/)智能求职助手，通过双引擎爬虫技术获取岗位信息，使用多AI模型分析岗位匹配度，提供实时的智能化岗位筛选服务。

**当前状态**: Web版本已完成，支持实时搜索、双引擎爬虫、多AI分析、现代化UI界面

**目标岗位类型**:
- 市场风险管理相关岗位
- 咨询相关岗位（战略咨询、管理咨询、行业分析）  
- AI/人工智能相关岗位
- 金融相关岗位（银行、证券、基金、保险）

**支持城市**: 上海、北京、深圳、杭州（可扩展）

## 核心需求

### 1. 自动化岗位筛选
- 根据用户设定的过滤条件自动筛选岗位
- 处理boss直聘的登录和反爬虫机制
- 获取岗位的详细信息（公司、经验要求、薪资等）

### 2. 智能岗位分析
- 使用DeepSeek API分析岗位描述
- 总结岗位对求职者的主要要求
- 根据用户个人情况评估岗位适合度

### 3. 邮件通知系统
- 每日定时执行（建议每天早上8点）
- 整合5-10个筛选后的岗位信息
- 发送到用户个人邮箱，包含岗位链接

## 技术架构

### 技术栈选择
- **语言**: Python 3.9+
- **后端框架**: Flask + SocketIO (实时通信)
- **前端界面**: 嵌入式HTML + Tailwind CSS (Apple风格UI)
- **爬虫引擎**: 
  - Selenium + undetected-chromedriver (传统稳定)
  - Playwright MCP (AI驱动，更智能)
- **AI分析**: 支持多种AI模型
  - DeepSeek API (默认，性价比高)
  - Claude API (分析质量优秀)
  - Gemini API (Google出品)
- **配置管理**: YAML配置文件 + 环境变量分离
- **数据格式**: JSON导出 + 实时展示
- **部署方式**: 本地Web服务 (未来可云端部署)

### 项目结构
```
boss_automation/
├── backend/                    # Web后端
│   └── app.py                 # Flask应用 + 嵌入式前端
├── crawler/                    # 双引擎爬虫模块
│   ├── __init__.py
│   ├── boss_spider.py         # Selenium爬虫
│   ├── playwright_spider.py   # Playwright MCP爬虫
│   └── browser_manager.py     # 浏览器管理
├── analyzer/                   # AI分析模块
│   ├── __init__.py
│   ├── deepseek_client.py     # DeepSeek API客户端
│   ├── claude_client.py       # Claude API客户端
│   ├── gemini_client.py       # Gemini API客户端
│   ├── ai_client_factory.py   # AI客户端工厂
│   └── job_analyzer.py        # 统一岗位分析器
├── config/                     # 分离式配置管理
│   ├── config_manager.py      # 配置管理器
│   ├── app_config.yaml        # 应用级配置
│   ├── user_preferences.yaml  # 用户偏好配置
│   └── secrets.env           # 敏感信息(API密钥)
├── data/                      # 数据存储
│   ├── jobs_results.json     # 搜索结果
│   ├── jobs_analysis.txt     # 分析报告
│   └── logs/                 # 日志文件
├── frontend/                  # 前端开发目录(预留)
├── .gitignore                # Git忽略文件
├── requirements.txt          # Python依赖
├── main.py                   # CLI版本入口
├── run_web.py               # Web版本启动脚本
├── design.md                # 设计文档
└── README.md                # 项目说明
```

## 核心功能模块

### 1. 双引擎爬虫模块 (crawler/)

**🤖 Selenium引擎 (传统稳定)**:
- 使用undetected-chromedriver模拟真实浏览器
- 手动登录辅助 + Cookie保存机制
- 随机化用户行为（滚动、点击间隔、鼠标移动）
- 多元素定位策略，适应网站结构变化
- 滚动加载更多岗位

**🎭 Playwright MCP引擎 (AI驱动)**:
- 基于自然语言指令控制浏览器
- AI理解页面结构，更难被检测
- 自动处理复杂交互和验证
- 更强的适应性和稳定性
- 支持截图和调试功能

**统一接口设计**:
- 用户可在Web界面选择爬虫引擎
- 两种引擎提供一致的数据格式
- 自动切换和故障转移机制
- 性能监控和效果对比

### 2. AI分析模块 (analyzer/)

**多AI模型支持**:
- DeepSeek API集成 (默认)
- Claude API集成
- Gemini API集成
- 统一的AI客户端接口

**分析功能**:
- 岗位描述文本分析
- 技能要求提取
- 工作经验要求分析
- 薪资范围合理性评估

**匹配算法**:
- 技能匹配度计算 (1-10分)
- 经验匹配度评估
- 综合评分系统
- 推荐优先级排序

**评分标准**:
- 岗位类型匹配度（是否符合求职意向）
- 技能要求匹配度
- 薪资合理性
- 公司背景适合度
- 最终输出：评分、推荐状态、详细理由、一句话总结

### 3. 过滤系统 (filter/)

**过滤条件**:
- 地理位置
- 薪资范围
- 工作年限要求
- 公司规模
- 行业类型
- 技能关键词

**智能过滤**:
- 基于历史数据的动态调整
- 黑名单公司过滤
- 重复岗位去重

### 4. 邮件通知 (notification/)

**邮件内容**:
- 岗位标题和链接
- 公司信息
- 薪资范围
- 匹配度评分
- AI分析摘要

**邮件格式**:
- HTML格式，美观易读
- 移动端适配
- 一键跳转到岗位页面

## 配置管理

### 用户配置 (config/user_profile.yaml)
```yaml
personal_info:
  name: "用户姓名"
  experience_years: 5
  skills: ["Python", "机器学习", "数据分析"]
  preferred_locations: ["北京", "上海", "深圳"]
  salary_range: [20000, 35000]
  
preferences:
  company_size: ["100-499人", "500-999人", "1000人以上"]
  industries: ["互联网", "人工智能", "金融科技"]
  blacklist_companies: ["某某公司"]
```

### 系统配置 (.env文件)
```bash
# AI模型配置
DEEPSEEK_API_KEY=sk-0a7febc3244b4bbc8e06d7030f162506
AI_PROVIDER=deepseek  # deepseek/claude/gemini
DEEPSEEK_MODEL=deepseek-chat
CLAUDE_API_KEY=your_claude_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# 搜索配置
SEARCH_KEYWORD=市场风险管理
CITY_CODE=101210100  # 上海
MAX_JOBS=20          # 搜索岗位总数
MAX_ANALYZE_JOBS=10  # AI分析岗位数
MIN_SCORE=6          # 最低评分标准

# 城市代码参考：
# 101210100 = 上海
# 101210300 = 杭州  
# 101280600 = 深圳
# 101010100 = 北京
```

## 开发计划

### 阶段一：基础框架搭建 ✅ 已完成
- [x] 项目结构创建
- [x] 依赖环境配置
- [x] 基础爬虫框架
- [x] 数据库设计

### 阶段二：核心功能开发 ✅ 已完成(MVP)
- [x] boss直聘爬虫实现
- [x] 多AI模型API集成 (DeepSeek/Claude/Gemini)
- [x] 岗位分析算法
- [ ] 邮件通知系统 (待开发)

### 阶段三：系统优化 🔄 进行中
- [x] 反爬虫机制优化
- [x] 滚动加载更多岗位
- [x] 错误处理和日志
- [x] 配置管理完善 (.env文件)
- [x] 多元素定位策略

### 阶段四：测试和部署 ⏳ 待开发
- [ ] 单元测试
- [ ] 集成测试
- [ ] 部署方案
- [ ] 监控和维护

## 当前MVP功能清单

### ✅ 已实现功能
1. **智能爬虫系统**
   - 手动登录辅助 + Cookie保存
   - 多种元素定位策略
   - 滚动加载更多岗位
   - 反爬虫机制

2. **多AI模型分析**
   - DeepSeek API (默认)
   - Claude API 支持
   - Gemini API 支持
   - 1-10分评分系统

3. **灵活配置系统**
   - 城市选择 (上海/杭州/深圳/北京)
   - 搜索关键词可配置
   - AI分析数量可调整
   - 最低评分标准可设置

4. **智能输出系统**
   - 控制台详细显示
   - 文件结果保存
   - 调试信息输出

### ✅ Web版本核心功能 (v2.0)
1. **现代化Web界面**
   - Flask + 嵌入式HTML + Tailwind CSS
   - 苹果风格UI设计，支持移动端
   - 实时状态指示和连接状态
   - 美观的卡片式布局

2. **双引擎爬虫系统**
   - Selenium传统引擎 (稳定可靠)
   - Playwright MCP引擎 (AI驱动，新一代)
   - 用户可在界面动态选择引擎
   - 引擎区分显示和性能对比

3. **实时通信系统**
   - WebSocket双向通信
   - 实时进度条和百分比显示
   - 搜索日志和状态更新
   - 任务执行状态跟踪

4. **智能配置管理**
   - 三层配置文件分离(app/user/secrets)
   - Web界面动态参数调整
   - 城市选择(上海/北京/深圳/杭州)
   - 搜索数量和分析数量可调

5. **增强数据处理**
   - 默认获取完整岗位详情
   - 展开式详情信息显示
   - JSON格式数据导出
   - 统计信息和匹配度展示

### ⏳ 待开发功能
1. 邮件通知系统
2. 定时调度任务
3. 数据库持久化
4. 多招聘网站支持
5. 用户认证系统

## 注意事项

1. **合规性**: 遵守boss直聘的robots.txt和用户协议
2. **频率控制**: 避免过于频繁的请求导致IP被封
3. **数据安全**: 妥善保管用户凭据和个人信息
4. **错误处理**: 完善的异常处理和重试机制
5. **可扩展性**: 设计时考虑后续功能扩展

## 风险评估

1. **技术风险**: 网站反爬虫机制升级
2. **法律风险**: 数据获取的合规性
3. **维护成本**: 网站结构变更需要代码调整
4. **稳定性**: 依赖第三方服务的可用性

## 使用方式和部署

### Web版本启动 (推荐)
```bash
# 快速启动
python run_web.py

# 访问地址
http://localhost:5000
```

### CLI版本启动 (传统)
```bash
# 命令行版本
python main.py
```

### 配置要求
1. **API密钥配置**: 在 `config/secrets.env` 中设置 DeepSeek API Key
2. **Playwright MCP**: 需要通过 Claude Code 安装 `claude mcp add playwright`
3. **浏览器环境**: Chrome/Chromium 浏览器

### 核心文件说明
- `run_web.py`: Web版本启动脚本
- `backend/app.py`: Flask应用主文件，包含完整前端界面
- `config/`: 三层配置管理，支持动态调整
- `crawler/`: 双引擎爬虫模块

## 技术亮点

1. **双引擎架构**: 传统Selenium + 创新Playwright MCP
2. **嵌入式前端**: 单文件部署，无需复杂构建
3. **实时通信**: WebSocket实现流畅的用户体验
4. **配置分离**: 安全性和灵活性并重
5. **Apple风格UI**: 现代化设计语言

## 后续优化方向

1. 支持多个招聘网站 (猎聘网、智联招聘等)
2. 增加更多AI分析维度 (公司文化匹配等)
3. 邮件通知和定时任务功能
4. 用户认证和数据持久化
5. 云端部署和多用户支持
6. 移动端原生应用开发