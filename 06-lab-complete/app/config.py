from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os

class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    environment: str = "development"
    debug: bool = False
    
    # App
    app_name: str = "Smart Travel Assistant"
    app_version: str = "1.0.0"
    
    # LLM & Agent Config
    MODEL_NAME: str = "gemini-2.5-flash"
    GEMINI_API_KEY: str = ""
    TEMPERATURE: float = 0.7
    USE_TOOLS: bool = True
    
    # Tool Keys
    OPENWEATHER_API_KEY: Optional[str] = None
    EXCHANGERATE_API_KEY: Optional[str] = None
    RAPIDAPI_KEY: Optional[str] = None
    SERPAPI_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    
    # Security
    agent_api_key: str = "lab-secret-key-123"
    jwt_secret: str = "dev-jwt-secret"
    allowed_origins: List[str] = ["*"]
    
    # Rate Limiting & Budgeting
    rate_limit_per_minute: int = 10
    monthly_budget_usd: float = 10.0
    
    # Storage
    redis_url: str = "redis://localhost:6379/0"
    
    model_config = SettingsConfigDict(
        # Try to find .env in current dir or parent dir
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
