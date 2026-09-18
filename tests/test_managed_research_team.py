"""Real File/SQLite authority and CLI composition; only model execution is substituted."""
import json
import asyncio
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples" / "managed-research-team"))
import research_team as demo  # noqa: E402
from acceptance import canonical_tasks, todo_id, validate_delivery  # noqa: E402
from scenario import encoded  # noqa: E402
from test_managed_research_scenario import fixture  # noqa: E402
from loopx.control_plane.goals.acceptance import (  # noqa: E402
    configure_goal_acceptance, inspect_goal_acceptance, verify_goal_acceptance,
)


@pytest.fixture(params=["file", "sqlite"])
def team(tmp_path, monkeypatch, request):
    monkeypatch.setenv("NODE_OPTIONS", os.environ.get("NODE_OPTIONS", "") + " --experimental-sqlite")
    for variable in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(variable, str(tmp_path))
    root = tmp_path / "team"
    demo.prepare(root, request.param)
    return root


def plan(root, actor, revision):
    return demo.cli(root, "turn", "plan", "--goal-id", demo.GOAL, "--agent-id", actor,
                    "--todo-id", todo_id(actor, revision), "--host", "dsh",
                    "--scan-root", str(root / actor / revision))


def test_canonical_delivery_requires_completed_current_dependencies(team, monkeypatch):
    root = team
    fixture(root)
    route = dict(registry_path=root / "registry.json", goal_id=demo.GOAL,
                 runtime_root=str(root / "runtime"))
    before = inspect_goal_acceptance(**route)
    # Both choices are available; explicit request must select exactly the second,
    # independently of canonical ordering / the controller's default.
    selected = plan(root, "analyst", "initial")
    assert selected["turn_envelope"]["action"]["selected_todo"]["todo_id"] == "todo_analyst-initial", selected
    assert inspect_goal_acceptance(**route)["provider_revision"] == before["provider_revision"]
    # All artifact hashes and cached accepted files exist, but canonical work is open.
    with pytest.raises(ValueError, match="canonical_dependency_incomplete"):
        validate_delivery(root)
    with pytest.raises(RuntimeError, match="goal_acceptance_validation_rejected"):
        demo.complete(root, "lead", "report")
    assert not canonical_tasks(root)["todo_lead-report"]["done"]

    # A child closes without requiring its parent's report. The real TS owner
    # runs only that child's pinned criterion, then commits terminal state.
    report = root / "lead" / "report.json"
    original_report = report.read_bytes()
    report.unlink()
    done = demo.complete(root, "analyst", "initial")
    assert done["changed"] is True
    assert [row["criterion_id"] for row in done["goal_acceptance_completion"]["results"]] == ["analyst-initial"]
    report.write_bytes(original_report)
    # Completion always reruns artifact validation; a prior independent verify
    # cannot authorize changed output. Restore and complete the same task.
    output = root / "analyst" / "corrected" / "output.json"
    good_output = output.read_bytes()
    verification = verify_goal_acceptance(**route, execute=True)
    results = verification["goal_acceptance_contract"]["verification"]["results"]
    assert next(row for row in results if row["criterion_id"] == "analyst-corrected")["passed"]
    bad = json.loads(good_output)
    bad["normalized_fcf"] = 75
    output.write_bytes(encoded(bad))
    with pytest.raises(RuntimeError, match="goal_acceptance_validation_rejected"):
        demo.complete(root, "analyst", "corrected")
    assert not canonical_tasks(root)["todo_analyst-corrected"]["done"]
    output.write_bytes(good_output)
    demo.complete(root, "analyst", "corrected")

    # A model cannot reconfigure the owner contract after semantic task edits.
    demo.cli(root, "todo", "update", "--goal-id", demo.GOAL, "--agent-id", "reviewer",
             "--todo-id", "todo_reviewer-initial", "--text", "Independently analyze the initial filing and sources")
    with pytest.raises(RuntimeError, match="goal_acceptance_stale"):
        demo.complete(root, "reviewer", "initial")
    document = json.loads((root / "bootstrap.json").read_text())["document"]
    provider_revision = inspect_goal_acceptance(**route)["provider_revision"]
    with pytest.raises(ValueError):
        configure_goal_acceptance(**route, document=document, agent_id="lead",
                                  expected_provider_revision=provider_revision, execute=True)
    held = plan(root, "reviewer", "initial")
    assert not held.get("turn_envelope", {}).get("action", {}).get("delivery_allowed", False), held
    # Explicit owner amendment for this negative fixture, never done by delegate().
    configure_goal_acceptance(**route, document=json.loads((root / "bootstrap.json").read_text())["document"],
                              expected_provider_revision=inspect_goal_acceptance(**route)["provider_revision"], execute=True)
    demo.complete(root, "reviewer", "initial")

    validator = root / "project" / "validation" / "scenario.py"
    original_validator = validator.read_bytes()
    validator.write_bytes(original_validator + b"\n# changed validator\n")
    with pytest.raises(RuntimeError, match="goal_acceptance_validation_rejected"):
        demo.complete(root, "reviewer", "corrected")
    validator.write_bytes(original_validator)
    demo.complete(root, "reviewer", "corrected")

    invalid_report = json.loads(original_report)
    invalid_report["dependencies"]["analyst/corrected"] = invalid_report["dependencies"]["analyst/initial"]
    report.write_bytes(encoded(invalid_report))
    with pytest.raises(RuntimeError, match="goal_acceptance_validation_rejected"):
        demo.complete(root, "lead", "report")
    report.write_bytes(original_report)
    demo.complete(root, "lead", "report")
    assert all(row["done"] for row in canonical_tasks(root).values())
    assert verify_goal_acceptance(**route, execute=True)["acceptance_ready"]
    assert json.loads((root / "registry.json").read_text())["goals"][0]["status"] == "active"


