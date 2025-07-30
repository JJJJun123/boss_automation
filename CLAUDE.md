# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Boss直聘智能求职助手 - A web-based intelligent job search assistant for Boss直聘 (zhipin.com) that uses dual-engine crawlers and multiple AI models to analyze job listings.

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

# Frontend development server (if needed)
cd frontend && npm start
```

### Development Commands

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright MCP (required for AI-driven crawler)
claude mcp add playwright npx -- @playwright/mcp@latest

# Install Playwright browsers (required for real browser operations)
playwright install chromium

# Install safe dependencies (alternative installer)
python install_safe.py

# Stop all running processes
python stop_all.py
```

### Testing

```bash
# Quick functionality tests
python quick_test.py
python quick_test_large_scale.py

# Safe web application test
python run_web_safe.py

# Legacy test files (if available)
python test_app.py
python simple_test.py
python test_fixes.py
python test_real_browser.py
```

## Architecture Overview

The project uses a dual-crawler architecture with multiple AI analysis models:

### Core Components

1. **Crawler System** (`crawler/`):
   - **Enhanced Crawler Manager** (`enhanced_crawler_manager.py`): High-level orchestration with performance monitoring (推荐)
   - **Large-Scale Crawler** (`large_scale_crawler.py`): Handles 50-100+ job listings with intelligent batching
   - **Real Playwright Engine** (`real_playwright_spider.py`): Direct Playwright API with session management
   - **Smart Components**: Smart selector (`smart_selector.py`), enhanced extractor (`enhanced_extractor.py`)
   - **MCP Engine** (`mcp_client.py`, `advanced_mcp_client.py`): AI-driven browser automation (实验性)
   - **Unified Interface** (`unified_crawler_interface.py`): Single entry point supporting multiple engines
   - **Supporting Services**: Session management, retry handling, performance monitoring, concurrent processing

2. **AI Analysis System** (`analyzer/`):
   - **AI Client Factory** (`ai_client_factory.py`): Multi-provider support with dynamic model selection
   - **Supported Providers**: DeepSeek (default, cost-effective), Claude (high quality), Gemini (balanced)
   - **Job Analyzer** (`job_analyzer.py`): Unified analysis interface with 1-10 scoring system
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
3. Unified crawler interface selects appropriate engine (Enhanced/Real Playwright/MCP)
4. Crawler fetches job listings with session management and anti-detection
5. AI analyzer processes job descriptions using selected provider (DeepSeek/Claude/Gemini)
6. Jobs scored 1-10 based on user preferences and job match criteria
7. Results streamed in real-time via WebSocket to web interface
8. Final data persisted to `data/job_results.json` with metadata

## Configuration Requirements

### API Keys (config/secrets.env)
```bash
DEEPSEEK_API_KEY=sk-xxx    # Required for AI analysis
CLAUDE_API_KEY=sk-ant-xxx  # Optional
GEMINI_API_KEY=xxx         # Optional
```

### User Preferences (config/user_preferences.yaml)
- **Search Configuration**: Keywords, cities, job count limits, crawler engine selection
- **AI Analysis**: Provider selection (deepseek/claude/gemini), minimum score threshold, analysis depth
- **Personal Profile**: Skills, experience, salary expectations, company preferences
- **UI Preferences**: Theme, language, display options, notification settings

## Important Implementation Details

1. **Multi-Engine Architecture**: Enhanced Crawler Manager orchestrates multiple engines with automatic fallback
2. **Large-Scale Processing**: Supports 50-100+ job listings (upgraded from 20-job limit) with intelligent batching
3. **Smart Data Extraction**: Multi-stage extraction with 90%+ success rate and adaptive CSS selectors
4. **Session Persistence**: Automatic cookie and session management with 7-day persistence (`crawler/sessions/`)
5. **AI Cost Optimization**: Intelligent caching system with batch processing (5 jobs/API call) achieving 70-85% cost savings
6. **Anti-Detection System**: Human-like behavior simulation, random delays, smart element selection
7. **Performance Monitoring**: Real-time system resource monitoring with bottleneck detection
8. **Concurrent Processing**: Async task scheduling with browser instance pooling (5x performance improvement)
9. **Error Recovery**: Multi-strategy retry system with 95% recovery rate and intelligent fallback
10. **Real-time Communication**: WebSocket-based progress updates with detailed status information

## Common Development Tasks

**Crawler System Modifications**:
- Enhanced crawler: Update `crawler/enhanced_crawler_manager.py` (recommended entry point)
- Large-scale processing: Modify `crawler/large_scale_crawler.py` for 50-100+ job handling
- Smart extraction: Update `crawler/enhanced_extractor.py` and `crawler/smart_selector.py`  
- Real Playwright: Modify `crawler/real_playwright_spider.py` for direct Playwright features
- MCP integration: Update `crawler/mcp_client.py` or `crawler/advanced_mcp_client.py`
- Add new engines: Register in `crawler/unified_crawler_interface.py`

**AI Analysis Enhancements**:
- New AI providers: Create client in `analyzer/` following existing pattern, register in `ai_client_factory.py`
- Job requirement analysis: Modify `analyzer/job_requirement_summarizer.py` for structured analysis
- Analysis logic: Modify `analyzer/job_analyzer.py` for scoring algorithms  
- Prompt engineering: Update templates in `analyzer/prompts/`
- Market analysis: Enhance `analyzer/market_analyzer.py`
- Cost optimization: Update caching logic and batch processing strategies

**Configuration Changes**:
- App settings: Edit `config/app_config.yaml`
- User preferences: Update `config/user_preferences.yaml` structure
- Configuration logic: Modify `config/config_manager.py`

**Frontend Development**:
- Embedded UI: Backend serves UI directly from `backend/app.py` (lines 71+)
- React development: Use separate React app in `frontend/` for complex changes
- Real-time features: Update WebSocket handlers in both backend and frontend