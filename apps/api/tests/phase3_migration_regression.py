"""Shared Phase 3 migration regression helpers.

P3-AC-001 proves the accepted Phase 3 scope boundary remains intact on
descendant implementation branches. That invariant is *not* "Alembic head
remains 0003"; it is that accepted Phase 1–3 migrations are unchanged and
remain an ancestor of the current linear migration chain.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

PHASE3_BASELINE_TAG = "v0.3.0-phase3"
PHASE3_HEAD_REVISION = "0003_phase3_brew_day_os"
PHASE3_MIGRATION_PATHS = (
    "database/migrations/versions/0001_phase1a.py",
    "database/migrations/versions/0002_phase2_brewing_core.py",
    "database/migrations/versions/0003_phase3_brew_day_os.py",
)


def migration_versions_dir(root: Path) -> Path:
    return root / "database/migrations/versions"


def load_migration_revision_graph(root: Path) -> dict[str, str | None]:
    revisions: dict[str, str | None] = {}
    for path in sorted(migration_versions_dir(root).glob("[0-9]*.py")):
        body = path.read_text(encoding="utf-8")
        revision_match = re.search(r'^revision:\s*str\s*=\s*"([^"]+)"', body, re.M)
        down_revision_match = re.search(
            r'^down_revision:\s*str\s*\|\s*None\s*=\s*(?:"([^"]+)"|None)',
            body,
            re.M,
        )
        if revision_match is None:
            continue
        down_revision = down_revision_match.group(1) if down_revision_match else None
        revisions[revision_match.group(1)] = down_revision
    return revisions


def migration_heads(revisions: dict[str, str | None]) -> set[str]:
    referenced = {down for down in revisions.values() if down}
    return set(revisions) - referenced


def migration_ancestors(revisions: dict[str, str | None], revision: str) -> list[str]:
    chain: list[str] = []
    current: str | None = revision
    seen: set[str] = set()
    while current:
        if current in seen:
            raise ValueError(f"cycle detected at migration revision {current}")
        seen.add(current)
        chain.append(current)
        current = revisions.get(current)
    return chain


def assert_phase3_migrations_unchanged(root: Path) -> None:
    for relative in PHASE3_MIGRATION_PATHS:
        assert (root / relative).is_file(), f"missing accepted migration {relative}"
    if not (root / ".git").exists() or not shutil.which("git"):
        return
    for relative in PHASE3_MIGRATION_PATHS:
        diff = subprocess.check_output(
            ["git", "diff", PHASE3_BASELINE_TAG, "HEAD", "--", relative],
            cwd=root,
            text=True,
            encoding="utf-8",
        )
        assert diff == "", f"{relative} changed since {PHASE3_BASELINE_TAG}"


def assert_phase3_migration_ancestry(root: Path, *, head_revision: str | None = None) -> str:
    revisions = load_migration_revision_graph(root)
    heads = migration_heads(revisions)
    assert len(heads) == 1, f"expected one Alembic head, found {heads}"
    head = head_revision or next(iter(heads))
    assert head in heads, f"{head} is not an Alembic head; heads={heads}"
    ancestry = migration_ancestors(revisions, head)
    assert PHASE3_HEAD_REVISION in ancestry, (
        f"{PHASE3_HEAD_REVISION} is not an ancestor of head {head}; chain={ancestry}"
    )
    assert ancestry[-1] == "0001_phase1a"
    assert revisions["0002_phase2_brewing_core"] == "0001_phase1a"
    assert revisions[PHASE3_HEAD_REVISION] == "0002_phase2_brewing_core"
    return head
