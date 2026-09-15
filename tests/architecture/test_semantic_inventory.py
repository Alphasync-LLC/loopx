"""Semantics of the repository-wide vocabulary inventory scanner.

The inventory is the map behind the semantic vocabulary registry. These tests
pin the classification rules from the RFC rather than from scanner output:
which carriers count as closed sets, how duplicate constants split into
cross-runtime twins, same-runtime forks, and conflicting values, and that the
committed inventory is regenerated with the code it describes.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from loopx.semantics.inventory import (
    INVENTORY_SCHEMA_VERSION,
    build_inventory,
    render_inventory,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _write(
        tmp_path,
        "loopx/a.py",
        'from enum import Enum\n'
        'from typing import Literal\n'
        'class Kind(str, Enum):\n    ONE = "one"\n    TWO = "two"\n    _private = "ignored"\n'
        'class Mixed(Enum):\n    A = "a"\n    B = 2\n'
        'STATES = frozenset({"open", "closed"})\n'
        'SINGLE = ("only",)\n'
        'NOT_STRINGS = (1, 2)\n'
        'Mode = Literal["fast", "slow"]\n'
        'FOO_SCHEMA_VERSION = "foo_v0"\n'
        'SHARED = "same"\n'
        'CLASHING = "left"\n',
    )
    _write(
        tmp_path,
        "loopx/b.py",
        'SHARED = "same"\n'
        'CLASHING = "right"\n'
        'FOO_SCHEMA_VERSION = "foo_v0"\n'
        'PAIRED_SCHEMA_VERSION = "paired_v0"\n',
    )
    _write(
        tmp_path,
        "loopx/b.ts",
        'export const KINDS = ["one", "two"] as const;\n'
        'export const PAIRED_SCHEMA_VERSION = "paired_v0";\n'
        'export const NOT_CLOSED = ["x"];\n',
    )
    _write(tmp_path, "loopx/__pycache__/junk.py", 'IGNORED = ("a", "b")\n')
    _write(tmp_path, "loopx/node_modules/dep.ts", 'export const IGNORED = ["a", "b"] as const;\n')
    return tmp_path


def test_python_carriers_are_classified_by_shape(repo: Path) -> None:
    inventory = build_inventory(repo)
    enums = {entry["name"]: entry["values"] for entry in inventory["python_enums"]}
    assert enums == {"Kind": ["one", "two"]}, "only string-valued members of string enums are vocabularies"
    closed = {entry["name"]: entry for entry in inventory["python_closed_sets"]}
    assert set(closed) == {"STATES"}, "a closed set needs two or more string members"
    assert closed["STATES"]["container"] == "frozenset"
    assert [entry["values"] for entry in inventory["python_literal_aliases"]] == [["fast", "slow"]]


def test_typescript_as_const_arrays_only(repo: Path) -> None:
    inventory = build_inventory(repo)
    assert [entry["name"] for entry in inventory["typescript_const_arrays"]] == ["KINDS"]


def test_duplicate_constants_split_into_twin_fork_conflict(repo: Path) -> None:
    inventory = build_inventory(repo)["duplicate_definitions"]
    assert [entry["name"] for entry in inventory["cross_runtime_twins"]] == ["PAIRED_SCHEMA_VERSION"]
    assert [entry["name"] for entry in inventory["same_runtime_forks"]] == ["FOO_SCHEMA_VERSION", "SHARED"]
    assert [entry["name"] for entry in inventory["conflicting_values"]] == ["CLASHING"]
    fork = inventory["same_runtime_forks"][0]
    assert fork["is_schema_version"] is True
    assert fork["modules"] == ["loopx/a.py", "loopx/b.py"]


def test_summary_counts_and_skipped_directories(repo: Path) -> None:
    summary = build_inventory(repo)["summary"]
    assert summary["source_files"] == 3, "__pycache__ and node_modules are never scanned"
    assert summary["schema_version_names"] == 2
    assert summary["schema_version_same_runtime_forks"] == 1
    assert summary["cross_runtime_twins"] == 1
    assert summary["same_runtime_forks"] == 2
    assert summary["conflicting_values"] == 1


def test_render_is_deterministic_valid_json(repo: Path) -> None:
    inventory = build_inventory(repo)
    rendered = render_inventory(inventory)
    assert rendered == render_inventory(build_inventory(repo))
    assert json.loads(rendered) == inventory
    assert inventory["schema_version"] == INVENTORY_SCHEMA_VERSION
    # one entry per line keeps diffs reviewable
    assert '    {"name": "Kind", "module": "loopx/a.py", "values": ["one", "two"]}' in rendered


def test_committed_inventory_matches_the_tree() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_semantic_inventory.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
