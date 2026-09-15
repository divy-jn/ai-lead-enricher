"""
config.py — Application settings loaded from environment variables.

Uses pydantic-settings for typed, validated configuration with .env support.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment / .env file."""

    # LLM
    llm_api_key: str = ""
    llm_base_url: str = "https://ollama.com/v1"
    llm_model: str = "gpt-oss:120b-cloud"
    llm_timeout_s: int = 120
    llm_max_retries: int = 3

    # Browser
    browser_headless: bool = True
    browser_timeout_ms: int = 30_000

    # Crawler
    max_crawl_pages: int = 8

    # Preprocessing
    max_text_chars: int = 15_000

    # Logging
    log_level: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


# Singleton instance — import this throughout the project.
settings = Settings()
