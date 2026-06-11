"""
Configuration management for the application
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # API Configuration
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    MODEL_NAME: str = "gpt-3.5-turbo"
    
    # Embedding Model Configuration (SiliconFlow)
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_API_BASE: str = "https://api.siliconflow.cn/v1"
    EMBEDDING_MODEL: str = "Qwen/Qwen3-VL-Embedding-8B"

    # Reranker Configuration (reuses embedding API key/base)
    RERANK_ENABLED: bool = False
    RERANK_MODEL: str = "Qwen/Qwen3-VL-Reranker-8B"
    RERANK_CANDIDATES: int = 30
    RERANK_TOP_N: int = 8
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./boardgames.db"
    VECTOR_DB_PATH: str = "./data/vector_db"
    
    # File Upload Configuration
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 52428800  # 50MB
    ALLOWED_EXTENSIONS: str = "pdf"
    
    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    
    # Processing Configuration
    CHUNK_SIZE: int = 900
    CHUNK_OVERLAP: int = 180
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Create necessary directories
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.VECTOR_DB_PATH, exist_ok=True)
