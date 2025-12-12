# AI Skills Development Pipeline

A sophisticated web-based system that generates advanced AI agent skills through iterative refinement. The system runs a 3-stage pipeline combining multiple AI models to research, analyze, and create structured skill templates.

## Features

- **Multi-Stage Pipeline**: Research → Analysis → Template Generation
- **Iterative Refinement**: Automatically improve templates based on analysis
- **Interactive Web UI**: Clean, responsive interface for managing the pipeline
- **Template Editor**: Live preview and editing capabilities
- **Export Options**: Download individual templates or complete pipeline runs
- **Version History**: Track iterations and improvements over time

## Quick Start

### Prerequisites

- [UV](https://github.com/astral-sh/uv) - Python package installer
- OpenRouter API key (sign up at [openrouter.ai](https://openrouter.ai))

### Installation

1. **Install UV** (if not already installed)
   ```bash
   # On macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # On Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

   # Or with pip
   pip install uv
   ```

2. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd skills_FFT
   ```

3. **Install dependencies with UV**
   ```bash
   # Install and create virtual environment
   uv sync

   # Or explicitly
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=your_api_key_here
   ```

5. **Run the application**
   ```bash
   uv run app.py
   ```

6. **Open in browser**
   Navigate to [http://localhost:5001](http://localhost:5001)

## Usage

### Generating a Skill Template

1. Enter your query in the main interface (e.g., "Research quantum computing optimization techniques")
2. Click "Start Pipeline" to begin the 3-stage process
3. Wait for the pipeline to complete
4. Review the generated template
5. Optionally iterate to refine further (if new instructions are generated)

### Working with Templates

- **Preview**: Click "Preview & Edit" to view and modify the template
- **Export**: Download templates as ZIP files
- **History**: View all previous iterations and improvements
- **Management**: List, preview, and delete generated templates

## Architecture

### Pipeline Stages

1. **Domain Research** (Perplexity Llama 3.1 Sonar)
   - Comprehensive research on the topic
   - Identifies key concepts, methodologies, and applications
   - Provides reference sources and further reading

2. **Deep Analysis** (DeepSeek Coder V2)
   - Critical analysis of research findings
   - Identifies issues, shortcomings, and gaps
   - Suggests enhancements and improvements
   - Generates new research instructions if needed

3. **Template Generation** (DeepSeek Coder V2)
   - Creates structured skill templates
   - Includes YAML metadata with proper formatting
   - Provides clear instructions and examples

### Data Structure

Generated templates are stored in `skills_output/` with the following structure:

```
skills_output/
└── YYYY-MM-DD_HH-MM-SS/
    ├── skill.md              # Final template
    ├── metadata.json         # Pipeline information
    ├── iteration_1/          # First iteration
    │   ├── research.md
    │   ├── analysis.md
    │   ├── template.md
    │   └── instruction.txt
    └── iteration_2/          # Second iteration (if applicable)
```

## API Reference

### Pipeline Endpoints

- `POST /api/pipeline/start`
  - Start a new pipeline run
  - Body: `{"query": "your query here"}`

- `POST /api/pipeline/iterate`
  - Run an iteration of the pipeline
  - Body: `{"session_id": "session-id"}`

### Template Endpoints

- `GET /api/templates`
  - List all generated templates

- `GET /api/template/<timestamp>`
  - Get specific template content

- `POST /api/template/<timestamp>/save`
  - Save edited template
  - Body: `{"content": "template content"}`

- `GET /api/template/<timestamp>/export`
  - Download template as ZIP
  - Query: `?type=template` or `?type=full`

- `DELETE /api/template/<timestamp>`
  - Delete a template and all files

## Configuration

### Environment Variables

- `OPENROUTER_API_KEY` (required): Your OpenRouter API key
- `FLASK_ENV`: Environment (default: development)
- `FLASK_DEBUG`: Debug mode (default: True)
- `SECRET_KEY`: Flask secret key

### Model Configuration

Models can be configured in `config.py`:

```python
RESEARCH_MODEL = "perplexity/llama-3.1-sonar-large-128k-online"
ANALYSIS_MODEL = "deepseek/deepseek-coder-v2"
TEMPLATE_MODEL = "deepseek/deepseek-coder-v2"
MAX_ITERATIONS = 3
```

## Testing

Run the test suite with UV:

```bash
# Run all tests
uv run pytest tests/

# Run with coverage
uv run pytest --cov=. tests/

# Run specific test file
uv run pytest tests/test_pipeline.py

# Install test dependencies first (if needed)
uv sync --group test
```

### Development Tools

UV provides integrated development tool support:

```bash
# Format code
uv run black .
uv run isort .

# Lint code
uv run flake8 .

# Type checking
uv run mypy .

# Run pre-commit hooks
uv run pre-commit run --all-files
```

## Development

### Project Structure

```
skills_FFT/
├── app.py                 # Main Flask application
├── config.py              # Configuration management
├── pipeline.py            # Pipeline logic
├── requirements.txt       # Python dependencies
├── templates/             # Jinja2 HTML templates
├── static/                # CSS, JavaScript, images
├── utils/                 # Utility modules
├── tests/                 # Test files
└── skills_output/         # Generated templates (git-ignored)
```

### Adding New Models

To add a new model to the pipeline:

1. Update `config.py` with the model name
2. Modify the appropriate stage function in `pipeline.py`
3. Update prompts as needed for the new model

### Customizing Prompts

Prompts are defined in `pipeline.py` in each stage function:
- `run_research()`: Research prompt
- `run_analysis()`: Analysis prompt
- `run_template_generation()`: Template generation prompt

## Troubleshooting

### Common Issues

1. **API Key Error**
   - Ensure `OPENROUTER_API_KEY` is set correctly
   - Verify the key has access to the required models

2. **Pipeline Timeout**
   - Increase timeout in `pipeline.py` if needed
   - Check network connectivity

3. **Template Not Found**
   - Verify the timestamp is correct
   - Check `skills_output/` directory

### Debug Mode

Enable debug mode by setting:
```
FLASK_DEBUG=True
```

This will provide detailed error messages and auto-reload on code changes.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [OpenRouter](https://openrouter.ai) for providing access to multiple AI models
- [Flask](https://flask.palletsprojects.com) for the web framework
- The open-source community for various tools and libraries

## Support

For support, please:
1. Check the troubleshooting section
2. Search existing issues
3. Create a new issue with details about your problem

---

**Note**: This tool requires an active OpenRouter API subscription and may incur costs based on usage.