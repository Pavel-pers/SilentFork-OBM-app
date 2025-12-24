import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.main import create_app
from app.infra.db import get_db
from app.models.base import Base
import app.models
from app.models.user import User, UserRole
from app.features.auth.dependencies import get_current_user

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://app:app@localhost:5432/app"
)


@pytest.fixture
async def engine():
    engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()



@pytest.fixture
async def db(engine):
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        if engine.dialect.name == "sqlite":
            # SQLite не поддерживает TRUNCATE, чистим таблицы вручную
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(table.delete())
            await session.commit()
        else:
            tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
            if tables:
                await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE;"))
                await session.commit()
        yield session

@pytest.fixture
def client(engine, db):
    app = create_app()
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)

@pytest.fixture
def auth_client(db):
    app_instance = create_app()
    mock_user = MagicMock()
    mock_user.user_id = 1
    mock_user.email = "test@example.com"
    mock_user.role = "CLIENT"
    async def mock_get_current_user(access_token=None, db=None):
        return mock_user
    async def override_get_db():
        yield db
    app_instance.dependency_overrides[get_current_user] = mock_get_current_user
    app_instance.dependency_overrides[get_db] = override_get_db
    with TestClient(app_instance) as test_client:
        yield test_client
    app_instance.dependency_overrides.clear()


@pytest.fixture
async def async_app_client():
    """
    Async клиент и sessionmaker для случаев, когда нужен один event loop
    (например, е2е-тесты с асинхронными роутами).
    """
    engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        if tables:
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE;"))

    app = create_app()

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, SessionLocal

    app.dependency_overrides.clear()
    await engine.dispose()
