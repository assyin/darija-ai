"""Unit tests for the related-articles service.

These tests target the orchestration logic in
``compute_related`` (pinned overrides, deduplication, fallback decision)
without touching the SQL — the actual ranking query is covered by the
integration suite where a real Postgres can execute the GIN-indexed
overlap queries.

The contract pinned here:

  - When the caller supplies ``pinned_slugs``, those articles appear in
    the result in the order the caller passed them, and the algorithmic
    search runs only for the remaining slots.
  - The source slug is never returned to the caller — even if the admin
    pins it by mistake.
  - When the algorithmic search returns zero rows, the service falls back
    to the most-recent publications.
  - When the algorithmic search already fills the limit, the fallback
    helper is not called.
  - The deduplication excludes pinned slugs from the algorithmic search so
    we don't render the same article twice in the rail.
  - ``limit <= 0`` is a no-op.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.article import Article
from app.services.articles.related import compute_related


def _article(slug: str, **kw: Any) -> Article:
    """Build a minimal Article with sensible defaults so tests stay terse."""
    defaults: dict[str, Any] = {
        "slug": slug,
        "title_darija": f"title {slug}",
        "excerpt_darija": "excerpt",
        "content_darija": "body",
        "categories": [],
        "tags": [],
        "raw_article_id": 1,
        "is_published": True,
    }
    defaults.update(kw)
    return Article(**defaults)


@pytest.mark.asyncio
async def test_limit_zero_returns_empty_no_db_calls() -> None:
    """Guard: caller asking for 0 results must not hit the DB."""
    session = MagicMock()
    with (
        patch(
            "app.services.articles.related._rank_by_overlap",
            new=AsyncMock(),
        ) as mock_rank,
        patch(
            "app.services.articles.related._fetch_articles_by_slugs",
            new=AsyncMock(),
        ) as mock_pinned,
        patch(
            "app.services.articles.related._fetch_most_recent",
            new=AsyncMock(),
        ) as mock_recent,
    ):
        result = await compute_related(session, source_slug="x", limit=0)

    assert result == []
    mock_rank.assert_not_called()
    mock_pinned.assert_not_called()
    mock_recent.assert_not_called()


@pytest.mark.asyncio
async def test_algorithmic_results_returned_when_no_pins() -> None:
    """Default path: no pins, algorithm fills the whole rail."""
    session = MagicMock()
    algo = [_article("a"), _article("b"), _article("c"), _article("d")]
    with (
        patch(
            "app.services.articles.related._rank_by_overlap",
            new=AsyncMock(return_value=algo),
        ),
        patch(
            "app.services.articles.related._fetch_most_recent",
            new=AsyncMock(),
        ) as mock_recent,
    ):
        result = await compute_related(session, source_slug="src", limit=4)

    assert [a.slug for a in result] == ["a", "b", "c", "d"]
    mock_recent.assert_not_called()  # algorithm produced enough, no fallback


@pytest.mark.asyncio
async def test_pinned_slugs_take_first_slots_and_excluded_from_algo() -> None:
    """Pins come first (in admin order), algo fills the rest and skips them."""
    session = MagicMock()
    pinned = [_article("pin-a"), _article("pin-b")]
    algo = [_article("algo-x"), _article("algo-y")]

    with (
        patch(
            "app.services.articles.related._fetch_articles_by_slugs",
            new=AsyncMock(return_value=pinned),
        ),
        patch(
            "app.services.articles.related._rank_by_overlap",
            new=AsyncMock(return_value=algo),
        ) as mock_rank,
    ):
        result = await compute_related(
            session,
            source_slug="src",
            limit=4,
            pinned_slugs=["pin-a", "pin-b"],
        )

    assert [a.slug for a in result] == ["pin-a", "pin-b", "algo-x", "algo-y"]
    # Algorithm asked for the remaining 2 only.
    rank_kwargs = mock_rank.await_args.kwargs
    assert rank_kwargs["limit"] == 2
    # And was told to exclude the source + both pinned slugs.
    assert set(rank_kwargs["exclude_slugs"]) == {"src", "pin-a", "pin-b"}


@pytest.mark.asyncio
async def test_pinned_order_preserved_from_caller() -> None:
    """If DB returns pinned articles in a different order, we re-sort to the admin's choice."""
    session = MagicMock()
    db_order = [_article("pin-b"), _article("pin-a")]  # DB returns b, a
    with (
        patch(
            "app.services.articles.related._fetch_articles_by_slugs",
            new=AsyncMock(return_value=db_order),
        ),
        patch(
            "app.services.articles.related._rank_by_overlap",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.articles.related._fetch_most_recent",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await compute_related(
            session,
            source_slug="src",
            limit=4,
            pinned_slugs=["pin-a", "pin-b"],  # admin asked a, b
        )

    assert [a.slug for a in result] == ["pin-a", "pin-b"]


@pytest.mark.asyncio
async def test_source_slug_pinned_is_silently_dropped() -> None:
    """If an admin pins the source itself, we ignore it rather than self-link."""
    session = MagicMock()
    with (
        patch(
            "app.services.articles.related._fetch_articles_by_slugs",
            new=AsyncMock(return_value=[_article("pin-x")]),
        ) as mock_pinned,
        patch(
            "app.services.articles.related._rank_by_overlap",
            new=AsyncMock(return_value=[_article("algo")]),
        ),
    ):
        await compute_related(
            session,
            source_slug="src",
            limit=4,
            pinned_slugs=["src", "pin-x"],  # 'src' must be dropped
        )

    # The pinned helper should never have been asked for 'src'.
    pinned_kwargs = mock_pinned.await_args.kwargs
    pinned_args = mock_pinned.await_args.args
    requested_slugs = pinned_args[1] if len(pinned_args) > 1 else pinned_kwargs.get("slugs", [])
    assert "src" not in requested_slugs


@pytest.mark.asyncio
async def test_pins_fill_limit_skip_algorithm() -> None:
    """When pins already meet the limit, the algorithm doesn't run."""
    session = MagicMock()
    with (
        patch(
            "app.services.articles.related._fetch_articles_by_slugs",
            new=AsyncMock(
                return_value=[
                    _article("p1"),
                    _article("p2"),
                    _article("p3"),
                    _article("p4"),
                ]
            ),
        ),
        patch(
            "app.services.articles.related._rank_by_overlap",
            new=AsyncMock(),
        ) as mock_rank,
        patch(
            "app.services.articles.related._fetch_most_recent",
            new=AsyncMock(),
        ) as mock_recent,
    ):
        result = await compute_related(
            session,
            source_slug="src",
            limit=4,
            pinned_slugs=["p1", "p2", "p3", "p4"],
        )

    assert len(result) == 4
    mock_rank.assert_not_called()
    mock_recent.assert_not_called()


@pytest.mark.asyncio
async def test_fallback_to_most_recent_when_algorithm_empty() -> None:
    """Niche source with no shared signals → fallback to latest published articles."""
    session = MagicMock()
    fallback = [_article("recent-a"), _article("recent-b")]
    with (
        patch(
            "app.services.articles.related._rank_by_overlap",
            new=AsyncMock(return_value=[]),  # niche article, no overlap
        ),
        patch(
            "app.services.articles.related._fetch_most_recent",
            new=AsyncMock(return_value=fallback),
        ) as mock_recent,
    ):
        result = await compute_related(session, source_slug="src", limit=4)

    assert [a.slug for a in result] == ["recent-a", "recent-b"]
    # Fallback should exclude the source (defensive — we never want a self-link).
    recent_kwargs = mock_recent.await_args.kwargs
    assert "src" in recent_kwargs["exclude_slugs"]


@pytest.mark.asyncio
async def test_lang_fr_propagates_to_helpers() -> None:
    """`lang='fr'` must flow through to both the algorithmic and fallback queries."""
    session = MagicMock()
    with (
        patch(
            "app.services.articles.related._rank_by_overlap",
            new=AsyncMock(return_value=[]),
        ) as mock_rank,
        patch(
            "app.services.articles.related._fetch_most_recent",
            new=AsyncMock(return_value=[]),
        ) as mock_recent,
    ):
        await compute_related(session, source_slug="src", lang="fr", limit=4)

    assert mock_rank.await_args.kwargs["lang"] == "fr"
    assert mock_recent.await_args.kwargs["lang"] == "fr"
