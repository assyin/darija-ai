"""One-shot backfill: auto-translate every article that still has empty FR.

Run-by-run idempotent — articles whose FR fields are already populated are
skipped. The Translator's Redis cache makes re-runs on the same Darija
content effectively free; what does cost money is the *first* run on each
article (~$0.02 each via Haiku 4.5).

Usage (inside the backend container):

    PYTHONPATH=/app python -m app.scripts.backfill_french_translations \\
        [--limit 50] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

import redis.asyncio as aioredis
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal, engine
from app.core.logging import configure_logging, get_logger
from app.models.article import Article
from app.services.ai.claude_client import ClaudeClient
from app.services.ai.translator import Translator


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of articles to translate this run (default: 50).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be translated without calling the API.",
    )
    args = parser.parse_args()

    configure_logging()
    log = get_logger("scripts.backfill_french_translations")
    settings = get_settings()

    try:
        async with AsyncSessionLocal() as session:
            # Untranslated = title_fr empty/null. Bias toward unpublished
            # drafts first so the admin sees them in /admin/articles.
            stmt = (
                select(Article)
                .where(Article.deleted_at.is_(None))
                .where((Article.title_fr.is_(None)) | (Article.title_fr == ""))  # type: ignore[union-attr]
                .order_by(Article.is_published.asc(), Article.id.asc())
                .limit(args.limit)
            )
            rows = list((await session.execute(stmt)).scalars())

        if not rows:
            print("No untranslated articles found.")
            return 0

        print(f"Found {len(rows)} article(s) without French translation.")
        for r in rows:
            published = "published" if r.is_published else "draft"
            print(f"  - id={r.id:>4} [{published}] {r.slug[:60]}")

        if args.dry_run:
            print("\nDry-run: no API calls made.")
            return 0

        redis_client = aioredis.from_url(str(settings.redis_url))
        claude = ClaudeClient(settings.anthropic_api_key)
        translator = Translator(claude=claude, redis_client=redis_client)

        ok = 0
        failed: list[tuple[int, str]] = []
        for r in rows:
            assert r.id is not None
            try:
                result = await translator.translate(
                    title_darija=r.title_darija,
                    excerpt_darija=r.excerpt_darija,
                    content_darija=r.content_darija,
                    meta_title=r.meta_title,
                    meta_description=r.meta_description,
                )
            except Exception as exc:
                print(f"  ✗ id={r.id} failed: {exc.__class__.__name__}: {exc}")
                failed.append((r.id, f"{exc.__class__.__name__}: {exc}"))
                continue

            async with AsyncSessionLocal() as session:
                row = await session.get(Article, r.id)
                if row is None:
                    continue
                row.title_fr = result.title_fr or None
                row.excerpt_fr = result.excerpt_fr or None
                row.content_fr = result.content_fr or None
                row.meta_title_fr = result.meta_title_fr or None
                row.meta_description_fr = result.meta_description_fr or None
                row.updated_at = datetime.now(UTC)
                await session.commit()

            ok += 1
            cached_note = " (cached)" if result.cached else ""
            print(
                f"  ✓ id={r.id} → {result.title_fr[:60]!r}{cached_note} "
                f"({result.duration_ms} ms, {len(result.content_fr)} chars)"
            )

        print()
        print(f"Done: {ok} translated, {len(failed)} failed.")
        if failed:
            for fid, err in failed:
                print(f"  - id={fid}: {err}")
            return 1
        return 0
    except Exception:
        log.exception("backfill_french_translations.unexpected_error")
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
