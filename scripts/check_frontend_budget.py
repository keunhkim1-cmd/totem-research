#!/usr/bin/env python3
"""Check static frontend asset size budgets."""

from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AssetBudget:
    path: str
    raw_limit: int
    gzip_limit: int


ASSETS = (
    AssetBudget("index.html", raw_limit=20 * 1024, gzip_limit=5 * 1024),
    AssetBudget("assets/app.css", raw_limit=2 * 1024, gzip_limit=1 * 1024),
    AssetBudget("assets/css/base.css", raw_limit=24 * 1024, gzip_limit=6 * 1024),
    AssetBudget("assets/css/secondary-pages.css", raw_limit=12 * 1024, gzip_limit=4 * 1024),
    AssetBudget("assets/css/terminal.css", raw_limit=32 * 1024, gzip_limit=8 * 1024),
    AssetBudget("assets/css/about.css", raw_limit=12 * 1024, gzip_limit=4 * 1024),
    AssetBudget("assets/css/responsive.css", raw_limit=12 * 1024, gzip_limit=4 * 1024),
    AssetBudget("assets/app.js", raw_limit=12 * 1024, gzip_limit=4 * 1024),
    AssetBudget("assets/app/state.js", raw_limit=4 * 1024, gzip_limit=1 * 1024),
    AssetBudget("assets/app/dom_utils.js", raw_limit=8 * 1024, gzip_limit=3 * 1024),
    AssetBudget("assets/app/calendar.js", raw_limit=2 * 1024, gzip_limit=1 * 1024),
    AssetBudget("assets/app/warning_render.js", raw_limit=24 * 1024, gzip_limit=6 * 1024),
    AssetBudget("assets/app/chart.js", raw_limit=12 * 1024, gzip_limit=4 * 1024),
    AssetBudget("assets/app/search.js", raw_limit=20 * 1024, gzip_limit=5 * 1024),
    AssetBudget("assets/secondary_pages.js", raw_limit=16 * 1024, gzip_limit=6 * 1024),
    AssetBudget("assets/trading_calendar.js", raw_limit=8 * 1024, gzip_limit=3 * 1024),
)

TOTAL_RAW_LIMIT = 200 * 1024
TOTAL_GZIP_LIMIT = 48 * 1024


def byte_size(n: int) -> str:
    return f"{n / 1024:.1f} KB"


def measure(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    return len(data), len(gzip.compress(data, compresslevel=9, mtime=0))


def build_report() -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
    rows: list[dict[str, object]] = []
    failures: list[str] = []

    for asset in ASSETS:
        full_path = ROOT / asset.path
        raw_size, gzip_size = measure(full_path)
        raw_ok = raw_size <= asset.raw_limit
        gzip_ok = gzip_size <= asset.gzip_limit
        rows.append(
            {
                "path": asset.path,
                "raw_bytes": raw_size,
                "raw_limit": asset.raw_limit,
                "raw_ok": raw_ok,
                "gzip_bytes": gzip_size,
                "gzip_limit": asset.gzip_limit,
                "gzip_ok": gzip_ok,
            }
        )
        if not raw_ok:
            failures.append(
                f"{asset.path} raw size {byte_size(raw_size)} exceeds {byte_size(asset.raw_limit)}"
            )
        if not gzip_ok:
            failures.append(
                f"{asset.path} gzip size {byte_size(gzip_size)} exceeds {byte_size(asset.gzip_limit)}"
            )

    total_raw = sum(int(row["raw_bytes"]) for row in rows)
    total_gzip = sum(int(row["gzip_bytes"]) for row in rows)
    total = {
        "raw_bytes": total_raw,
        "raw_limit": TOTAL_RAW_LIMIT,
        "raw_ok": total_raw <= TOTAL_RAW_LIMIT,
        "gzip_bytes": total_gzip,
        "gzip_limit": TOTAL_GZIP_LIMIT,
        "gzip_ok": total_gzip <= TOTAL_GZIP_LIMIT,
    }
    if not total["raw_ok"]:
        failures.append(
            f"total raw size {byte_size(total_raw)} exceeds {byte_size(TOTAL_RAW_LIMIT)}"
        )
    if not total["gzip_ok"]:
        failures.append(
            f"total gzip size {byte_size(total_gzip)} exceeds {byte_size(TOTAL_GZIP_LIMIT)}"
        )

    return rows, total, failures


def print_table(rows: list[dict[str, object]], total: dict[str, object]) -> None:
    print("Frontend asset budget")
    print("-" * 78)
    print(f"{'asset':<22} {'raw':>9} {'raw limit':>11} {'gzip':>9} {'gzip limit':>11} status")
    print("-" * 78)
    for row in rows:
        status = "ok" if row["raw_ok"] and row["gzip_ok"] else "fail"
        print(
            f"{str(row['path']):<22} "
            f"{byte_size(int(row['raw_bytes'])):>9} "
            f"{byte_size(int(row['raw_limit'])):>11} "
            f"{byte_size(int(row['gzip_bytes'])):>9} "
            f"{byte_size(int(row['gzip_limit'])):>11} "
            f"{status}"
        )
    status = "ok" if total["raw_ok"] and total["gzip_ok"] else "fail"
    print("-" * 78)
    print(
        f"{'total':<22} "
        f"{byte_size(int(total['raw_bytes'])):>9} "
        f"{byte_size(int(total['raw_limit'])):>11} "
        f"{byte_size(int(total['gzip_bytes'])):>9} "
        f"{byte_size(int(total['gzip_limit'])):>11} "
        f"{status}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check frontend static asset size budgets.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    try:
        rows, total, failures = build_report()
    except FileNotFoundError as exc:
        print(f"Missing frontend asset: {exc.filename}")
        return 1

    if args.json:
        print(json.dumps({"assets": rows, "total": total, "failures": failures}, ensure_ascii=False, indent=2))
    else:
        print_table(rows, total)
        if failures:
            print("\nFailures:")
            for failure in failures:
                print(f"- {failure}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
