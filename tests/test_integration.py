import csv
from pathlib import Path

import polars as pl

from oc_botwatch import classify, visualize

GPTBOT_UA = "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)"
CLAUDEBOT_UA = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ClaudeBot/1.0"
GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
NODE_UA = "node"
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

EXPECTED_CLASSIFICATION = [
    {"date": "2026-01-15", "human": 0, "generic_bot": 1, "llm_bot": 2},
    {"date": "2026-01-16", "human": 1, "generic_bot": 1, "llm_bot": 0},
]


def _write_csv(path: Path, rows: list[tuple[str, str]]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "user_agent"])
        writer.writerows(rows)


def _write_input_csvs(input_dir: Path) -> None:
    input_dir.mkdir(parents=True)
    _write_csv(
        input_dir / "2026-01-a.csv",
        [
            ("2026-01-15T08:00:00", GPTBOT_UA),
            ("2026-01-15T09:00:00", CLAUDEBOT_UA),
            ("2026-01-15T10:00:00", GOOGLEBOT_UA),
            ("not-a-date", CHROME_UA),
        ],
    )
    _write_csv(
        input_dir / "2026-01-b.csv",
        [
            ("2026-01-16T11:00:00", NODE_UA),
            ("2026-01-16T12:00:00", CHROME_UA),
        ],
    )


def test_classify_main_end_to_end(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    _write_input_csvs(input_dir)
    output_dir.mkdir()

    classify.main(input_dir=input_dir, output_dir=output_dir)

    out_csv = output_dir / "daily_traffic.csv"
    assert out_csv.exists()
    assert pl.read_csv(out_csv).to_dicts() == EXPECTED_CLASSIFICATION


def test_visualize_main_generates_pngs(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "daily_traffic.csv").write_text(
        "date,human,generic_bot,llm_bot\n"
        "2026-01-15,205984,1978755,33985\n"
        "2026-01-16,156806,1476709,49966\n"
        "2026-01-17,350000,2500000,75000\n",
    )

    visualize.main(output_dir=output_dir)

    assert (output_dir / "daily_traffic.png").exists()
    assert (output_dir / "daily_traffic_pct.png").exists()
