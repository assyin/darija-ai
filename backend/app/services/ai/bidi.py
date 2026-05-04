from __future__ import annotations

import re

# Match a contiguous run of Latin tokens separated by single spaces, so multi-word
# brand/title sequences group into a single <bdi> block instead of one-per-word.
#
# Components:
#   start       letter
#   body        zero+ connector/letter/digit chars, must end on alnum
#   tail repeat single space + (letter|digit) + optional body ending on alnum
#
# Effect:
#   "Anthropic ضجة OpenAI"               → 2 matches (stops at Arabic, restarts after)
#   "The Most Stealable Slackbot Prompts" → 1 match
#   "Fortune 500 list"                    → 1 match (digit-led tokens after space allowed)
#   "claude-haiku-4-5"                    → 1 match (hyphens & digits in body)
#   "A"                                   → no match (single-letter excluded)
_LATIN_PATTERN = re.compile(
    r"[A-Za-z](?:[A-Za-z0-9._'-]*[A-Za-z0-9])(?:[ ][A-Za-z0-9](?:[A-Za-z0-9._'-]*[A-Za-z0-9])?)*"
)
_BDI_BLOCK = re.compile(r"<bdi>.*?</bdi>", re.DOTALL)


def wrap_latin_with_bdi(text: str) -> str:
    """Wrap contiguous Latin runs (2+ chars) in <bdi> tags. Idempotent."""
    if not text:
        return text

    parts = re.split(r"(<bdi>.*?</bdi>)", text, flags=re.DOTALL)
    out: list[str] = []
    for part in parts:
        if part.startswith("<bdi>"):
            out.append(part)
        else:
            out.append(_LATIN_PATTERN.sub(lambda m: f"<bdi>{m.group()}</bdi>", part))
    return "".join(out)


def count_wrapped_terms(text: str) -> int:
    return len(_BDI_BLOCK.findall(text))


def strip_bdi_tags(text: str) -> str:
    """Remove <bdi>...</bdi> wrappers, keeping the inner text."""
    if not text:
        return text
    return re.sub(r"<bdi>(.*?)</bdi>", r"\1", text, flags=re.DOTALL)
