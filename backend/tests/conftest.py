"""Tests sur une base PostgreSQL dédiée (careneo_test) : migrée par Alembic au début de la session
(aller-retour complet, ce qui teste aussi le downgrade), puis remise aux données de démonstration
avant chaque test."""

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://careneo:careneo@localhost:5432/careneo_test"
)
os.environ["ENVIRONMENT"] = "test"

from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db import engine
from app.main import app
from app.seed import DEMO_PASSWORD, seed

OWNER = "armateur@careneo.demo"
OWNER2 = "armateur2@careneo.demo"
YARD = "chantier@careneo.demo"
YARD2 = "chantier2@careneo.demo"
ADMIN = "admin@careneo.demo"

ApiFactory = Callable[..., Awaitable[AsyncClient]]


async def _ensure_test_database() -> None:
    url = make_url(settings.database_url)
    server = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with server.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    await server.dispose()


def _migrate(connection: Connection) -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes.update(connection=connection, configure_logger=False)
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
async def database() -> AsyncIterator[None]:
    await _ensure_test_database()
    async with engine.begin() as connection:
        await connection.run_sync(_migrate)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def demo_data(database: None) -> None:
    await seed(reset=True)


@pytest.fixture
async def api() -> AsyncIterator[ApiFactory]:
    """Fabrique de clients HTTP : `await api()` anonyme, `await api(email)` connecté."""
    transport = ASGITransport(app=app)
    clients: list[AsyncClient] = []

    async def client(email: str | None = None) -> AsyncClient:
        http = AsyncClient(transport=transport, base_url="http://testserver")
        clients.append(http)
        if email is not None:
            response = await http.post(
                "/api/auth/login", json={"email": email, "password": DEMO_PASSWORD}
            )
            assert response.status_code == 200, response.text
        return http

    yield client
    for http in clients:
        await http.aclose()
