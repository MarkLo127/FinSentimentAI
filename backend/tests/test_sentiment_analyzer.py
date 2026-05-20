"""Tests for the Claude-based sentiment analyzer.

We mock the AsyncAnthropic client to keep tests offline and deterministic.
The structural assertions verify (a) the Pydantic schema, (b) the cache_control
parameter is sent on every call, and (c) usage stats round-trip correctly.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from services.sentiment_analyzer import (  # noqa: E402
    SYSTEM_PROMPT,
    SentimentAnalysis,
    SentimentAnalyzer,
)


def _fake_response(parsed: SentimentAnalysis, *, cache_read: int = 0, cache_create: int = 0):
    return SimpleNamespace(
        parsed_output=parsed,
        stop_reason="end_turn",
        usage=SimpleNamespace(
            input_tokens=80,
            output_tokens=120,
            cache_creation_input_tokens=cache_create,
            cache_read_input_tokens=cache_read,
        ),
    )


def test_system_prompt_is_large_enough_for_haiku_cache():
    """Haiku 4.5 requires >=4096 tokens of prefix to actually cache.

    Mixed EN/ZH content averages ~3 chars/token on the low end. The system
    prompt is >12K chars, comfortably over 4096 tokens.
    """
    assert len(SYSTEM_PROMPT) > 12_000


def test_pydantic_schema_validates_labels():
    valid = SentimentAnalysis(
        label="positive",
        confidence=0.85,
        key_drivers=["beat earnings", "raised guidance"],
        is_clickbait=False,
        reasoning="Earnings beat with raised guidance.",
    )
    assert valid.label == "positive"
    assert 0.0 <= valid.confidence <= 1.0

    with pytest.raises(ValueError):
        SentimentAnalysis(
            label="bullish",  # type: ignore[arg-type] — not in Literal
            confidence=0.9,
            key_drivers=[],
            is_clickbait=False,
            reasoning="x",
        )

    with pytest.raises(ValueError):
        SentimentAnalysis(
            label="positive",
            confidence=1.5,  # out of [0,1]
            key_drivers=[],
            is_clickbait=False,
            reasoning="x",
        )


def test_pydantic_schema_caps_key_drivers_at_five():
    with pytest.raises(ValueError):
        SentimentAnalysis(
            label="positive",
            confidence=0.9,
            key_drivers=["a", "b", "c", "d", "e", "f"],  # 6 > max_length=5
            is_clickbait=False,
            reasoning="x",
        )


@pytest.mark.asyncio
async def test_analyze_sends_cache_control_and_returns_structured():
    parsed = SentimentAnalysis(
        label="positive",
        confidence=0.88,
        key_drivers=["Q3 revenue beat", "raised FY guide"],
        is_clickbait=True,
        reasoning="Title says crash but body shows clean beat.",
    )

    analyzer = SentimentAnalyzer(api_key="test-key", model="claude-haiku-4-5")
    parse_mock = AsyncMock(return_value=_fake_response(parsed, cache_create=5000))

    with patch.object(analyzer.client.messages, "parse", parse_mock):
        result, usage = await analyzer.analyze(
            title="TSMC stock TANKS",
            content="TSMC beat Q3 by 3% and raised guidance.",
            source="finnhub",
            ticker="TSM",
        )

    parse_mock.assert_awaited_once()
    call_kwargs = parse_mock.await_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5"
    assert call_kwargs["system"][0]["text"] == SYSTEM_PROMPT
    assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert call_kwargs["output_format"] is SentimentAnalysis
    user_msg = call_kwargs["messages"][0]["content"]
    assert "TICKER: TSM" in user_msg
    assert "TITLE: TSMC stock TANKS" in user_msg
    assert "SOURCE: finnhub" in user_msg

    assert result.label == "positive"
    assert result.is_clickbait is True
    assert usage["cache_creation_input_tokens"] == 5000
    assert usage["cache_read_input_tokens"] == 0


@pytest.mark.asyncio
async def test_analyze_cache_warm_path():
    """Second call should report cache_read_input_tokens > 0 (we just verify
    that the analyzer surfaces the field — actual caching is server-side)."""
    parsed = SentimentAnalysis(
        label="negative",
        confidence=0.7,
        key_drivers=["miss guidance"],
        is_clickbait=False,
        reasoning="Body confirms title.",
    )
    analyzer = SentimentAnalyzer(api_key="test-key", model="claude-haiku-4-5")
    parse_mock = AsyncMock(return_value=_fake_response(parsed, cache_read=4800))
    with patch.object(analyzer.client.messages, "parse", parse_mock):
        _, usage = await analyzer.analyze(content="Body text here.", title="X")
    assert usage["cache_read_input_tokens"] == 4800


@pytest.mark.asyncio
async def test_analyze_falls_back_to_neutral_on_parse_failure():
    """If the SDK can't parse the response (refusal / schema mismatch),
    we return a neutral placeholder rather than raising — pipeline keeps going."""
    refusal_response = SimpleNamespace(
        parsed_output=None,
        stop_reason="refusal",
        usage=SimpleNamespace(
            input_tokens=80,
            output_tokens=10,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=4800,
        ),
    )
    analyzer = SentimentAnalyzer(api_key="test-key", model="claude-haiku-4-5")
    parse_mock = AsyncMock(return_value=refusal_response)
    with patch.object(analyzer.client.messages, "parse", parse_mock):
        result, _ = await analyzer.analyze(content="suspicious content")
    assert result.label == "neutral"
    assert result.confidence == 0.0
    assert "refusal" in result.reasoning


@pytest.mark.asyncio
async def test_analyze_truncates_long_content():
    """We cap content at 12K chars before sending — sanity check the cap fires."""
    parsed = SentimentAnalysis(
        label="neutral",
        confidence=0.5,
        key_drivers=[],
        is_clickbait=False,
        reasoning="x",
    )
    analyzer = SentimentAnalyzer(api_key="test-key", model="claude-haiku-4-5")
    parse_mock = AsyncMock(return_value=_fake_response(parsed))
    very_long = "X" * 50_000
    with patch.object(analyzer.client.messages, "parse", parse_mock):
        await analyzer.analyze(content=very_long)
    user_msg = parse_mock.await_args.kwargs["messages"][0]["content"]
    # Body should be truncated to 12K, plus the "BODY:\n\n" prefix
    assert "X" * 12_000 in user_msg
    assert "X" * 13_000 not in user_msg
