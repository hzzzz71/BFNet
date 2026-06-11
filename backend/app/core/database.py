"""
数据库连接管理
使用SQLAlchemy 2.0异步引擎
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy import text
from app.core.config import settings


def normalize_database_url(raw_url: str) -> str:
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://")
    return raw_url


def build_engine(target_url: str):
    engine_kwargs = {"echo": settings.DEBUG}
    if not target_url.startswith("sqlite+aiosqlite://"):
        engine_kwargs.update(
            {
                "poolclass": AsyncAdaptedQueuePool,
                "pool_size": 20,
                "max_overflow": 0,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
                "connect_args": {"timeout": 10},
            }
        )
    return create_async_engine(target_url, **engine_kwargs)


def build_session_factory(db_engine):
    return sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


database_url = normalize_database_url(settings.DATABASE_URL)
fallback_database_url = "sqlite+aiosqlite:///./polyp_ai.db"
active_database_url = database_url
engine = build_engine(active_database_url)
AsyncSessionLocal = build_session_factory(engine)

# 创建ORM基类
Base = declarative_base()


async def get_db():
    """依赖注入: 获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库 - 创建所有表"""
    global engine, AsyncSessionLocal, active_database_url
    try:
        async with engine.begin() as conn:
            from app.models import patient, patient_report, examination, polyp, followup
            await conn.run_sync(Base.metadata.create_all)
            await _ensure_patient_detail_columns(conn)
            await _ensure_examination_review_columns(conn)
    except Exception:
        if active_database_url == fallback_database_url:
            raise
        active_database_url = fallback_database_url
        engine = build_engine(active_database_url)
        AsyncSessionLocal = build_session_factory(engine)
        async with engine.begin() as conn:
            from app.models import patient, patient_report, examination, polyp, followup
            await conn.run_sync(Base.metadata.create_all)
            await _ensure_patient_detail_columns(conn)
            await _ensure_examination_review_columns(conn)


async def _ensure_patient_detail_columns(conn):
    dialect = conn.engine.dialect.name
    if dialect == "postgresql":
        await conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS allergies TEXT"))
        await conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS family_history TEXT"))
        return

    try:
        await conn.execute(text("ALTER TABLE patients ADD COLUMN allergies TEXT"))
    except Exception:
        pass
    try:
        await conn.execute(text("ALTER TABLE patients ADD COLUMN family_history TEXT"))
    except Exception:
        pass


async def _ensure_examination_review_columns(conn):
    dialect = conn.engine.dialect.name
    if dialect == "postgresql":
        await conn.execute(text("ALTER TABLE examinations ADD COLUMN IF NOT EXISTS doctor_confirmed_report JSONB"))
        await conn.execute(text("ALTER TABLE examinations ADD COLUMN IF NOT EXISTS doctor_reviewed BOOLEAN DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE examinations ADD COLUMN IF NOT EXISTS doctor_reviewed_at TIMESTAMP WITH TIME ZONE"))
        await conn.execute(text("ALTER TABLE examinations ADD COLUMN IF NOT EXISTS llm_model_key VARCHAR(50)"))
        await conn.execute(text("ALTER TABLE examinations ADD COLUMN IF NOT EXISTS llm_model_id VARCHAR(100)"))
        return

    try:
        await conn.execute(text("ALTER TABLE examinations ADD COLUMN doctor_confirmed_report JSON"))
    except Exception:
        pass
    try:
        await conn.execute(text("ALTER TABLE examinations ADD COLUMN doctor_reviewed BOOLEAN DEFAULT 0"))
    except Exception:
        pass
    try:
        await conn.execute(text("ALTER TABLE examinations ADD COLUMN doctor_reviewed_at DATETIME"))
    except Exception:
        pass
    try:
        await conn.execute(text("ALTER TABLE examinations ADD COLUMN llm_model_key VARCHAR(50)"))
    except Exception:
        pass
    try:
        await conn.execute(text("ALTER TABLE examinations ADD COLUMN llm_model_id VARCHAR(100)"))
    except Exception:
        pass


async def drop_db():
    """删除所有表 (测试用)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
