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

# Stop all running processes
python stop_all.py
```

### Testing

```bash
# Run test applications
python test_app.py
python simple_test.py
python test_fixes.py
python test_real_browser.py
```

## Architecture Overview

The project uses a dual-crawler architecture with multiple AI analysis models:

### Core Components

1. **Playwright-Based Crawlers** (`crawler/`):
   - **Real Playwright Engine** (`real_playwright_spider.py`): Modern, high-performance web scraping using native Playwright API (推荐)
   - **Playwright MCP Engine** (`mcp_client.py`): AI-driven browser automation through MCP protocol (实验性)
   - Unified interfaces for both engines

2. **AI Analysis System** (`analyzer/`):
   - Factory pattern (`ai_client_factory.py`) supports multiple AI providers
   - DeepSeek (default, cost-effective), Claude (high quality), Gemini (balanced)
   - Unified analysis interface via `job_analyzer.py`
   - Scoring system: 1-10 points based on job match criteria

3. **Web Application** (`backend/app.py`):
   - Flask + SocketIO for real-time communication
   - Embedded frontend (Apple-style UI) served directly from Flask
   - WebSocket events for progress updates
   - RESTful API endpoints for configuration and search

4. **Configuration Management** (`config/`):
   - Three-layer configuration: `secrets.env` (API keys), `app_config.yaml` (app settings), `user_preferences.yaml` (user preferences)
   - Dynamic configuration through web interface
   - ConfigManager handles all configuration loading and validation

### Data Flow

1. User configures search parameters via web interface
2. Selected crawler engine (Real Playwright/MCP) fetches job listings
3. AI model analyzes job descriptions and scores them
4. Results are displayed in real-time via WebSocket
5. Data saved to `data/job_results.json`

## Configuration Requirements

### API Keys (config/secrets.env)
```bash
DEEPSEEK_API_KEY=sk-xxx    # Required for AI analysis
CLAUDE_API_KEY=sk-ant-xxx  # Optional
GEMINI_API_KEY=xxx         # Optional
```

### User Preferences (config/user_preferences.yaml)
- Search keywords, cities, job count limits
- AI provider selection and minimum score threshold
- Spider engine choice (playwright/mcp)

## Important Implementation Details

1. **Playwright Integration**: The Real Playwright engine provides high-performance, modern web automation
2. **MCP Integration**: The MCP client requires the MCP server to be installed via Claude Code (optional)
3. **Cookie Management**: Automatic cookie persistence and session management
4. **Anti-Detection**: Advanced evasion techniques and human-like behavior simulation
5. **Error Handling**: Comprehensive try-catch blocks with intelligent fallback strategies
5. **Real-time Updates**: WebSocket emits progress at each stage of crawling and analysis

## Common Development Tasks

When modifying the crawler engines:
- Real Playwright crawler: Update `crawler/real_playwright_spider.py`
- MCP crawler: Update `crawler/mcp_client.py`

When adding new AI providers:
- Create new client in `analyzer/` following existing pattern
- Register in `ai_client_factory.py`
- Update configuration options

When updating the UI:
- Frontend code is embedded in `backend/app.py` (lines 71-end)
- For complex changes, use the separate React app in `frontend/`