"""Schemas for ERE Human Audit V1 (admin review of shadow decisions)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Verdict = Literal["KEEP", "REJECT"]


class AuditQueueItem(BaseModel):
    id: int
    title: str
    source: str
    score: int
    decision: str
    category: str
    breakdown: dict[str, Any]


class AuditQueueList(BaseModel):
    data: list[AuditQueueItem]
    next_cursor: str | None = None


class AuditVerdictIn(BaseModel):
    article_id: int
    human_verdict: Verdict
    notes: str | None = Field(default=None, max_length=2000)


class AuditRecord(BaseModel):
    id: int
    article_id: int
    ere_score: int
    ere_decision: str
    human_verdict: str
    reviewer: str
    notes: str | None
    created_at: str
    updated_at: str


class AuditMetrics(BaseModel):
    audited: int
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float
    recall: float
