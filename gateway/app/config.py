"""
Application configuration using Pydantic Settings.
Loads from environment variables and .env file.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "AI Assistant Gateway"
    debug: bool = True
    
    # Supabase Configuration
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_anon_key: str = ""  # Set via SUPABASE_ANON_KEY env var
    supabase_service_role_key: str = ""  # Set via SUPABASE_SERVICE_ROLE_KEY env var
    
    # JWT Configuration (for local Supabase, this is the default secret)
    jwt_secret: str = ""  # Set via JWT_SECRET env var
    jwt_algorithm: str = "HS256"
    
    # Inference Endpoints (to be configured later)
    inference_instant_url: str = ""
    inference_thinking_url: str = ""
    
    # Database URL (for direct connections if needed)
    database_url: str = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
