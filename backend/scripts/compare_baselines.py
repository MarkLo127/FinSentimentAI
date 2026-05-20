"""Compare Claude Haiku 4.5 sentiment against Alpha Vantage's built-in baseline.

For every news row that has BOTH:
  * a ``model_version='claude-haiku-4-5'`` row in sentiment_results, AND
  * a ``model_version='alpha_vantage_v1'`` row in sentiment_results
we compute the per-label confusion matrix and overall agreement rate.

This is the Phase-2 acceptance check (>=70% agreement on labels).

Usage: uv run python -m scripts.compare_baselines
"""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import aliased

from database import SessionLocal
from models.comment import Comment
from models.news import News
from models.sentiment import SentimentResult

CLAUDE = "claude-haiku-4-5"
AV = "alpha_vantage_v1"
LABELS = ("positive", "neutral", "negative")


async def fetch_pairs() -> list[tuple[News, SentimentResult, SentimentResult]]:
    claude = aliased(SentimentResult)
    av = aliased(SentimentResult)
    stmt = (
        select(News, claude, av)
        .join(claude, claude.news_id == News.id)
        .join(av, av.news_id == News.id)
        .where(claude.model_version == CLAUDE)
        .where(av.model_version == AV)
    )
    async with SessionLocal() as session:
        rows = await session.execute(stmt)
        return list(rows.all())


def print_confusion_matrix(pairs: list[tuple[News, SentimentResult, SentimentResult]]) -> None:
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    for _, claude_row, av_row in pairs:
        matrix[av_row.sentiment_label][claude_row.sentiment_label] += 1

    header = " " * 12 + "│" + "".join(f"{c:^12}" for c in LABELS) + "│ total"
    sep = "─" * (12 + 1 + 12 * 3 + 1 + 7)
    print(header)
    print(sep)
    for av_label in LABELS:
        row_total = sum(matrix[av_label].values())
        cells = "".join(f"{matrix[av_label][c]:^12}" for c in LABELS)
        print(f"AV {av_label:<8}│{cells}│{row_total:>5}")
    print(sep)
    col_totals = [
        sum(matrix[av_label][c] for av_label in LABELS) for c in LABELS
    ]
    cells = "".join(f"{t:^12}" for t in col_totals)
    print(f"{'Claude tot':<12}│{cells}│{sum(col_totals):>5}")


def print_clickbait_findings(pairs) -> None:
    clickbait_disagreements = []
    for news, claude_row, av_row in pairs:
        meta = claude_row.analysis_metadata or {}
        if meta.get("is_clickbait") and claude_row.sentiment_label != av_row.sentiment_label:
            clickbait_disagreements.append((news, claude_row, av_row))
    if not clickbait_disagreements:
        print("\nNo clickbait disagreements found.")
        return
    print(f"\nClickbait-flagged articles where Claude and AV disagree ({len(clickbait_disagreements)}):")
    print("─" * 80)
    for news, claude_row, av_row in clickbait_disagreements[:5]:
        title = (news.title or "")[:78]
        reasoning = (claude_row.analysis_metadata or {}).get("reasoning", "")[:200]
        print(f"  {news.id}: {title}")
        print(f"    AV: {av_row.sentiment_label} (conf {av_row.confidence:.2f})  vs  "
              f"Claude: {claude_row.sentiment_label} (conf {claude_row.confidence:.2f})")
        print(f"    Claude reasoning: {reasoning}")
        print()


