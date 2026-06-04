"""Pydantic schemas for the proofreader endpoint.

The proofreader evaluates an editorial translation (Darija or French) and
returns an editorial score plus a list of localized correction suggestions
the admin UI can present Grammarly-style.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["darija", "french"]
Field_ = Literal["title", "excerpt", "body"]
Severity = Literal["low", "medium", "high"]
Category = Literal["grammar", "naturalness", "clarity", "consistency"]


class ProofreadRequest(BaseModel):
    """Body of POST /admin/articles/{id}/proofread."""

    text: str = Field(..., min_length=1, max_length=20_000)
    lang: Language = "darija"
    field: Field_ = "body"


class ProofreadSuggestion(BaseModel):
    """A single fix suggestion the UI can render and apply on click."""

    original: str = Field(..., min_length=1, max_length=300)
    suggestion: str = Field(..., max_length=300)
    reason: str = Field(..., max_length=240)
    severity: Severity = "medium"
    category: Category = "naturalness"


class ProofreadResult(BaseModel):
    """Response of POST /admin/articles/{id}/proofread.

    From prompt v2 onwards the model returns four independent sub-scores and
    the top-level ``score`` is computed server-side as ``min(...)`` of the
    four — the worst dimension dominates, no anchoring to a "publishable"
    threshold. Older cached v1 results have the sub-scores set to ``None``
    and ``score`` carries the legacy single score.
    """

    score: int = Field(..., ge=0, le=100)
    grammar_score: int | None = Field(default=None, ge=0, le=100)
    naturalness_score: int | None = Field(default=None, ge=0, le=100)
    clarity_score: int | None = Field(default=None, ge=0, le=100)
    consistency_score: int | None = Field(default=None, ge=0, le=100)
    summary: str = Field(..., max_length=400)
    suggestions: list[ProofreadSuggestion] = Field(default_factory=list, max_length=12)
    lang: Language
    field: Field_
    model: str
    cached: bool = False