def test_bootstrap_refuses_existing_state(team):
    root = team
    before = canonical_tasks(root)
    repeated = subprocess.run(["node", "--no-warnings", "--experimental-sqlite", "--experimental-strip-types",
                              str(demo.HERE / "bootstrap.ts"), str(root)], capture_output=True)
    assert repeated.returncode != 0
    with pytest.raises(ValueError, match="new_disposable"):
        demo.prepare(root)
    assert canonical_tasks(root) == before


def test_cloud_member_mcp_requires_bound_identity_and_completed_upstream(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    root = tmp_path / "member-tools"
    demo.prepare(root, topology="local-led")
    fixture(root)
    workspace = root / "cloud-reviewer" / "initial"
    (workspace / "TASK.md").write_text("Independently review the accepted local analysis")
    env = {**os.environ, "LOOPX_RESEARCH_DEMO_ROOT": str(root),
           "LOOPX_TURN_GOAL_ID": demo.GOAL, "LOOPX_TURN_AGENT_ID": "cloud-reviewer",
           "LOOPX_TURN_TODO_ID": "todo_cloud-reviewer-initial", "LOOPX_TURN_WORKSPACE": str(workspace)}

    async def call(environment):
        params = StdioServerParameters(command=sys.executable,
            args=[str(demo.HERE / "server.py"), "--worker", "cloud-reviewer", "--revision", "initial"],
            env=environment, cwd=str(workspace))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                assert {"read_input", "write_output", "read_context", "assess_request"} <= {row.name for row in (await session.list_tools()).tools}
                return await session.call_tool("read_input", {})

    assert "incomplete" in str(asyncio.run(call(env)))
    demo.complete(root, "local-analyst", "initial")
    assert not asyncio.run(call(env)).isError
    assert asyncio.run(call({**env, "LOOPX_TURN_TODO_ID": "todo_someone_else"})).isError
    assert not canonical_tasks(root)["todo_cloud-reviewer-initial"]["done"]
