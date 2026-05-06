from __future__ import annotations

from httpx import AsyncClient

from app.core.db import AsyncSessionLocal
from app.models.site_setting import SiteSetting
from tests.integration.conftest import TEST_KEY_PREFIX


async def _insert(setting: SiteSetting) -> None:
    async with AsyncSessionLocal() as session:
        session.add(setting)
        await session.commit()


async def _get(key: str) -> SiteSetting | None:
    async with AsyncSessionLocal() as session:
        return await session.get(SiteSetting, key)


async def test_get_public_returns_only_public_settings(
    client: AsyncClient, db_cleanup: None
) -> None:
    public_key = f"{TEST_KEY_PREFIX}public_brand"
    private_key = f"{TEST_KEY_PREFIX}private_admin_email"
    await _insert(
        SiteSetting(
            key=public_key,
            value="public-value",
            value_type="string",
            category="branding",
            label_fr="Test public",
            description=None,
            is_public=True,
        )
    )
    await _insert(
        SiteSetting(
            key=private_key,
            value="private-value",
            value_type="email",
            category="admin",
            label_fr="Test private",
            description=None,
            is_public=False,
        )
    )

    response = await client.get("/api/v1/settings/public")
    assert response.status_code == 200
    body = response.json()
    assert body[public_key] == "public-value"
    assert private_key not in body


async def test_admin_list_returns_all(
    client: AsyncClient, db_cleanup: None
) -> None:
    public_key = f"{TEST_KEY_PREFIX}public_x"
    private_key = f"{TEST_KEY_PREFIX}private_x"
    await _insert(
        SiteSetting(
            key=public_key, value="p", value_type="string", category="branding",
            label_fr="P", description=None, is_public=True,
        )
    )
    await _insert(
        SiteSetting(
            key=private_key, value="q", value_type="string", category="admin",
            label_fr="Q", description=None, is_public=False,
        )
    )

    response = await client.get("/api/v1/admin/settings")
    assert response.status_code == 200
    body = response.json()
    keys = {item["key"] for item in body}
    assert public_key in keys
    assert private_key in keys


async def test_admin_patch_updates_value(
    client: AsyncClient, db_cleanup: None
) -> None:
    key = f"{TEST_KEY_PREFIX}contact_whatsapp"
    await _insert(
        SiteSetting(
            key=key, value="+212 600 000 000", value_type="phone",
            category="contact", label_fr="WA test", description=None, is_public=True,
        )
    )

    response = await client.patch(
        f"/api/v1/admin/settings/{key}",
        json={"value": "+212 700 111 222"},
    )
    assert response.status_code == 200
    assert response.json()["value"] == "+212 700 111 222"

    # Re-fetch to confirm persistence
    refetch = await client.get(f"/api/v1/admin/settings/{key}")
    assert refetch.status_code == 200
    assert refetch.json()["value"] == "+212 700 111 222"

    # And via DB directly
    row = await _get(key)
    assert row is not None and row.value == "+212 700 111 222"


async def test_admin_patch_unknown_key_returns_404(
    client: AsyncClient, db_cleanup: None
) -> None:
    response = await client.patch(
        f"/api/v1/admin/settings/{TEST_KEY_PREFIX}does_not_exist",
        json={"value": "anything"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"


async def test_admin_bulk_update_applies_all(
    client: AsyncClient, db_cleanup: None
) -> None:
    key_a = f"{TEST_KEY_PREFIX}bulk_a"
    key_b = f"{TEST_KEY_PREFIX}bulk_b"
    await _insert(
        SiteSetting(
            key=key_a, value="a-old", value_type="string", category="branding",
            label_fr="A", description=None, is_public=True,
        )
    )
    await _insert(
        SiteSetting(
            key=key_b, value="b-old", value_type="string", category="branding",
            label_fr="B", description=None, is_public=True,
        )
    )

    response = await client.post(
        "/api/v1/admin/settings/bulk",
        json={
            "updates": [
                {"key": key_a, "value": "a-new"},
                {"key": key_b, "value": "b-new"},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    by_key = {item["key"]: item["value"] for item in body}
    assert by_key[key_a] == "a-new"
    assert by_key[key_b] == "b-new"

    # Persistence check
    row_a = await _get(key_a)
    row_b = await _get(key_b)
    assert row_a is not None and row_a.value == "a-new"
    assert row_b is not None and row_b.value == "b-new"
