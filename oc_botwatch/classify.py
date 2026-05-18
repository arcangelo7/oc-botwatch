import json
import logging
import re
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "input"

_SKIP_LLM_NAMES: frozenset[str] = frozenset({"Spider", "Code"})

_SUPPLEMENTARY_BOT_PATTERNS: list[str] = [
    r"^node$",
    r"XeraRetractionTracker",
    r"academic-doi-finder",
    r"opencitations-second-hop",
    r"Episciences",
    r"Microsoft\.Data\.Mashup",
    r"PMC_abstract",
]


def _build_llm_pattern() -> str:
    with (BASE_DIR / "ai-robots-txt" / "robots.json").open() as f:
        data: dict[str, object] = json.load(f)
    parts: list[str] = []
    for name in data:
        if name in _SKIP_LLM_NAMES:
            continue
        parts.append(rf"\b{re.escape(name)}\b")
    return "(?i)" + "|".join(parts)


def _build_generic_bot_pattern() -> str:
    with (BASE_DIR / "crawler-user-agents" / "crawler-user-agents.json").open() as f:
        crawlers = json.load(f)
    with (BASE_DIR / "COUNTER-Robots" / "COUNTER_Robots_list.json").open() as f:
        counter = json.load(f)
    patterns: list[str] = []
    for entry in crawlers:
        if "tags" in entry and "ai-crawler" in entry["tags"]:
            continue
        patterns.append(entry["pattern"])
    patterns.extend(entry["pattern"] for entry in counter)
    patterns.extend(_SUPPLEMENTARY_BOT_PATTERNS)
    return "(?i)" + "|".join(patterns)


def classify_traffic() -> pl.DataFrame:
    llm_pat = _build_llm_pattern()
    generic_pat = _build_generic_bot_pattern()

    frames = [
        pl.scan_csv(f, schema_overrides={"user_agent": pl.Utf8, "date": pl.Utf8}).select(
            "date", "user_agent",
        )
        for f in sorted(INPUT_DIR.glob("*.csv"))
    ]

    daily = (
        pl.concat(frames)
        .with_columns(pl.col("date").str.slice(0, 10).alias("date"))
        .filter(pl.col("date").str.contains(r"^\d{4}-\d{2}-\d{2}$"))
        .with_columns(
            pl.when(pl.col("user_agent").str.contains(llm_pat))
            .then(pl.lit("llm_bot"))
            .when(pl.col("user_agent").str.contains(generic_pat))
            .then(pl.lit("generic_bot"))
            .otherwise(pl.lit("human"))
            .alias("category"),
        )
        .group_by("date", "category")
        .len()
        .collect(engine="streaming")
    )

    return (
        daily.pivot(on="category", index="date", values="len")
        .fill_null(0)
        .sort("date")
        .select("date", "human", "generic_bot", "llm_bot")
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    result = classify_traffic()
    out_path = BASE_DIR / "output" / "daily_traffic.csv"
    result.write_csv(out_path)
    logger.info("Output: %s", out_path)


if __name__ == "__main__":
    main()
