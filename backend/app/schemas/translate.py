"""Schemas for the Darija → French auto-translator endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TranslateToFrenchResult(BaseModel):
    """Response shape of the translator service + endpoint."""

    title_fr: str = Field(default="", max_length=500)
    excerpt_fr: str = Field(default="", max_length=1000)
    content_fr: str = Field(default="")
    meta_title_fr: str = Field(default="", max_length=500)
    meta_description_fr: str = Field(default="", max_length=1000)
    model: str
    cached: bool = False
    duration_ms: int = 0
