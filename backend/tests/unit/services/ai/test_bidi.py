from app.services.ai.bidi import wrap_latin_with_bdi


def test_single_latin_word():
    assert wrap_latin_with_bdi("OpenAI") == "<bdi>OpenAI</bdi>"


def test_groups_consecutive_latin_words():
    out = wrap_latin_with_bdi("The Most Stealable Slackbot Prompts كان فيه 250 prompt")
    assert "<bdi>The Most Stealable Slackbot Prompts</bdi>" in out
    assert "<bdi>prompt</bdi>" in out
    # The standalone "250" between Arabic words is left plain.
    assert "<bdi>250</bdi>" not in out


def test_does_not_cross_arabic_boundary():
    out = wrap_latin_with_bdi("Anthropic مادارتش ضجة بحال OpenAI")
    assert out == "<bdi>Anthropic</bdi> مادارتش ضجة بحال <bdi>OpenAI</bdi>"


def test_multi_word_brand():
    out = wrap_latin_with_bdi("بدات تستعمل Google Drive files")
    assert out == "بدات تستعمل <bdi>Google Drive files</bdi>"


def test_keeps_pure_arabic_unchanged():
    arabic = "هاد المقال على الذكاء الاصطناعي"
    assert wrap_latin_with_bdi(arabic) == arabic


def test_handles_punctuation_and_hyphens():
    out = wrap_latin_with_bdi("claude-haiku-4-5 مقابل GPT-5")
    assert out == "<bdi>claude-haiku-4-5</bdi> مقابل <bdi>GPT-5</bdi>"


def test_digit_token_after_letter_groups():
    # "Fortune 500" should group; "60%" stays plain because it doesn't start with a letter.
    out = wrap_latin_with_bdi("60% ديال Fortune 500")
    assert out == "60% ديال <bdi>Fortune 500</bdi>"


def test_two_char_minimum_wraps_AI():
    assert wrap_latin_with_bdi("AI") == "<bdi>AI</bdi>"


def test_single_char_not_wrapped():
    assert wrap_latin_with_bdi("A") == "A"


def test_idempotent():
    inputs = [
        "ChatGPT أعلنات على GPT-5",
        "The Most Stealable Slackbot Prompts كان فيه 250 prompt",
        "Anthropic vs OpenAI: claude-sonnet-4-6 vs GPT-5",
    ]
    for s in inputs:
        once = wrap_latin_with_bdi(s)
        twice = wrap_latin_with_bdi(once)
        assert once == twice, f"not idempotent for: {s!r}"


def test_does_not_double_wrap():
    pre = "النموذج <bdi>Claude</bdi> سريع و <bdi>Google Drive</bdi> بطيء"
    assert wrap_latin_with_bdi(pre) == pre


def test_empty_string():
    assert wrap_latin_with_bdi("") == ""


def test_multiple_separate_latin_runs():
    # Three Latin tokens, each separated from the others by Arabic.
    out = wrap_latin_with_bdi("OpenAI و Anthropic و Google")
    assert out.count("<bdi>") == 3
    assert "<bdi>OpenAI</bdi>" in out
    assert "<bdi>Anthropic</bdi>" in out
    assert "<bdi>Google</bdi>" in out
