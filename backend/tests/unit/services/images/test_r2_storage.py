from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from app.core.exceptions import ExternalServiceError
from app.services.images.r2_storage import PUBLIC_CACHE_CONTROL, R2Storage


def _make_storage_with_mock_s3(s3_mock: MagicMock) -> R2Storage:
    storage = R2Storage(
        account_id="acct",
        access_key_id="ak",
        secret_access_key="sk",
        bucket_name="darija-ai-images",
        endpoint_url="https://acct.eu.r2.cloudflarestorage.com",
        public_url="https://pub-x.r2.dev/",
    )
    storage._s3 = s3_mock
    return storage


@pytest.mark.asyncio
async def test_upload_calls_put_object_with_expected_kwargs():
    s3 = MagicMock()
    s3.put_object = MagicMock(return_value={"ETag": '"abc123"'})
    storage = _make_storage_with_mock_s3(s3)

    url = await storage.upload(
        key="articles/2026/05/test.webp",
        body=b"\x89PNG-bytes",
        content_type="image/webp",
    )

    s3.put_object.assert_called_once_with(
        Bucket="darija-ai-images",
        Key="articles/2026/05/test.webp",
        Body=b"\x89PNG-bytes",
        ContentType="image/webp",
        CacheControl=PUBLIC_CACHE_CONTROL,
    )
    assert url == "https://pub-x.r2.dev/articles/2026/05/test.webp"


@pytest.mark.asyncio
async def test_client_error_wraps_in_external_service_error():
    s3 = MagicMock()
    s3.put_object = MagicMock(
        side_effect=ClientError(
            {"Error": {"Code": "SignatureDoesNotMatch", "Message": "bad sig"}},
            "PutObject",
        )
    )
    storage = _make_storage_with_mock_s3(s3)

    with pytest.raises(ExternalServiceError) as exc_info:
        await storage.upload(
            key="articles/2026/05/test.webp",
            body=b"\x00",
            content_type="image/webp",
        )
    assert exc_info.value.details["provider"] == "r2"
    assert exc_info.value.details["bucket"] == "darija-ai-images"
