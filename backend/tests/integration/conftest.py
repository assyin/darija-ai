from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core.db import AsyncSessionLocal
from app.main import create_app
from app.models.site_setting import SiteSetting

TEST_KEY_PREFIX = "_test_"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTPX async client wired to the FastAPI app via ASGITransport."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db_cleanup() -> AsyncIterator[None]:
    """Removes any rows whose key starts with the test prefix after each test.

    Tests that mutate seeded settings restore them themselves (or use the prefix).
    """
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(SiteSetting).where(SiteSetting.key.startswith(TEST_KEY_PREFIX))
        )
        await session.commit()
