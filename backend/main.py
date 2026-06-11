"""
智能息肉诊疗辅助平台 - 主入口
FastAPI应用启动文件
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.api.v1 import examinations, patients, llm_analysis
from app.core.config import settings
from app.core.database import init_db
from app.services.model_service import ModelService

# 全局模型服务实例
model_service = None
db_connected = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global model_service, db_connected

    print("=" * 60)
    print("启动智能息肉诊疗辅助平台")
    print("=" * 60)

    # 初始化数据库
    try:
        await init_db()
        db_connected = True
        print("数据库连接成功")
    except Exception as e:
        db_connected = False
        print(f"数据库初始化失败: {str(e)}")

    # 加载BFNet模型
    model_service = ModelService()
    # 注入到examinations路由中
    import app.services.model_service as ms
    ms.model_service = model_service

    try:
        model_service.load_model()
        print("BFNet模型加载成功")
    except Exception as e:
        print(f"模型加载失败: {str(e)}")
        print("   继续启动（演示模式）")

    print("平台启动成功")
    print(f"API文档: http://localhost:{settings.PORT}/docs")
    print("=" * 60)

    yield

    # 关闭时清理
    if model_service:
        model_service.unload_model()


# 创建FastAPI应用
app = FastAPI(
    title="智能息肉诊疗辅助平台API",
    description="基于BFNet分割算法 + LLM医学增强的完整临床系统",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(examinations.router, prefix="/api/v1/examinations", tags=["检查管理"])
app.include_router(patients.router, prefix="/api/v1/patients", tags=["患者管理"])
app.include_router(llm_analysis.router, prefix="/api/v1/analysis", tags=["智能分析"])

# 挂载上传目录为静态文件
upload_dir = os.path.join(os.path.dirname(__file__), "data", "uploads")
os.makedirs(upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")


@app.get("/")
async def root():
    return {
        "message": "智能息肉诊疗辅助平台API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model": "loaded" if model_service and model_service.model else "not_loaded",
        "database": "connected" if db_connected else "disconnected",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
