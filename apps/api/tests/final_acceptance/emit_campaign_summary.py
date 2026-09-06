#!/usr/bin/env python3
"""Emit machine-readable Phase 4 final-acceptance campaign summaries from pytest/playwright logs.

Usage (after campaigns):
  python apps/api/tests/final_acceptance/emit_campaign_summary.py \\
    --recovery .fa-recovery.txt \\
    --backup .fa-backup.txt \\
    --performance .fa-perf.txt \\
    --cross .fa-cross.txt \\
    --playwright .fa-playwright.txt
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def parse_pytest(path: Path) -> tuple[int, int, int, str]:
    if not path.is_file():
        return 0, 0, 0, "BLOCKED"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "ERROR:" in text and "No such file" in text:
        return 0, 0, 0, "BLOCKED"
    # pytest -q short summary: "N passed" / "N failed" / "N skipped"
    passed = sum(int(x) for x in re.findall(r"(\d+) passed", text))
    failed = sum(int(x) for x in re.findall(r"(\d+) failed", text))
    skipped = sum(int(x) for x in re.findall(r"(\d+) skipped", text))
    # Also count collected items from verbose lines of form "test_... PASSED"
    if passed == 0 and failed == 0:
        passed = len(re.findall(r"\bPASSED\b", text))
        failed = len(re.findall(r"\bFAILED\b", text))
        skipped = len(re.findall(r"\bSKIPPED\b", text))
    total = passed + failed
    if total == 0 and skipped > 0:
        return skipped, 0, 0, "BLOCKED"
    if total == 0:
        return 0, 0, 0, "BLOCKED"
    return total, passed, failed, "PASS" if failed == 0 else "FAIL"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recovery", type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--performance", type=Path)
    parser.add_argument("--cross", type=Path)
    parser.add_argument("--a11y", type=Path)
    parser.add_argument("--playwright", type=Path)
    args = parser.parse_args()
    for label, path in (
        ("RECOVERY", args.recovery),
        ("BACKUP_RESTORE", args.backup),
        ("PERFORMANCE", args.performance),
        ("ACCESSIBILITY", args.a11y),
        ("PLAYWRIGHT", args.playwright),
    ):
        if path is None:
            continue
        total, passed, failed, status = parse_pytest(path)
        print(f"{label}_TESTS_TOTAL={total}")
        print(f"{label}_TESTS_PASSED={passed}")
        print(f"{label}_TESTS_FAILED={failed}")
        print(f"{label}_ACCEPTANCE={status}")


if __name__ == "__main__":
    main()
