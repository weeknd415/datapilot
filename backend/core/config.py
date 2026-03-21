"""Application configuration with environment variable support."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """DataPilot configuration loaded from environment variables."""

    # Application
    env: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    # LLM Providers (free tiers)
    groq_api_key: str = ""
    google_api_key: str = ""
    openai_api_base: str = "http://localhost:11434/v1"
    openai_api_key: str = "ollama"

    # Primary LLM config
    primary_model: str = "groq"  # groq, google, openai
    groq_model_name: str = "llama-3.3-70b-versatile"
    google_model_name: str = "gemini-2.0-flash"
    openai_model_name: str = "llama3.1"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/sample_db/business.db"

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma_db"

    # Agent settings
    sql_agent_confidence_threshold: float = 0.7
    document_agent_chunk_size: int = 512
    document_agent_chunk_overlap: int = 50
    max_retries: int = 3
    request_timeout: int = 30

    # MCP server ports
    mcp_sql_port: int = 8010
    mcp_document_port: int = 8011
    mcp_analytics_port: int = 8012

    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent
    data_dir: Path = Path(__file__).parent.parent.parent / "data"
    sample_docs_dir: Path = Path(__file__).parent.parent.parent / "data" / "sample_docs"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "allow"}


settings = Settings()
