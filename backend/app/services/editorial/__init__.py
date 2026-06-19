"""Editorial Ranking Engine (ERE) — deterministic scoring.

Step 3 of the ERE rollout: pure, testable scoring logic only. No DB, no flags,
no job, no pipeline wiring, no LLM. See docs/EDITORIAL_RANKING_ENGINE_MVP_V1.md.
"""

from __future__ import annotations

from app.services.editorial.deterministic_ranker import (
    RankInput,
    RankResult,
    decide,
    rank,
)

__all__ = ["RankInput", "RankResult", "decide", "rank"]
