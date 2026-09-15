"""Run the semantic vocabulary drift smoke inside the pull-request pytest sweep.

The canary fleet discovers ``examples/**/*-smoke.py`` on its own, but the fleet
runs after merge and on a schedule, and ``loopx canary premerge`` selects smokes
by changed-path tokens. Neither is a commit-time check for a diff that only
touches ``loopx/``. This wrapper is the PR-path obligation named in the RFC
``docs/architecture/rfcs/semantic-vocabulary-convergence-v0.md`` (Section 10):
the smoke fails closed here on every pull request that runs the Python tests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE = REPO_ROOT / "examples" / "semantic-vocabulary-drift-smoke.py"


def test_semantic_vocabulary_registry_matches_the_code() -> None:
    completed = subprocess.run(
        [sys.executable, "-B", str(SMOKE)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, (
        "semantic vocabulary drift smoke failed; the registry, the inventory, or an "
        "anchor no longer matches the code:\n" + completed.stdout + completed.stderr
    )
    assert completed.stdout.startswith("semantic-vocabulary-drift-smoke: ok"), (
        completed.stdout
    )
