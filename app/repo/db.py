# app/repo/db.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import SessionLocal
from sqlalchemy.orm import declarative_base

Base = declarative_base()

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
