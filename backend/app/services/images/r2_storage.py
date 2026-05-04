from __future__ import annotations

import asyncio

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger("services.images.r2_storage")

PUBLIC_CACHE_CONTROL = "public, max-age=31536000, immutable"


class R2Storage:
    """Cloudflare R2 uploader using boto3 (S3-compatible API).

    R2 endpoints are HTTPS only, region is the literal string ``"auto"``,
    and signature must be ``s3v4`` for compatibility.
    """

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        endpoint_url: str,
        public_url: str,
    ):
        self._account_id = account_id  # kept for log context only
        self._bucket = bucket_name
        self._public_url = public_url.rstrip("/")
        self._endpoint_url = endpoint_url
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    async def upload(self, *, key: str, body: bytes, content_type: str) -> str:
        """Upload bytes to R2; return the public URL."""
        logger.info(
            "image.r2.upload_started",
            bucket=self._bucket,
            key=key,
            content_type=content_type,
            bytes=len(body),
        )
        try:
            await asyncio.to_thread(
                self._s3.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                CacheControl=PUBLIC_CACHE_CONTROL,
            )
        except (ClientError, BotoCoreError) as exc:
            logger.error(
                "image.r2.upload_failed",
                bucket=self._bucket,
                key=key,
                error=str(exc),
                error_type=exc.__class__.__name__,
            )
            raise ExternalServiceError(
                f"R2 upload failed: {exc.__class__.__name__}",
                details={
                    "provider": "r2",
                    "bucket": self._bucket,
                    "key": key,
                    "error": str(exc),
                },
            ) from exc

        public_url = f"{self._public_url}/{key}"
        logger.info("image.r2.upload_completed", key=key, public_url=public_url)
        return public_url
