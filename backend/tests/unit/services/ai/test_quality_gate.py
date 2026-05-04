from app.services.ai.localizer import LocalizedArticle
from app.services.ai.quality_gate import QualityGate

_FILLER = (
    "هاد المقال على الذكاء الاصطناعي وكيفاش كيتطور هاد المجال فالعالم اليوم. "
    "كاينة بزاف ديال الشركات اللي كتخدم على هاد التكنولوجيا الجديدة وكتدير "
    "تطورات مهمة فهاد المجال المثير للاهتمام بزاف ديال الناس فجميع البلدان. "
    "خاصنا نفهموا كيفاش هاد الأمور كتأثر علينا فحياتنا اليومية وفالعمل ديالنا. "
)

VALID_BODY = (
    _FILLER * 3
    + "\n\n## القسم الأول من المقال\n\n"
    + _FILLER * 3
    + "\n\nالنقاط الأساسية:\n\n"
    + "- النقطة الأولى المهمة فهاد الموضوع الكبير\n"
    + "- النقطة الثانية اللي خاصنا نركزوا عليها مزيان\n"
    + "- النقطة الثالثة اللي كتكمل الصورة كاملة\n\n"
    + "## القسم الثاني من التحليل\n\n"
    + _FILLER * 3
    + "\n\n## شنو كيعني هاد الشي ليك؟\n\n"
    + _FILLER * 2
)


def _make_article(content: str, **overrides: object) -> LocalizedArticle:
    defaults: dict[str, object] = {
        "title_darija": "عنوان المقال على الذكاء الاصطناعي",
        "slug": "test-article-slug",
        "excerpt_darija": "هاد المقال كيشرح التطورات الجديدة فعالم الذكاء الاصطناعي.",
        "content_darija": content,
        "meta_title": "عنوان للسيو على الذكاء الاصطناعي",
        "meta_description": "وصف قصير للسيو على الذكاء الاصطناعي والتطورات الجديدة.",
        "categories": ["llm"],
        "tags": ["ai", "claude"],
        "image_prompt": "Abstract editorial illustration",
    }
    defaults.update(overrides)
    return LocalizedArticle(**defaults)  # type: ignore[arg-type]


def test_valid_darija_article_passes():
    article = _make_article(VALID_BODY)
    result = QualityGate().check(article)
    assert result.passed, f"failures={result.failures} warnings={result.warnings}"
    assert result.detected_language == "ar"


def test_too_short_fails():
    short = "## مقدمة\n\nهاد المقال قصير بزاف.\n\n## شنو كيعني هاد الشي ليك؟\n\nقصير."
    article = _make_article(short)
    result = QualityGate().check(article)
    assert not result.passed
    assert "too_short" in result.failures


def test_missing_takeaway_fails():
    body = VALID_BODY.replace("## شنو كيعني هاد الشي ليك؟", "## خاتمة عامة")
    article = _make_article(body)
    result = QualityGate().check(article)
    assert not result.passed
    assert "missing_takeaway" in result.failures


def test_english_residue_fails():
    leaked = (
        VALID_BODY
        + "\n\nThis is a long paragraph in English that should clearly trigger the residue heuristic check."
    )
    article = _make_article(leaked)
    result = QualityGate().check(article)
    assert not result.passed
    assert "english_residue" in result.failures


def test_placeholder_text_fails():
    body = VALID_BODY + "\n\n[TODO] هنا نزيد التفاصيل."
    article = _make_article(body)
    result = QualityGate().check(article)
    assert not result.passed
    assert "placeholder_text" in result.failures


def test_bdi_wrapped_latin_does_not_trigger_residue():
    body = (
        VALID_BODY
        + "\n\n<bdi>This is some long English content that would normally trigger the residue check</bdi> ولكن كاين فالـ bdi."
    )
    article = _make_article(body)
    result = QualityGate().check(article)
    assert "english_residue" not in result.failures


def test_missing_h2_sections_fails():
    body = "هاد فقرة بدون عناوين على الذكاء الاصطناعي. " * 50
    body += "\n\n## شنو كيعني هاد الشي ليك؟\n\nخلاصة قصيرة."
    body += "\n\n- نقطة"
    article = _make_article(body)
    result = QualityGate().check(article)
    assert not result.passed
    assert "missing_h2_sections" in result.failures


def test_invalid_slug_warning():
    article = _make_article(VALID_BODY, slug="Bad Slug With Spaces")
    result = QualityGate().check(article)
    assert "slug_invalid" in result.warnings


def test_long_title_warning():
    article = _make_article(VALID_BODY, title_darija="ع" * 80)
    result = QualityGate().check(article)
    assert "title_too_long" in result.warnings
