"""
系统配置管理
使用pydantic-settings管理环境变量
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "智能息肉诊疗辅助平台"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS配置
    ALLOWED_HOSTS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]
    
    # 数据库配置
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/polyp_ai_db"
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379"
    
    # MinIO配置
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "polyp-images"
    MINIO_SECURE: bool = False
    
    # BFNet模型配置
    MODEL_PATH: str = "../BFNet/model/BFNet.pth"
    MODEL_PVT_PATH: str = "../BFNet/pvt_v2_b2.pth"
    MODEL_DEVICE: str = "cuda"  # or "cpu"
    MODEL_IMAGE_SIZE: int = 704
    
    # LLM配置
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    DEFAULT_LLM_MODEL_KEY: str = "deepseek_chat"
    SILICONFLOW_KIMI_MODEL_ID: str = ""
    SILICONFLOW_GLM_MODEL_ID: str = ""
    LLM_TEMPERATURE: float = 0.3
    LLM_TIMEOUT_SECONDS: float = 300.0

    # Supabase配置
    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_SECRET_KEY: str = ""
    
    # 文件上传限制
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_IMAGE_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".tiff", ".bmp"]
    ALLOWED_VIDEO_EXTENSIONS: List[str] = [".mp4", ".avi", ".mov", ".wmv"]
    
    # JWT配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()
