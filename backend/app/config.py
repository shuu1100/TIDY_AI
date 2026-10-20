"""Configuration management for TidyAI backend."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""
    
    # Server binding (strictly local)
    host: str = "127.0.0.1"
    port: int = 8765
    debug: bool = False
    
    # Local Ollama AI settings
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout_seconds: float = 15.0
    
    # Local SQLite Database
    database_path: str = "tidy_ai.db"
    
    # Frontend origin for CORS
    frontend_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
