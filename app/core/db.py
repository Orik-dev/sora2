from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.settings import settings


engine = create_async_engine(
    settings.SQLALCHEMY_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
