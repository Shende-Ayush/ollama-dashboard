"""
Test configuration and shared fixtures.

Industry-standard async test setup with:
- In-memory SQLite for fast isolated DB tests
- Mock Ollama client to avoid external dependencies
- Factory fixtures for test data generation
- Proper teardown and isolation between tests
"""
import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

# Override database URL BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.common.db.base import Base
from backend.common.db.session import get_db_session
from backend.main import app


# ---------------------------------------------------------------------------
# Event loop configuration
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=engine_test,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test and drop after."""
    # Register JSONB as JSON for SQLite compatibility
    from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
    from sqlalchemy import event

    @event.listens_for(engine_test.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    # Render JSONB as JSON and UUID as String for SQLite
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def compile_jsonb_sqlite(type_, compiler, **kw):
        return "JSON"

    @compiles(PG_UUID, "sqlite")
    def compile_uuid_sqlite(type_, compiler, **kw):
        return "VARCHAR(36)"

    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional test database session."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Override dependency for FastAPI test client."""
    async with TestSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# HTTP client fixture
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with DB override."""
    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Mock Ollama client
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_ollama_client():
    """Mock OllamaClient for tests that don't need real Ollama."""
    with patch("backend.services.ollama_client.OllamaClient") as MockClass:
        instance = MockClass.return_value
        instance.list_models = AsyncMock(return_value=[
            {"name": "llama3.2:3b", "size": 2_000_000_000, "details": {"family": "llama", "parameter_size": "3B", "quantization_level": "Q4_0"}, "modified_at": "2024-01-01T00:00:00Z"},
            {"name": "mistral:7b", "size": 4_200_000_000, "details": {"family": "mistral", "parameter_size": "7B", "quantization_level": "Q4_0"}, "modified_at": "2024-01-01T00:00:00Z"},
        ])
        instance.list_running = AsyncMock(return_value=[
            {"name": "llama3.2:3b", "size": 2_000_000_000, "expires_at": "2024-12-01T00:00:00Z"},
        ])
        instance.model_exists = AsyncMock(return_value=True)
        instance.stop_model = AsyncMock(return_value=None)
        instance.delete_model = AsyncMock(return_value=None)
        instance.pull_model = AsyncMock(return_value=async_pull_generator())
        instance.chat_stream = AsyncMock(return_value=async_chat_generator())
        instance._get_json = AsyncMock(return_value={"version": "0.5.0"})
        yield instance


async def async_pull_generator():
    """Simulate model pull streaming."""
    yield {"status": "pulling manifest"}
    yield {"status": "downloading", "completed": 500_000_000, "total": 2_000_000_000}
    yield {"status": "downloading", "completed": 2_000_000_000, "total": 2_000_000_000}
    yield {"status": "success"}


async def async_chat_generator():
    """Simulate chat streaming."""
    yield "Hello"
    yield " world"
    yield "!"


# ---------------------------------------------------------------------------
# Factory fixtures
# ---------------------------------------------------------------------------
class TestFactories:
    """Factory methods for creating test data."""

    @staticmethod
    def user_id() -> uuid.UUID:
        return uuid.uuid4()

    @staticmethod
    def conversation_data(user_id: uuid.UUID | None = None, **overrides) -> dict[str, Any]:
        defaults = {
            "id": uuid.uuid4(),
            "user_id": user_id or uuid.uuid4(),
            "title": "Test Conversation",
            "model_name": "llama3.2:3b",
            "context_window": 4096,
            "total_tokens": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "is_archived": False,
        }
        defaults.update(overrides)
        return defaults

    @staticmethod
    def message_data(conversation_id: uuid.UUID, **overrides) -> dict[str, Any]:
        defaults = {
            "id": uuid.uuid4(),
            "conversation_id": conversation_id,
            "role": "user",
            "content": "Hello, how are you?",
            "token_count": 5,
            "latency_ms": 100,
            "model_name": "llama3.2:3b",
            "request_id": uuid.uuid4().hex,
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return defaults

    @staticmethod
    def prompt_template_data(**overrides) -> dict[str, Any]:
        defaults = {
            "name": "Code Review",
            "description": "Review code for best practices",
            "template": "Review this code:\n\n{code}\n\nFocus on: {focus_areas}",
            "variables": ["code", "focus_areas"],
            "tags": ["code", "review"],
            "model_name": "llama3.2:3b",
        }
        defaults.update(overrides)
        return defaults

    @staticmethod
    def agent_config_data(**overrides) -> dict[str, Any]:
        defaults = {
            "name": "Backend Engineer",
            "agent_type": "backend_engineer",
            "description": "Implements APIs and business logic",
            "system_prompt": "You are a senior backend engineer...",
            "capabilities": ["code_generation", "api_design", "debugging"],
            "model_name": "llama3.2:3b",
            "max_iterations": 10,
        }
        defaults.update(overrides)
        return defaults


@pytest.fixture
def factories() -> TestFactories:
    """Provide test data factories."""
    return TestFactories()
