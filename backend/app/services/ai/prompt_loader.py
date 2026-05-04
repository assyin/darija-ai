from __future__ import annotations

import hashlib
from pathlib import Path


class PromptLoader:
    """Loads versioned prompts from disk and caches them in memory."""

    _PROMPTS_DIR: Path = Path(__file__).parent / "prompts"
    _cache: dict[tuple[str, str], str] = {}

    @classmethod
    def load(cls, name: str, version: str) -> str:
        key = (name, version)
        cached = cls._cache.get(key)
        if cached is not None:
            return cached

        path = cls._PROMPTS_DIR / f"{name}_{version}.md"
        if not path.is_file():
            raise FileNotFoundError(f"Prompt not found: {path}")
        content = path.read_text(encoding="utf-8")
        cls._cache[key] = content
        return content

    @classmethod
    def hash(cls, name: str, version: str) -> str:
        content = cls.load(name, version)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
