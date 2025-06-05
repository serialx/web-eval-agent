# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

web-eval-agent is an MCP (Model Context Protocol) server that enables AI agents to autonomously test web applications. It provides browser automation, network/console monitoring, and UX evaluation capabilities through a real-time dashboard.

## Key Commands

### Development Setup
```bash
# Install dependencies (requires UV package manager)
uv pip install -r requirements.txt

# Install Playwright browsers
uvx --with playwright playwright install --with-deps

# Run the MCP server
python webEvalAgent/mcp_server.py

# Clean build artifacts
./clear.sh
```

### Linting
```bash
# Run Ruff linter (configured in GitHub Actions)
ruff check .
```

## Architecture Overview

The codebase follows a modular architecture centered around MCP server integration:

1. **MCP Server Entry Point** (`webEvalAgent/mcp_server.py`)
   - Validates API keys via `src/api_utils.py`
   - Exposes two tools: `web_eval_agent` and `setup_browser_state`
   - Routes requests to tool handlers

2. **Browser Automation Layer**
   - `src/browser_manager.py`: Singleton managing Playwright browser lifecycle and CDP screencasting
   - `src/browser_utils.py`: Core automation logic using browser-use library with LangChain/Anthropic integration
   - `src/tool_handlers.py`: Implements evaluation logic and result formatting

3. **Real-time Dashboard**
   - `src/log_server.py`: Flask/SocketIO server for log streaming and browser control
   - `templates/static/index.html`: Web UI for monitoring evaluations and screencasting
   - `src/agent_overlay.js`: Browser overlay for visual feedback

4. **AI Integration**
   - Uses browser-use framework with LangChain for autonomous browser control
   - Supports Anthropic Claude and Google Gemini models
   - Evaluation prompts defined in `src/prompts.py`

## Important Implementation Details

- Browser state is managed as a singleton to prevent multiple instances
- Console logs and network requests are captured via CDP and filtered for relevance
- Screenshots are automatically captured during evaluation
- The dashboard provides bidirectional communication for manual browser intervention

## Environment Variables

- `ANTHROPIC_API_KEY`: Required for AI model access (standard Anthropic API key)