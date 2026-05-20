"""Unit tests for the StockDayBucket score formula.

The integration test (real DB UPSERT + idempotency) runs as part of the
manual verification step in run_daily_summary.py — we don't spin up
Postgres for unit tests.
"""

from datetime import date

from services.daily_summary import StockDayBucket


def test_score_pure_positive():
    b = StockDayBucket(stock_id=1, summary_date=date(2026, 5, 15))
    b.positive_count = 2
    b.positive_conf_sum = 0.9 + 0.8  # 1.7
    assert b.total == 2
    assert b.score == round(1.7 / 2, 4)


def test_score_pure_negative():
    b = StockDayBucket(stock_id=1, summary_date=date(2026, 5, 15))
    b.negative_count = 3
    b.negative_conf_sum = 0.7 + 0.6 + 0.85  # 2.15
    assert b.score == round(-2.15 / 3, 4)


def test_score_neutrals_dilute():
    """Neutrals contribute to total but NOT to the numerator."""
    b = StockDayBucket(stock_id=1, summary_date=date(2026, 5, 15))
    b.positive_count = 1
    b.positive_conf_sum = 0.9
    b.neutral_count = 9  # heavy dilution
    assert b.total == 10
    # 0.9 / 10 = 0.09
    assert b.score == 0.09


def test_score_balanced_yields_zero():
    b = StockDayBucket(stock_id=1, summary_date=date(2026, 5, 15))
    b.positive_count = 1
    b.positive_conf_sum = 0.8
    b.negative_count = 1
    b.negative_conf_sum = 0.8
    assert b.score == 0.0


def test_score_empty_bucket_returns_none():
    b = StockDayBucket(stock_id=1, summary_date=date(2026, 5, 15))
    assert b.total == 0
    assert b.score is None


def test_score_strongly_positive_within_threshold():
    """Per plan §4: score > 0.3 is 'market偏樂觀'."""
    b = StockDayBucket(stock_id=1, summary_date=date(2026, 5, 15))
    b.positive_count = 5
    b.positive_conf_sum = 5 * 0.85  # 4.25
    assert b.score > 0.3


def test_score_strongly_negative_within_threshold():
    """score < -0.3 is 'market偏悲觀'."""
    b = StockDayBucket(stock_id=1, summary_date=date(2026, 5, 15))
    b.negative_count = 5
    b.negative_conf_sum = 5 * 0.80
    assert b.score < -0.3
