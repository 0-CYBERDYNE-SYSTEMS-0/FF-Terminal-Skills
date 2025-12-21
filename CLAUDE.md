# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI Skills Development Pipeline System that generates advanced AI agent skills through iterative refinement. The system combines multiple AI models via OpenRouter to research, analyze, and create structured skill templates with YAML metadata. A Flask web UI enables users to run pipelines, preview results, edit templates, and export outputs.

## Development Commands

### Setup
```bash
# Install dependencies using UV
uv sync

# Activate virtual environment (optional)
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate    # Windows

# Configure environment
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY
```

### Running
```bash
# Development server (includes Flask hot-reload)
uv run app.py

# Server runs on http://localhost:5001
```

### Testing & Code Quality
```bash
# Run all tests
uv run pytest tests/

# Run specific test file or test function
uv run pytest tests/test_pipeline.py
uv run pytest tests/test_pipeline.py::TestAIPipeline::test_call_model

# Format code
uv run black .
uv run isort .

# Lint and type checking
uv run flake8 .
uv run mypy .
```

## Architecture

### Core Pipeline Design

The system executes a 3-stage pipeline for each query:

1. **Research Stage** (`run_research()`)
   - Model: Grok-4.1-fast (currently configured)
   - Queries web search for domain information
   - Produces comprehensive background context

2. **Analysis Stage** (`run_analysis()`)
   - Model: DeepSeek V3.2
   - Critically evaluates research findings
   - Identifies improvements and gaps
   - May generate instructions for further research

3. **Template Generation Stage** (`run_template_generation()`)
   - Model: DeepSeek V3.2
   - Creates YAML-structured skill template
   - Includes metadata, instructions, and examples

Iterations repeat steps 1-3 if the analysis generates new instructions (up to MAX_ITERATIONS=3).

### Component Interactions

**Pipeline Flow:**
- User submits query via web UI (`app.py` → `/api/pipeline/start`)
- `AIPipeline.run()` executes the 3-stage pipeline
- Results stored in `skills_output/{TIMESTAMP}/`
- Web UI fetches updates via `/api/logs` (streaming logs)
- Users can preview, edit, and export results

**Web Search Integration:**
- `WebSearchManager` provides unified search interface across multiple providers
- Provider priority: Tavily → Perplexity → OpenRouter → Direct scraping
- Results cached for 1 hour to reduce API calls
- Configured via `WEB_SEARCH_PROVIDER` and related API keys

**Logging System:**
- `PipelineLogger` maintains per-session logs for real-time UI updates
- Logs include stage, level (debug/info/success/warning/error), and metadata
- Used by web UI's console.js to stream live pipeline progress

**File Management:**
- `EnhancedFileManager` handles organized storage under `skills_output/`
- Each run creates timestamped directory with iteration subdirectories
- Stores: research.md, analysis.md, template.md, instruction.txt, metadata.json
- Tracks pipeline state for resuming interrupted iterations

### Key Classes

- `PipelineState` - Tracks query, timestamp, iteration count, and outputs
- `AIPipeline` - Main orchestrator; calls models, manages state, handles iterations
- `WebSearchManager` - Unified search with provider fallback and caching
- `EnhancedFileManager` - Organized template storage and metadata tracking
- `PipelineLogger` - Session-based logging for real-time streaming

### API Endpoints

**Pipeline Operations:**
- `POST /api/pipeline/start` - Begin new pipeline run
- `POST /api/pipeline/iterate` - Execute next iteration (if instructions present)
- `GET /api/logs/<session_id>` - Stream logs for active session

**Template Management:**
- `GET /api/templates` - List all generated templates
- `GET /api/template/<timestamp>` - Retrieve template content
- `POST /api/template/<timestamp>/save` - Save edited template
- `GET /api/template/<timestamp>/export` - Download template(s) as ZIP
- `DELETE /api/template/<timestamp>` - Delete template and files

## Configuration & Environment

### Required Environment Variables
- `OPENROUTER_API_KEY` - Authentication for OpenRouter API (required)

### Optional Web Search Variables
- `WEB_SEARCH_ENABLED` - Enable web search (default: true)
- `WEB_SEARCH_PROVIDER` - Provider choice: `tavily` | `perplexity` | `openrouter` (default: tavily)
- `TAVILY_API_KEY` - Required if using Tavily
- `PERPLEXITY_API_KEY` - Required if using Perplexity

### Configurable Parameters (in `config.py`)
- Model selections: `RESEARCH_MODEL`, `ANALYSIS_MODEL`, `TEMPLATE_MODEL`
- Token limits: `MAX_TOKENS_*` for each stage
- Temperature: `DEFAULT_TEMPERATURE`, `ANALYSIS_TEMPERATURE`
- Max iterations: `MAX_ITERATIONS`

## Frontend & UI Details

### JavaScript Modules
- **main.js** - Pipeline UI, form submission, template listing/preview
- **console.js** - Live log streaming via EventSource, displays real-time pipeline progress
- **editor.js** - Template editing and preview functionality

### Real-Time Updates
The UI uses Server-Sent Events (SSE) via the `/api/logs/<session_id>` endpoint to stream pipeline logs in real-time. The console.js module listens to log events and updates the UI live.

## Data Storage Structure

```
skills_output/
└── YYYY-MM-DD_HH-MM-SS/          # Pipeline run timestamp
    ├── skill.md                   # Final generated template
    ├── metadata.json              # Pipeline metadata & state
    ├── iteration_1/               # First iteration
    │   ├── research.md           # Research stage output
    │   ├── analysis.md           # Analysis stage output
    │   ├── template.md           # Generated template
    │   └── instruction.txt       # New instructions (if applicable)
    └── iteration_2/               # Subsequent iteration (if applicable)
```

## Common Development Tasks

### Adding a New Model
1. Update `config.py` with new model identifier
2. Modify the appropriate stage function in `pipeline.py` (research/analysis/template)
3. Adjust prompts if needed for the new model's style
4. Test via the web UI

### Customizing Pipeline Prompts
Edit the prompt strings in pipeline.py:
- `run_research()` - Research/investigation prompt
- `run_analysis()` - Critical analysis prompt
- `run_template_generation()` - Skill template generation prompt

### Debugging Pipeline Issues
1. Check logs in browser console (real-time via /api/logs)
2. Enable DEBUG=True in Flask for detailed error output
3. Check `skills_output/` directory for partial outputs
4. Review OpenRouter API response in pipeline.py error handling

## Testing Notes

- Tests use mock OpenRouter responses to avoid API costs
- `test_pipeline.py` covers the 3-stage pipeline logic
- `test_app.py` covers Flask endpoints and file operations
- Run tests frequently during development to catch integration issues