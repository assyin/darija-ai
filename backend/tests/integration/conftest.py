from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.api.deps import public_rate_limit
from app.core.db import AsyncSessionLocal
from app.core.security import create_access_token
from app.main import create_app
from app.models.site_setting import SiteSetting

TEST_KEY_PREFIX = "_test_"
TEST_ADMIN_EMAIL = "test-admin@darija-ai.ma"


@pytest.fixture
def admin_token() -> str:
    return create_access_token(TEST_ADMIN_EMAIL)


@pytest.fixture
def auth_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTPX async client wired to the FastAPI app via ASGITransport."""
    app = create_app()
    # Public rate limiting would otherwise accumulate across tests on a shared
    # IP key and flake the suite — disable it for integration tests.
    app.dependency_overrides[public_rate_limit] = lambda: None
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
