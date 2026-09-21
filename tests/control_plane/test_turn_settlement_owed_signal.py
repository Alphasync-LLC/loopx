"""A committed writeback names the quota spend the Turn still owes."""

from __future__ import annotations

import json
from pathlib import Path

from loopx.control_plane.quota.effect_program import SettlementIdentity
from loopx.control_plane.quota.refresh_external_delivery import turn_settlement_owed
from loopx.control_plane.quota.settlement import read_heartbeat_settlement
from loopx.rollout_event_log import rollout_event_log_path
from loopx.state_refresh import refresh_state_run

GOAL_ID = "goal-owed-spend"
AGENT_ID = "agent-owed-spend"
TODO_ID = "todo_owed_spend"
TURN_ID = "turn-owed-spend"

STATE_TEXT = f"""# Active Goal State

## Agent Todo

- [ ] [P1] finish the owed spend signal
  <!-- loopx:todo status=open task_class=advancement_task claimed_by={AGENT_ID} todo_id={TODO_ID} -->
"""


def _append_guard_receipt(runtime_root: Path, identity: SettlementIdentity) -> None:
    path = rollout_event_log_path(runtime_root, GOAL_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "loopx_rollout_event_v0",
                "event_id": "event-owed-guard",
                "event_kind": "quota_should_run",
                "goal_id": GOAL_ID,
                "agent_id": AGENT_ID,
                "run_id": TURN_ID,
                "details": {
                    "todo_id": TODO_ID,
                    "settlement_effect_id": identity.effect_id,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _append_run_index_record(runtime_root: Path, record: dict) -> None:
    path = runtime_root / "goals" / GOAL_ID / "runs" / "index.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _readback(runtime_root: Path, *, spent: bool):
    identity = SettlementIdentity(GOAL_ID, AGENT_ID, TODO_ID, TURN_ID)
    _append_guard_receipt(runtime_root, identity)
    _append_run_index_record(
        runtime_root,
        {
            "classification": "state_refreshed",
            "delivery_outcome": "outcome_progress",
            "goal_id": GOAL_ID,
            "agent_id": AGENT_ID,
            "todo_id": TODO_ID,
            "turn_instance_id": TURN_ID,
        },
    )
    if spent:
        _append_run_index_record(
            runtime_root,
            {
                "classification": "quota_slot_spent",
                "goal_id": GOAL_ID,
                "agent_id": AGENT_ID,
                "todo_id": TODO_ID,
                "turn_instance_id": TURN_ID,
            },
        )
    readback = read_heartbeat_settlement(
        runtime_root,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        todo_id=TODO_ID,
        turn_instance_id=TURN_ID,
    )
    assert readback is not None
    return identity, readback


def test_unspent_turn_names_the_owed_quota_spend(tmp_path: Path) -> None:
    identity, readback = _readback(tmp_path / "runtime", spent=False)

    owed = turn_settlement_owed(readback)

    assert owed is not None
    assert owed["schema_version"] == "turn_settlement_owed_v0"
    assert owed["kind"] == "quota_spend"
    assert owed["effect_id"] == identity.effect_id
    assert owed["todo_id"] == TODO_ID
    assert owed["turn_instance_id"] == TURN_ID
    assert owed["recovery_does_not_spend"] is True
    assert owed["command"].startswith("loopx quota spend-slot")
    assert f"--todo-id {TODO_ID}" in owed["command"]
    assert f"--turn-instance-id {TURN_ID}" in owed["command"]
    assert "--execute" in owed["command"]


def test_spent_turn_owes_nothing(tmp_path: Path) -> None:
    _identity, readback = _readback(tmp_path / "runtime", spent=True)

    assert readback.spend_run is not None
    assert turn_settlement_owed(readback) is None


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    project = tmp_path / "project"
    state_path = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(STATE_TEXT, encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": GOAL_ID,
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state_path.relative_to(project)),
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [AGENT_ID],
                        },
                        "workspace_guard_policy": {
                            "peer_independent_worktree_required": False,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return registry_path, project, tmp_path / "runtime"


def test_refresh_state_result_carries_the_owed_step(tmp_path: Path) -> None:
    registry_path, project, runtime_root = _fixture(tmp_path)
    identity = SettlementIdentity(GOAL_ID, AGENT_ID, TODO_ID, TURN_ID)
    _append_guard_receipt(runtime_root, identity)

    result = refresh_state_run(
        registry_path=registry_path,
        runtime_root_override=str(runtime_root),
        goal_id=GOAL_ID,
        project=project,
        state_file=None,
        classification="validated_progress",
        recommended_action=None,
        delivery_batch_scale="single_surface",
        delivery_outcome="outcome_progress",
        delivery_workspace_path=project,
        todo_id=TODO_ID,
        turn_instance_id=TURN_ID,
        agent_id=AGENT_ID,
        dry_run=False,
        sync_global=False,
    )

    assert result["ok"] is True
    assert result["appended"] is True
    owed = result["settlement_owed"]
    assert owed["effect_id"] == identity.effect_id
    assert owed["kind"] == "quota_spend"
    assert f"--turn-instance-id {TURN_ID}" in owed["command"]
    assert "settlement_owed" not in refresh_state_run(
        registry_path=registry_path,
        runtime_root_override=str(runtime_root),
        goal_id=GOAL_ID,
        project=project,
        state_file=None,
        classification="validated_progress",
        recommended_action=None,
        delivery_batch_scale="single_surface",
        delivery_outcome="outcome_progress",
        delivery_workspace_path=project,
        todo_id=TODO_ID,
        turn_instance_id=TURN_ID,
        agent_id=AGENT_ID,
        dry_run=True,
        sync_global=False,
    )
