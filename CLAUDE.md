# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI Skills Development Pipeline System that generates advanced Anthropic-style agent skills through iterative refinement. The system runs a 3-stage pipeline:

1. **Domain Research** - Uses Perplexity's Llama 3.1 Sonar model for comprehensive research
2. **Deep Analysis** - Uses DeepSeek Coder V2 to analyze and identify improvements
3. **Template Generation** - Creates structured skill templates with YAML metadata

## Development Commands

### Setup with UV
```bash
# Install and create virtual environment
uv sync

# Or explicitly
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Set up environment variables
cp .env.example .env
# Edit .env with your OpenRouter API key
```

### Running the Application
```bash
# Development server
uv run app.py

# Or with Flask
uv run flask run --debug
```

### Testing
```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_pipeline.py

# Run with coverage
uv run pytest --cov=. tests/

# Install test dependencies
uv sync --group test
```

### Development Tools
```bash
# Format code
uv run black .
uv run isort .

# Lint code
uv run flake8 .

# Type checking
uv run mypy .

# Install dev dependencies
uv sync --group dev
```

## Architecture

### Core Components

1. **Flask App (`app.py`)**
   - Web server and API endpoints
   - Session management for pipeline state
   - RESTful API for pipeline operations

2. **Pipeline Module (`pipeline.py`)**
   - `AIPipeline` class manages the 3-stage process
   - `PipelineState` class tracks iteration state
   - OpenRouter API integration

3. **Configuration (`config.py`)**
   - Environment variable handling with python-dotenv
   - Model configuration and parameters
   - Centralized settings management

4. **Utilities**
   - `utils/file_manager.py` - Template storage and retrieval
   - `utils/export.py` - Zip export functionality

### API Endpoints
- `POST /api/pipeline/start` - Initialize new pipeline run
- `POST /api/pipeline/iterate` - Run refinement iteration
- `GET /api/template/<timestamp>` - Retrieve template
- `POST /api/template/<timestamp>/save` - Save edited template
- `GET /api/template/<timestamp>/export` - Download as zip
- `GET /api/templates` - List all generated templates

### Data Flow
1. User submits query via web UI
2. Pipeline runs research → analysis → template generation
3. Results stored in timestamped directories under `skills_output/`
4. Users can preview, edit, and export templates
5. Iterations possible if analysis provides new instructions

## File Structure

```
skills_FFT/
├── app.py                     # Main Flask application
├── config.py                  # Configuration management
├── pipeline.py                # Pipeline logic
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
├── templates/                # Jinja2 templates
│   ├── index.html           # Main UI
│   └── preview.html         # Template editor
├── static/                   # Static assets
│   ├── css/style.css        # Stylesheets
│   └── js/                  # JavaScript
│       ├── main.js          # UI logic
│       └── editor.js        # Editor functionality
├── utils/                    # Utility modules
├── tests/                    # Test files
└── skills_output/            # Generated templates (git-ignored)
```

## Important Notes

### API Key Configuration
- Requires `OPENROUTER_API_KEY` environment variable
- Can be set in `.env` file or directly as environment variable
- Key must have access to the specified models

### Model Configuration
- Research: `perplexity/llama-3.1-sonar-large-128k-online`
- Analysis: `deepseek/deepseek-coder-v2`
- Template: `deepseek/deepseek-coder-v2`
- Max iterations: 3 (configurable)

### State Management
- Pipeline runs use session IDs for tracking
- Active sessions stored in memory (development)
- Production should use Redis or proper session store

### Template Format
Generated templates include:
- YAML front matter with metadata
- Skill description and usage
- Implementation instructions
- Example interactions

## Testing

- Unit tests in `tests/test_pipeline.py` for pipeline logic
- Integration tests in `tests/test_app.py` for Flask routes
- Mock API responses for reliable testing
- Run tests before committing changes

## Security Considerations

- Sanitize all user inputs
- Validate API responses
- Rate limiting for API endpoints
- Secure handling of API keys
- XSS protection in template rendering