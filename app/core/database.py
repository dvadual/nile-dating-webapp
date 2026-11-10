import os
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()


class Base(DeclarativeBase):
    pass


def _database_url() -> URL:
    configured_url = os.getenv("DATABASE_URL")
    if not configured_url:
        if os.getenv("APP_ENV", "development").lower() in {"prod", "production"}:
            raise RuntimeError("DATABASE_URL must be configured in production.")
        configured_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/nile_dating"
    url = make_url(configured_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")
    if url.drivername != "postgresql+asyncpg":
        raise ValueError("DATABASE_URL must use PostgreSQL with the asyncpg driver.")
    return url


DATABASE_URL = _database_url()
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"ssl": "require", "statement_cache_size": 0},
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
