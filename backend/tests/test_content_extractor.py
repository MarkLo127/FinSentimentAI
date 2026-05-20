"""Tests for the three-layer fallback content extractor."""

from __future__ import annotations

import httpx
import pytest
import respx

from services.content_extractor import MIN_CONTENT_CHARS, fetch_full_content

LONG_TEXT = "Article body. " * 100  # ~1400 chars, well over MIN
SHORT_TEXT = "Too short"  # below MIN


@pytest.mark.asyncio
@respx.mock
async def test_layer1_jina_success():
    """Jina returns >=500 chars → use it, skip other layers."""
    respx.get("https://r.jina.ai/https://example.com/article").mock(
        return_value=httpx.Response(200, text=LONG_TEXT)
    )
    # If Jina succeeds we should NOT hit example.com directly
    direct = respx.get("https://example.com/article").mock(
        return_value=httpx.Response(500)
    )

    result = await fetch_full_content("https://example.com/article")
    assert result.fetched_via == "jina"
    assert result.length >= MIN_CONTENT_CHARS
    assert not direct.called


@pytest.mark.asyncio
@respx.mock
async def test_layer2_trafilatura_when_jina_short():
    """Jina returns < 500 chars → fall through to trafilatura."""
    respx.get("https://r.jina.ai/https://example.com/short-jina").mock(
        return_value=httpx.Response(200, text=SHORT_TEXT)
    )
    html_body = (
        "<html><body>"
        "<article>" + ("Real story paragraph. " * 80) + "</article>"
        "</body></html>"
    )
    respx.get("https://example.com/short-jina").mock(
        return_value=httpx.Response(200, text=html_body)
    )

    result = await fetch_full_content("https://example.com/short-jina")
    assert result.fetched_via == "trafilatura"
    assert result.length >= MIN_CONTENT_CHARS


@pytest.mark.asyncio
@respx.mock
async def test_layer3_snippet_when_jina_and_trafilatura_fail():
    """Jina errors AND trafilatura returns nothing → use snippet."""
    respx.get("https://r.jina.ai/https://example.com/dead").mock(
        return_value=httpx.Response(500)
    )
    respx.get("https://example.com/dead").mock(
        return_value=httpx.Response(404, text="<html><body>Not Found</body></html>")
    )

    result = await fetch_full_content(
        "https://example.com/dead",
        fallback_snippet="API-provided summary text.",
    )
    assert result.fetched_via == "snippet"
    assert result.text == "API-provided summary text."


@pytest.mark.asyncio
@respx.mock
async def test_layer3_snippet_when_all_short():
    """If Jina returns short text AND trafilatura returns short text → snippet."""
    respx.get("https://r.jina.ai/https://example.com/thin").mock(
        return_value=httpx.Response(200, text=SHORT_TEXT)
    )
    respx.get("https://example.com/thin").mock(
        return_value=httpx.Response(200, text="<html><body>tiny</body></html>")
    )

    result = await fetch_full_content(
        "https://example.com/thin", fallback_snippet="snippet here"
    )
    assert result.fetched_via == "snippet"


@pytest.mark.asyncio
@respx.mock
async def test_no_snippet_returns_empty_string():
    """When all layers fail and no snippet provided, return empty string but valid object."""
    respx.get("https://r.jina.ai/https://example.com/none").mock(
        return_value=httpx.Response(500)
    )
    respx.get("https://example.com/none").mock(return_value=httpx.Response(404))

    result = await fetch_full_content("https://example.com/none")
    assert result.fetched_via == "snippet"
    assert result.text == ""
    assert result.length == 0


@pytest.mark.asyncio
@respx.mock
async def test_jina_timeout_falls_through():
    """Jina timeout/exception → trafilatura tried next."""
    respx.get("https://r.jina.ai/https://example.com/slow").mock(
        side_effect=httpx.TimeoutException("slow")
    )
    html_body = "<html><body><article>" + ("Story paragraph. " * 80) + "</article></body></html>"
    respx.get("https://example.com/slow").mock(
        return_value=httpx.Response(200, text=html_body)
    )

    result = await fetch_full_content("https://example.com/slow")
    assert result.fetched_via == "trafilatura"
