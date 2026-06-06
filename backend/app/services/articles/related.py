"""Semantic related-articles ranking.

Picks 3-5 articles that are topically close to a given source article, based on
overlapping categories and tags plus a freshness bonus. Replaces the previous
frontend logic that just sliced the latest 3 publications regardless of topic.

Design (see SEO design doc 2026-06-06):

  - One Postgres query, uses the existing GIN indexes on
    ``articles.categories`` and ``articles.tags`` so cost stays O(log n) up
    to thousands of articles. No Redis cache in this MVP — at ~50 articles
    the compute is well under 50 ms; we'll layer caching in if and when
    the catalogue grows.
  - Scoring is `sum(weight * signal)`. Adding a new dimension (named
    entities, mentioned AI models, same-company links, …) is a single
    additional term in the SELECT — keep that surface intentional so the
    formula stays readable even at 4-5 signals.
  - Fail-soft: if the source has no overlap with anything in the corpus
    (a niche-tag article), the service falls back to the N most recent
    publications. The page never renders an empty "related" rail.
  - Admin override extension point: `pinned_slugs` lets a future admin UI
    pin specific related articles for a given source. Those slugs are
    prepended and excluded from the algorithmic search. The schema doesn't
    yet store per-article overrides — that's a follow-up migration when
    the admin needs the feature.
"""

from __future__ import annotations

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.article import Article

logger = get_logger("services.articles.related")

# Scoring weights. Tuneable in one place.
_WEIGHT_CATEGORY_OVERLAP = 4.0
_WEIGHT_TAG_OVERLAP = 2.0
_WEIGHT_RECENT_BONUS = 1.0
# A candidate counts as "recent" if published within this window.
_RECENT_WINDOW_DAYS = 30

# When we'd otherwise return an empty rail, hand back at most this many of
# the most recent articles (excluding the source). The constant lives next
# to the scoring weights because tuning the fallback is part of the same
# product question ("what does the rail look like when matching is thin?").
_FALLBACK_MAX = 5


async def compute_related(
    session: AsyncSession,
    *,
    source_slug: str,
    lang: str | None = None,
    limit: int = 4,
    pinned_slugs: list[str] | None = None,
) -> list[Article]:
    """Return up to ``limit`` published articles most topically related to ``source_slug``.

    Steps:

      1. Pinned overrides (if any) take the first slots and are excluded from
         the algorithmic search. When `pinned_slugs` is None or empty, this
         branch is a no-op.
      2. Algorithmic ranking via a single SQL query that joins the source
         article's `categories`/`tags` against every other published row,
         scores each candidate, and returns the top `remaining_limit`.
      3. If algorithmic search produces zero rows (very niche article), fall
         back to the latest published articles, excluding the source and the
         pinned slugs.

    Returns at most `limit` rows; may return fewer when the corpus is small.
    Never raises ApiError-style exceptions — callers can render the result
    directly even on degenerate inputs.

    ``lang='fr'`` filters out articles without a French translation
    (`title_fr` empty/null), so a French listing never links to a
    Darija-only article that would 404 or fall back to the original
    language without warning.
    """
    if limit <= 0:
        return []

    exclude_slugs = [source_slug]

    # 1) Pinned overrides — fetch in the order the admin specified.
    pinned_articles: list[Article] = []
    if pinned_slugs:
        # Take only as many pins as we have slots for.
        wanted = [s for s in pinned_slugs if s != source_slug][:limit]
        if wanted:
            pinned_articles = await _fetch_articles_by_slugs(session, wanted, lang=lang)
            # Preserve admin-specified order, not DB order.
            order = {slug: i for i, slug in enumerate(wanted)}
            pinned_articles.sort(key=lambda a: order.get(a.slug, len(wanted)))
            exclude_slugs.extend(a.slug for a in pinned_articles)

    remaining = limit - len(pinned_articles)
    if remaining <= 0:
        return pinned_articles

    # 2) Algorithmic ranking.
    algorithmic = await _rank_by_overlap(
        session,
        source_slug=source_slug,
        lang=lang,
        limit=remaining,
        exclude_slugs=exclude_slugs,
    )

    if algorithmic:
        return pinned_articles + algorithmic

    # 3) Fallback — most-recent articles when the source has no topical
    #    neighbours (typically a single niche tag, no shared category).
    fallback_count = min(remaining, _FALLBACK_MAX)
    fallback = await _fetch_most_recent(
        session,
        lang=lang,
        limit=fallback_count,
        exclude_slugs=exclude_slugs,
    )
    logger.info(
        "related.fallback_used",
        source_slug=source_slug,
        lang=lang,
        fallback_count=len(fallback),
    )
    return pinned_articles + fallback


