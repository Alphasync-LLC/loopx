"""One owner contract, actual validation and independent canonical readback."""

from __future__ import annotations

import hashlib
import json
import sys

import pytest
from canonical_authority_fixture import (
    initialize_canonical_authority,
    isolate_sqlite_runtime,
)

from loopx.control_plane.coordination.runtime_shadow import (
    build_todo_runtime_shadow_projection,
)
from loopx.control_plane.testing.canary_harness import (
    run_json_cli_result,
    write_fixture_registry,
)


@pytest.fixture(params=["file", "sqlite"])
def acceptance_goal(tmp_path, monkeypatch, request):
    if request.param == "sqlite":
        isolate_sqlite_runtime(tmp_path, monkeypatch)
    project = tmp_path / "project"
    project.mkdir()
    state = project / "state.md"
    state.write_text("---\nstatus: active\n---\n# Fixture\n## Agent Todo\n")
    runtime, registry = tmp_path / "runtime", tmp_path / "registry.json"
    write_fixture_registry(
        project=project,
        runtime_root=runtime,
        registry_path=registry,
        goal_id="goal-acceptance",
        domain="acceptance",
        adapter_kind="generic_project_goal_v0",
        state_file=str(state),
        registered_agents=["agent-a"],
    )
    todo = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_export",
        "role": "agent",
        "text": "Write the export artifact",
        "status": "open",
        "done": False,
        "task_class": "advancement_task",
        "action_kind": "implement",
        "index": 1,
        "source_section": "Agent Todo",
        "archive_state": "active",
        "claimed_by": "agent-a",
    }
    projection = build_todo_runtime_shadow_projection(
        goal_id="goal-acceptance", todos=[todo], handoff_mode="soft_claim"
    )
    initialize_canonical_authority(
        runtime, "goal-acceptance", projection, state_path=state, provider=request.param
    )
    document = {
        "objective": "Produce a usable export",
        "non_goals": ["No unrelated code cleanup"],
        "criteria": [
            {
                "id": "export",
                "description": "The exported artifact has the expected content",
                "validation_argv": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; assert Path('artifact.txt').read_text() == 'accepted'",
                ],
                "validation_timeout_seconds": 5,
            }
        ],
        "bindings": [{"todo_id": "todo_export", "criterion_ids": ["export"]}],
    }
    document_path = tmp_path / "acceptance.json"
    document_path.write_text(json.dumps(document))

    def cli(*arguments):
        return run_json_cli_result(
            "goal-acceptance",
            *arguments,
            "--goal-id",
            "goal-acceptance",
            registry_path=registry,
            runtime_root=runtime,
        )

    return project, document_path, cli


def test_owner_configure_validation_failure_success_and_disable(acceptance_goal):
    project, document, cli = acceptance_goal
    code, before = cli("inspect")
    assert code == 0 and before["goal_acceptance_contract"] == {"enabled": False}
    revision = before["provider_revision"]
    code, preview = cli(
        "configure",
        "--document",
        str(document),
        "--expected-provider-revision",
        revision,
    )
    assert code == 0 and preview["status"] == "planned"
    assert cli("inspect")[1] == before
    code, configured = cli(
        "configure",
        "--document",
        str(document),
        "--expected-provider-revision",
        revision,
        "--operation-id",
        "configure-acceptance",
        "--execute",
    )
    assert code == 0, configured
    contract = configured["goal_acceptance_contract"]
    assert contract["enabled"] and contract["tasks"][0]["state"] == "ready"
    assert "validation_argv" not in json.dumps(configured)
    code, failed = cli("verify", "--agent-id", "agent-a", "--execute")
    assert code == 1 and failed["checks_passed"] is False
    assert cli("inspect")[1]["goal_acceptance_contract"]["status"] == "failed"
    (project / "artifact.txt").write_text("accepted")
    code, passed = cli("verify", "--agent-id", "agent-a", "--execute")
    assert code == 0 and passed["checks_passed"] is True, passed
    observed = cli("inspect")[1]
    assert observed["goal_acceptance_contract"]["status"] == "accepted"
    assert "validation_argv" not in json.dumps(observed)
    code, disabled = cli(
        "disable",
        "--expected-provider-revision",
        observed["provider_revision"],
        "--execute",
    )
    assert code == 0 and disabled["goal_acceptance_contract"] == {"enabled": False}


def test_agents_cannot_rewrite_acceptance_and_stale_owner_write_rejects(
    acceptance_goal,
):
    _, document, cli = acceptance_goal
    original = cli("inspect")[1]
    args = (
        "configure",
        "--document",
        str(document),
        "--expected-provider-revision",
        original["provider_revision"],
        "--execute",
    )
    code, error = cli(*args, "--agent-id", "agent-a")
    assert code == 1, error
    assert cli("inspect")[1] == original
    code, configured = cli(*args)
    assert code == 0, configured
    code, error = cli(*args)
    assert code == 1 and "revision" in error["error"], error
    assert cli("inspect")[1]["goal_acceptance_contract"]["revision"] == 1


def test_cli_rejects_claimed_results_and_missing_configuration_basis(acceptance_goal):
    _, document, cli = acceptance_goal
    code, result = cli("configure", "--document", str(document), "--execute")
    assert code == 1 and "expected-provider-revision" in result["error"]
    code, result = cli("verify", "--document", str(document), "--execute")
    assert code == 1 and "configuration arguments" in result["error"]


@pytest.mark.parametrize("change", ["before", "during"])
def test_changed_verifier_cannot_turn_missing_artifact_into_acceptance(
    acceptance_goal, change
):
    project, document_path, cli = acceptance_goal
    verifier = project / "verify.py"
    verifier.write_text(
        "from pathlib import Path\nPath(__file__).write_text('pass\\n')\n"
        if change == "during"
        else "from pathlib import Path\nassert Path('artifact.txt').read_text() == 'accepted'\n"
    )
    document = json.loads(document_path.read_text())
    criterion = document["criteria"][0]
    criterion["validation_argv"] = [sys.executable, "verify.py"]
    criterion["validation_files"] = [
        {
            "path": "verify.py",
            "sha256": hashlib.sha256(verifier.read_bytes()).hexdigest(),
        }
    ]
    document_path.write_text(json.dumps(document))
    basis = cli("inspect")[1]["provider_revision"]
    code, configured = cli(
        "configure",
        "--document",
        str(document_path),
        "--expected-provider-revision",
        basis,
        "--execute",
    )
    assert code == 0, configured
    if change == "before":
        verifier.write_text("pass\n")
    code, result = cli("verify", "--execute")
    assert code == 1 and result["checks_passed"] is False, result
    assert cli("inspect")[1]["goal_acceptance_contract"]["status"] == "failed"


def test_passing_artifact_check_does_not_hide_unconfirmed_work(acceptance_goal):
    project, document_path, cli = acceptance_goal
    document = json.loads(document_path.read_text())
    document["bindings"] = []
    document_path.write_text(json.dumps(document))
    (project / "artifact.txt").write_text("accepted")
    basis = cli("inspect")[1]["provider_revision"]
    code, result = cli(
        "configure",
        "--document",
        str(document_path),
        "--expected-provider-revision",
        basis,
        "--execute",
    )
    assert code == 0, result
    code, result = cli("verify", "--execute")
    assert (
        code == 1
        and result["checks_passed"] is True
        and result["acceptance_ready"] is False
    )
    assert result["goal_acceptance_contract"]["status"] == "held"
