#!/usr/bin/env python3
"""Heuristic: set careers_url from website + /careers when missing.

Does not call search engines. Safe defaults for companies that already have
a website in Mongo/seed. Use --apply to write; default is dry-run.

Examples:
  python -m intel.scripts.backfill_careers_urls --seed
  python -m intel.scripts.backfill_careers_urls --seed --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

SEED_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "seeds" / "companies_seed.json"
)

CAREER_SUFFIXES = ("/careers", "/careers/", "/jobs", "/jobs/")


def guess_careers_url(website: str) -> str | None:
    if not website or not website.startswith("http"):
        return None
    p = urlparse(website)
    if not p.netloc:
        return None
    origin = f"{p.scheme}://{p.netloc}"
    return origin + "/careers"


def patch_seed(*, apply: bool) -> int:
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    changed = 0
    for row in data:
        if row.get("careers_url"):
            continue
        website = row.get("website") or row.get("board_url")
        if not website:
            continue
        guess = guess_careers_url(website)
        if not guess:
            continue
        print(f"{row.get('name')}: {guess}")
        if apply:
            row["careers_url"] = guess
            if row.get("ats_provider") in (None, "unknown"):
                row["ats_provider"] = "json_ld"
            changed += 1
    if apply and changed:
        SEED_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="store_true", help="Operate on companies_seed.json")
    parser.add_argument("--apply", action="store_true", help="Write changes")
    args = parser.parse_args(argv)
    if not args.seed:
        parser.error("Only --seed is supported currently")
    n = patch_seed(apply=args.apply)
    print(f"{'Applied' if args.apply else 'Would update'} {n} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
