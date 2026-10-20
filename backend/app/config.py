import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_ollama_base_url() -> str:
    """Return default local Ollama base URL depending on execution environment.

    Native Windows backend uses http://127.0.0.1:11434.
    If running inside a Docker container, host.docker.internal is used by default.
    """
    is_docker = (
        Path("/.dockerenv").exists()
        or os.environ.get("DOCKER_CONTAINER") == "1"
        or os.environ.get("CONTAINER") == "docker"
    )
    if is_docker:
        return "http://host.docker.internal:11434"
    return "http://127.0.0.1:11434"


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""
    
    # Server binding (strictly local)
    host: str = "127.0.0.1"
    port: int = 8765
    debug: bool = False
    
    # Local Ollama AI settings
    ollama_base_url: str = get_default_ollama_base_url()
    ollama_model: str = "qwen3:4b"
    ollama_connect_timeout_seconds: float = 5.0
    ollama_read_timeout_seconds: float = 90.0
    ollama_timeout_seconds: float = 90.0
    
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

