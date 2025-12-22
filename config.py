import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    """Application configuration class"""

    # OpenRouter API Configuration
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

    # Model Configuration
    RESEARCH_MODEL = "x-ai/grok-4.1-fast"  # Using Grok for research
    ANALYSIS_MODEL = "deepseek/deepseek-v3.2"
    TEMPLATE_MODEL = "deepseek/deepseek-v3.2"

    # Alternative Models (for fallback)
    FALLBACK_RESEARCH_MODELS = [
        "openai/gpt-4o",
        "anthropic/claude-3-opus",
        "google/gemini-pro"
    ]

    # Web Search Configuration
    WEB_SEARCH_ENABLED = os.environ.get('WEB_SEARCH_ENABLED', 'True').lower() == 'true'
    PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')
    TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')
    # Web Search Provider Priority: 1=Tavily, 2=Perplexity, 3=OpenRouter
    WEB_SEARCH_PROVIDER = os.environ.get('WEB_SEARCH_PROVIDER', 'tavily')  # tavily, perplexity, openrouter
    WEB_SEARCH_PRIORITY = ['tavily', 'perplexity', 'openrouter']

    # Pipeline Configuration
    MAX_ITERATIONS = 9
    MAX_TOKENS_RESEARCH = 4096
    MAX_TOKENS_ANALYSIS = 8192
    MAX_TOKENS_TEMPLATE = 4096

    # Default Parameters
    DEFAULT_TEMPERATURE = 0.7
    ANALYSIS_TEMPERATURE = 0.3

    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # File Storage
    SKILLS_OUTPUT_DIR = 'skills_output'

    # File System Access Configuration
    ALLOWED_READ_PATHS = [
        'examples/',
        'docs/',
        'templates/',
        'skills_output/',
        'utils/'
    ]

    ALLOWED_WRITE_PATHS = [
        'skills_output/',
        'temp/',
        'cache/'
    ]

    MAX_FILE_SIZE_MB = 10

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")

        # Validate web search configuration
        if cls.WEB_SEARCH_ENABLED:
            if cls.WEB_SEARCH_PROVIDER == 'perplexity' and not cls.PERPLEXITY_API_KEY:
                raise ValueError("PERPLEXITY_API_KEY is required when using Perplexity for web search")
            elif cls.WEB_SEARCH_PROVIDER == 'tavily' and not cls.TAVILY_API_KEY:
                raise ValueError("TAVILY_API_KEY is required when using Tavily for web search")

        return True
