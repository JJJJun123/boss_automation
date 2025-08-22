# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Boss直聘智能求职助手 - A web-based intelligent job search assistant for Boss直聘 (zhipin.com) that uses a real Playwright-based crawler and multiple AI models to analyze and score job listings.

**Target job types**: Market risk management, consulting, AI/artificial intelligence, fintech
**Supported cities**: Shanghai, Beijing, Shenzhen, Hangzhou

## Key Commands

### Running the Application

```bash
# Start web version (recommended) - includes both backend and embedded frontend
python run_web.py

# Start CLI version (traditional)
python main.py

# Alternative web startup (separate backend)
cd backend && python app.py

# Stop all running processes
python stop_all.py
```

### Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers (required for real browser operations)
playwright install chromium

# Install safe dependencies (alternative installer)
python install_safe.py
```

## Architecture Overview

The project uses a simplified unified crawler architecture with multiple AI analysis models:

### Core Components

1. **Crawler System** (`crawler/`):
   - **Real Playwright Spider** (`real_playwright_spider.py`): Core crawler engine with persistent browser context and anti-detection
   - **Unified Interface** (`unified_crawler_interface.py`): Simplified interface that uses Real Playwright Spider
   - **Large-Scale Crawler** (`large_scale_crawler.py`): Handles 50-100+ job listings with intelligent batching
   - **Smart Components**: Smart selector (`smart_selector.py`), enhanced extractor (`enhanced_extractor.py`)
   - **Supporting Services**: Session management (`session_manager.py`), retry handling (`retry_handler.py`)

2. **AI Analysis System** (`analyzer/`):
   - **AI Client Factory** (`ai_client_factory.py`): Multi-provider support with dynamic model selection
   - **Supported Providers**: DeepSeek (default, cost-effective), Claude (high quality), Gemini (balanced), GPT, GLM
   - **Job Analyzer** (`job_analyzer.py`): Unified analysis interface with 1-10 scoring system
   - **Enhanced Job Analyzer** (`enhanced_job_analyzer.py`): GLM+DeepSeek mixed mode for better cost-performance
   - **Smart Job Analyzer** (`smart_job_analyzer.py`): Batch processing with intelligent layered analysis
   - **Job Requirement Summarizer** (`job_requirement_summarizer.py`): Structured job requirement analysis with AI
   - **Market Analyzer** (`market_analyzer.py`): Industry and market trend analysis
   - **Resume Components** (`resume/`): Resume parsing and matching capabilities
   - **Prompt Templates** (`prompts/`): Structured prompts for consistent AI analysis
   - **Cost Optimization**: Intelligent caching (`data/job_requirements_cache.json`) and batch processing

3. **Web Application** (`backend/`):
   - **Main App** (`app.py`): Flask + SocketIO server with embedded Apple-style UI
   - **Job Service** (`services/job_service.py`): Business logic layer for job operations
   - **Real-time Features**: WebSocket events for progress updates and live search results
   - **API Endpoints**: RESTful interface for configuration management and search operations

4. **Configuration Management** (`config/`):
   - **Three-tier System**: `secrets.env` (API keys), `app_config.yaml` (app settings), `user_preferences.yaml` (user preferences)
   - **ConfigManager** (`config_manager.py`): Centralized configuration loading, validation, and hot-reload support
   - **Dynamic Updates**: Real-time configuration changes through web interface
   - **Validation**: Built-in validation for all configuration parameters

### Data Flow

1. User configures search parameters via web interface or CLI
2. Configuration validated and stored by ConfigManager  
3. Unified crawler interface uses the Real Playwright Spider engine
4. Crawler fetches job listings with integrated caching, session management and anti-detection
5. AI analyzer processes job descriptions using selected provider (DeepSeek/Claude/Gemini/GPT/GLM)
6. Jobs scored 1-10 based on user preferences and job match criteria
7. Results streamed in real-time via WebSocket to web interface
8. Final data persisted to `data/job_results.json` with metadata

## Configuration Requirements

### API Keys (config/secrets.env)
```bash
DEEPSEEK_API_KEY=sk-xxx    # Required for AI analysis
CLAUDE_API_KEY=sk-ant-xxx  # Optional
GEMINI_API_KEY=xxx         # Optional
GPT_API_KEY=sk-xxx         # Optional
GLM_API_KEY=xxx            # Optional for enhanced analyzer
```

### User Preferences (config/user_preferences.yaml)
- **Search Configuration**: Keywords, cities, job count limits
- **AI Analysis**: Provider selection, minimum score threshold, analysis depth
- **Personal Profile**: Skills, experience, salary expectations, company preferences
- **UI Preferences**: Theme, language, display options, notification settings

### App Configuration (config/app_config.yaml)
- **AI Model Settings**: Default provider, temperature, max tokens
- **Enhanced Analyzer**: GLM+DeepSeek mixed mode toggle
- **Smart Analyzer**: Batch processing and layered analysis settings
- **Crawler Settings**: Retry attempts, timeout, headless mode
- **Web Server**: Host, port, debug mode, WebSocket configuration

## Important Implementation Details

1. **Persistent Browser Context**: Uses `browser_profile/boss_zhipin` to maintain login state across sessions
2. **Large-Scale Processing**: Supports 50-100+ job listings with intelligent batching
3. **Smart Data Extraction**: Multi-stage extraction with 90%+ success rate and adaptive CSS selectors
4. **Session Persistence**: Automatic cookie and session management with persistent browser profile
5. **AI Cost Optimization**: 
   - Intelligent caching system with batch processing (5-10 jobs/API call)
   - Enhanced analyzer using GLM for extraction + DeepSeek for scoring
   - Smart analyzer with layered approach: GLM batch extraction → DeepSeek batch scoring → Claude deep analysis
6. **Anti-Detection System**: Human-like behavior simulation, random delays, smart element selection
7. **Login State Management**: Automatic detection and preservation of login status
8. **Retry Mechanism**: Built-in retry handler with exponential backoff for network failures
9. **Error Recovery**: Multi-strategy retry system with intelligent fallback
10. **Real-time Communication**: WebSocket-based progress updates with detailed status information

## Common Development Tasks

**Crawler System Modifications**:
- Main crawler engine: Update `crawler/real_playwright_spider.py` (core crawler with persistent login)
- Crawler interface: Modify `crawler/unified_crawler_interface.py` for API changes
- Large-scale processing: Modify `crawler/large_scale_crawler.py` for 50-100+ job handling
- Smart extraction: Update `crawler/enhanced_extractor.py` and `crawler/smart_selector.py`  
- Session/retry logic: Update `crawler/session_manager.py` or `crawler/retry_handler.py`

**AI Analysis Enhancements**:
- New AI providers: Create client in `analyzer/clients/` following existing pattern, register in `ai_client_factory.py`
- Job requirement analysis: Modify `analyzer/job_requirement_summarizer.py` for structured analysis
- Analysis logic: Modify `analyzer/job_analyzer.py` for scoring algorithms  
- Enhanced analyzer: Update `analyzer/enhanced_job_analyzer.py` for GLM+DeepSeek mixed mode
- Smart analyzer: Update `analyzer/smart_job_analyzer.py` for batch processing logic
- Prompt engineering: Update templates in `analyzer/prompts/`
- Market analysis: Enhance `analyzer/market_analyzer.py`
- Cost optimization: Update caching logic and batch processing strategies

**Configuration Changes**:
- App settings: Edit `config/app_config.yaml`
- User preferences: Update `config/user_preferences.yaml` structure
- Configuration logic: Modify `config/config_manager.py`

**Frontend Development**:
- Embedded UI: Backend serves UI directly from `backend/app.py` (lines 71+)
- Real-time features: Update WebSocket handlers in both backend and frontend

## 错误处理原则 - 必须严格遵守

### 禁止的做法
1. **禁止静默失败**: 永远不要用默认值掩盖错误。错误就是错误，必须明确显示
2. **禁止假数据**: 不要生成看起来正常的假数据。宁可崩溃也不要假装正常
3. **禁止模糊信息**: 不要用"需要进一步评估"这类模糊描述掩盖失败
4. **禁止过度兜底**: 不要试图"智能恢复"，让错误暴露出来

### 正确的做法
1. **快速失败**: 遇到问题立即报错，让异常向上传播
2. **明确的错误信息**: 准确说明什么失败了，包含具体错误原因
3. **使用异常**: 用raise而不是return默认值
4. **显式错误标记**: 使用error=True, error_message字段

### 代码示例
```python
# ❌ 错误做法 - 绝对禁止
try:
    result = api_call()
except:
    return {"score": 5, "status": "需要评估"}  # 假数据！
    
try:
    data = parse_json(response)
except:
    return get_default_data()  # 静默失败！

# ✅ 正确做法
try:
    result = api_call()
except Exception as e:
    logger.error(f"API调用失败: {e}")
    raise Exception(f"API调用失败: {e}")  # 明确失败！
    
try:
    data = parse_json(response)
except Exception as e:
    return {
        "error": True,
        "error_message": f"JSON解析失败: {e}",
        "data": None
    }
```

### 原则总结
- **透明性优于稳定性**: 宁可让用户看到错误，也不要用假数据欺骗用户
- **调试友好**: 清晰的错误信息让问题定位变得简单
- **不要过度工程**: 简单的失败比复杂的恢复机制更好