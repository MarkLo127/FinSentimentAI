"""Unit tests for the 6 fetchers using respx to mock httpx.

These tests do NOT hit live APIs — they validate parsing/transformation only.
"""

from __future__ import annotations

import os

import httpx
import pytest
import respx

# Force config to load with predictable values (avoids reading real .env)
os.environ.setdefault("MARKETAUX_API_KEY", "test-key")
os.environ.setdefault("FINNHUB_API_KEY", "test-key")
os.environ.setdefault("NEWSAPI_KEY", "test-key")
os.environ.setdefault("ALPHA_VANTAGE_KEY", "test-key")

from services.fetchers.alpha_vantage import AlphaVantageFetcher, _map_sentiment_label
from services.fetchers.base import NewsItem, SocialPost
from services.fetchers.finnhub import FinnhubFetcher
from services.fetchers.marketaux import MarketauxFetcher
from services.fetchers.newsapi import NewsApiFetcher
from services.fetchers.ptt import PttFetcher
from services.fetchers.stocktwits import StockTwitsFetcher


def test_url_hash_stable():
    item = NewsItem(source="marketaux", title="t", url="https://example.com/a")
    assert item.url_hash == NewsItem(source="x", title="x", url="https://example.com/a").url_hash


@pytest.mark.asyncio
@respx.mock
async def test_marketaux_parsing():
    respx.get("https://api.marketaux.com/v1/news/all").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "title": "TSM beats estimates",
                        "url": "https://example.com/a",
                        "snippet": "Strong quarter",
                        "language": "en",
                        "published_at": "2026-05-15T10:00:00Z",
                    }
                ]
            },
        )
    )
    items = await MarketauxFetcher().fetch_news("TSM")
    assert len(items) == 1
    assert items[0].source == "marketaux"
    assert items[0].summary == "Strong quarter"
    assert items[0].published_at is not None


@pytest.mark.asyncio
@respx.mock
async def test_finnhub_parsing():
    respx.get("https://finnhub.io/api/v1/company-news").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "headline": "AAPL launches new chip",
                    "url": "https://example.com/b",
                    "summary": "M5 announced",
                    "datetime": 1747310400,
                }
            ],
        )
    )
    items = await FinnhubFetcher().fetch_news("AAPL")
    assert len(items) == 1
    assert items[0].source == "finnhub"
    assert items[0].title == "AAPL launches new chip"


@pytest.mark.asyncio
@respx.mock
async def test_newsapi_parsing():
    respx.get("https://newsapi.org/v2/everything").mock(
        return_value=httpx.Response(
            200,
            json={
                "articles": [
                    {
                        "title": "NVDA hits new high",
                        "url": "https://example.com/c",
                        "description": "Record earnings",
                        "publishedAt": "2026-05-15T08:00:00Z",
                    }
                ]
            },
        )
    )
    items = await NewsApiFetcher().fetch_news("NVDA")
    assert len(items) == 1
    assert items[0].source == "newsapi"


def test_alpha_vantage_label_mapping():
    assert _map_sentiment_label("Bullish") == "positive"
    assert _map_sentiment_label("Somewhat-Bearish") == "negative"
    assert _map_sentiment_label("Neutral") == "neutral"
    assert _map_sentiment_label(None) is None
    assert _map_sentiment_label("unknown") is None


@pytest.mark.asyncio
@respx.mock
async def test_alpha_vantage_baseline_extraction():
    respx.get("https://www.alphavantage.co/query").mock(
        return_value=httpx.Response(
            200,
            json={
                "feed": [
                    {
                        "title": "TSLA delivers record Q",
                        "url": "https://example.com/d",
                        "summary": "Strong Q1",
                        "time_published": "20260515T103000",
                        "overall_sentiment_label": "Bullish",
                        "overall_sentiment_score": 0.42,
                    }
                ]
            },
        )
    )
    items = await AlphaVantageFetcher().fetch_news("TSLA")
    assert len(items) == 1
    assert items[0].baseline_sentiment_label == "positive"
    assert items[0].baseline_sentiment_score == 0.42


@pytest.mark.asyncio
@respx.mock
async def test_alpha_vantage_rate_limit_returns_empty():
    respx.get("https://www.alphavantage.co/query").mock(
        return_value=httpx.Response(
            200,
            json={"Information": "Thank you for using Alpha Vantage. Daily limit reached."},
        )
    )
    assert await AlphaVantageFetcher().fetch_news("TSLA") == []


@pytest.mark.asyncio
@respx.mock
async def test_stocktwits_extracts_bullish_label():
    respx.get("https://api.stocktwits.com/api/2/streams/symbol/TSM.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "messages": [
                    {
                        "id": 123,
                        "body": "TSM to the moon",
                        "created_at": "2026-05-15T10:00:00Z",
                        "user": {"username": "trader42"},
                        "entities": {"sentiment": {"basic": "Bullish"}},
                    }
                ]
            },
        )
    )
    posts = await StockTwitsFetcher().fetch_social("TSM")
    assert len(posts) == 1
    assert posts[0].platform == "stocktwits"
    assert posts[0].platform_metadata["sentiment"] == "bullish"


@pytest.mark.asyncio
@respx.mock
async def test_stocktwits_404_returns_empty():
    respx.get("https://api.stocktwits.com/api/2/streams/symbol/UNKNOWN.json").mock(
        return_value=httpx.Response(404)
    )
    assert await StockTwitsFetcher().fetch_social("UNKNOWN") == []


@pytest.mark.asyncio
@respx.mock
async def test_ptt_extracts_article_links_via_jina():
    index_md = (
        "# 看板 Stock\n\n"
        "[Re: [標的] 美麗國股票](https://www.ptt.cc/bbs/Stock/M.1778849789.A.92B.html)\n"
        "peter98\n\n"
        "[Re: [情報] 台積電](https://www.ptt.cc/bbs/Stock/M.1778849790.A.92C.html)\n"
    )
    article_md = "標題: Test\n推 user1: 看好\n推 user2: 同意\n噓 user3: 不認同\n本文..."

    route = respx.get(url__startswith="https://r.jina.ai/").mock(
        side_effect=[
            httpx.Response(200, text=index_md),
            httpx.Response(200, text=article_md),
            httpx.Response(200, text=article_md),
        ]
    )

    posts = await PttFetcher(post_limit=2).fetch_social("2330")
    assert route.call_count == 3
    assert len(posts) == 2
    assert posts[0].platform == "ptt"
    assert posts[0].platform_metadata["push"] >= 2
    assert posts[0].platform_metadata["boo"] >= 1


def test_socialpost_url_hash_stable():
    p = SocialPost(platform="ptt", content="x", post_url="https://www.ptt.cc/a.html")
    assert len(p.url_hash) == 64