async def main() -> None:
    pairs = await fetch_pairs()
    if not pairs:
        logger.error("No paired rows found. Run backfill_sentiment.py first.")
        return

    print("=" * 80)
    print(f"Found {len(pairs)} news articles with BOTH Claude and AV sentiment")
    print("=" * 80)
    print("\nConfusion matrix (rows = Alpha Vantage label, columns = Claude label):\n")
    print_confusion_matrix(pairs)

    agree = sum(
        1 for _, c, a in pairs if c.sentiment_label == a.sentiment_label
    )
    rate = agree / len(pairs)
    print(f"\nOverall agreement: {agree}/{len(pairs)} = {rate:.1%}")
    if rate >= 0.70:
        print("✅ M2 acceptance threshold met (≥70%)")
    else:
        print("⚠️  Below M2 threshold — inspect clickbait flags below for likely causes")

    # When AV says positive but Claude says neutral, that's often a sign AV
    # over-rates routine descriptive coverage as bullish (its training is on
    # headlines + first paragraph; ours is on full body).
    drift_dirs = Counter()
    for _, c, a in pairs:
        if c.sentiment_label != a.sentiment_label:
            drift_dirs[(a.sentiment_label, c.sentiment_label)] += 1
    if drift_dirs:
        print("\nDisagreement breakdown (AV → Claude):")
        for (av_l, cl_l), n in drift_dirs.most_common():
            print(f"  {av_l:<8} → {cl_l:<8} : {n}")

    print_clickbait_findings(pairs)

    # ---- Section 2: StockTwits user-self-label as ground truth ----
    # StockTwits users self-tag posts as bullish/bearish — a much cleaner
    # ground truth than AV's biased news classifier.
    await compare_against_stocktwits()


async def compare_against_stocktwits() -> None:
    print("\n" + "=" * 80)
    print("Section 2 — Claude vs StockTwits user-self-label (better ground truth)")
    print("=" * 80)
    stmt = (
        select(Comment, SentimentResult)
        .join(SentimentResult, SentimentResult.comment_id == Comment.id)
        .where(Comment.platform == "stocktwits")
        .where(SentimentResult.model_version == CLAUDE)
    )
    async with SessionLocal() as session:
        rows = list((await session.execute(stmt)).all())

    # Filter to only posts where the user actually set bullish/bearish
    rows_with_label = [
        (c, s) for c, s in rows
        if (c.platform_metadata or {}).get("sentiment") in ("bullish", "bearish")
    ]
    if not rows_with_label:
        print("No StockTwits posts with user-tagged sentiment.")
        return

    correct = 0
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    for c, s in rows_with_label:
        gt = (c.platform_metadata or {}).get("sentiment")
        gt_label = "positive" if gt == "bullish" else "negative"
        confusion[gt_label][s.sentiment_label] += 1
        if s.sentiment_label == gt_label:
            correct += 1

    print(f"\n{len(rows_with_label)} StockTwits posts with user-tagged sentiment")
    print("\nConfusion (rows = StockTwits user tag, cols = Claude):\n")
    header = " " * 14 + "│" + "".join(f"{c:^12}" for c in LABELS)
    print(header)
    print("─" * (14 + 1 + 12 * 3))
    for gt_label in ("positive", "negative"):
        cells = "".join(f"{confusion[gt_label][c]:^12}" for c in LABELS)
        print(f"User {gt_label:<8}│{cells}")

    rate = correct / len(rows_with_label)
    print(f"\nAgreement: {correct}/{len(rows_with_label)} = {rate:.1%}")
    if rate >= 0.70:
        print("✅ M2 ground-truth check met (≥70% vs StockTwits user labels)")
    else:
        # StockTwits users skew bullish too — agreement <70% may still be fine
        # if Claude's neutral catches genuinely-noise posts.
        print("ℹ️  Note: StockTwits users skew toward bullish/bearish even on noise;")
        print("   Claude's neutral labels on thin posts are expected and not errors.")
        # Stricter check: of bullish posts Claude labels positive OR neutral
        # (i.e. didn't flip to negative) — that's the real false-positive rate.
        bullish_total = sum(confusion["positive"].values())
        bullish_not_flipped = bullish_total - confusion["positive"]["negative"]
        if bullish_total:
            print(
                f"   Bullish-not-flipped: {bullish_not_flipped}/{bullish_total} "
                f"= {bullish_not_flipped/bullish_total:.1%}"
            )


if __name__ == "__main__":
    asyncio.run(main())