# --- Internal helpers ---------------------------------------------------------


async def _rank_by_overlap(
    session: AsyncSession,
    *,
    source_slug: str,
    lang: str | None,
    limit: int,
    exclude_slugs: list[str],
) -> list[Article]:
    """The single SQL query that does the scoring.

    Joins each candidate row against the source's ``categories`` and
    ``tags`` arrays, sums the weighted overlaps, applies the recency
    bonus, then orders by score → published_at → id for determinism.

    The ``categories && s.categories OR tags && s.tags`` predicate
    short-circuits via the GIN indexes — only rows with at least one
    shared signal reach the scoring expression.
    """
    fr_filter = ""
    if lang == "fr":
        fr_filter = "AND a.title_fr IS NOT NULL AND a.title_fr <> ''"

    sql = text(
        f"""
        WITH source AS (
            SELECT categories, tags
            FROM articles
            WHERE slug = :source_slug AND is_published = TRUE AND deleted_at IS NULL
        )
        SELECT a.*
        FROM articles a, source s
        WHERE a.is_published = TRUE
          AND a.deleted_at IS NULL
          AND a.slug <> ALL(:exclude_slugs)
          AND (a.categories && s.categories OR a.tags && s.tags)
          {fr_filter}
        ORDER BY
            (
                {_WEIGHT_CATEGORY_OVERLAP} * cardinality(
                    ARRAY(SELECT unnest(a.categories) INTERSECT SELECT unnest(s.categories))
                )
                + {_WEIGHT_TAG_OVERLAP} * cardinality(
                    ARRAY(SELECT unnest(a.tags) INTERSECT SELECT unnest(s.tags))
                )
                + CASE
                    WHEN a.published_at > NOW() - INTERVAL '{_RECENT_WINDOW_DAYS} days'
                    THEN {_WEIGHT_RECENT_BONUS}
                    ELSE 0
                END
            ) DESC,
            a.published_at DESC NULLS LAST,
            a.id DESC
        LIMIT :limit
        """  # noqa: S608 — `lang` controls only an additional WHERE clause and is bound to a literal
    )
    stmt = sql.bindparams(
        bindparam("source_slug", source_slug),
        bindparam("exclude_slugs", exclude_slugs),
        bindparam("limit", limit),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _fetch_most_recent(
    session: AsyncSession,
    *,
    lang: str | None,
    limit: int,
    exclude_slugs: list[str],
) -> list[Article]:
    """Fallback when the algorithmic pass returns nothing."""
    fr_filter = ""
    if lang == "fr":
        fr_filter = "AND title_fr IS NOT NULL AND title_fr <> ''"

    sql = text(
        f"""
        SELECT *
        FROM articles
        WHERE is_published = TRUE
          AND deleted_at IS NULL
          AND slug <> ALL(:exclude_slugs)
          {fr_filter}
        ORDER BY published_at DESC NULLS LAST, id DESC
        LIMIT :limit
        """  # noqa: S608 — same as above, lang governs a static filter only
    )
    stmt = sql.bindparams(
        bindparam("exclude_slugs", exclude_slugs),
        bindparam("limit", limit),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _fetch_articles_by_slugs(
    session: AsyncSession,
    slugs: list[str],
    *,
    lang: str | None = None,
) -> list[Article]:
    """Load a set of articles by slug, filtering published + FR-translated when asked."""
    if not slugs:
        return []
    fr_filter = ""
    if lang == "fr":
        fr_filter = "AND title_fr IS NOT NULL AND title_fr <> ''"

    sql = text(
        f"""
        SELECT *
        FROM articles
        WHERE slug = ANY(:slugs)
          AND is_published = TRUE
          AND deleted_at IS NULL
          {fr_filter}
        """  # noqa: S608
    )
    stmt = sql.bindparams(bindparam("slugs", slugs))
    result = await session.execute(stmt)
    return list(result.scalars().all())
