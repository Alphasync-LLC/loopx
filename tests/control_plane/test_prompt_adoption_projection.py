from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from loopx.control_plane.heartbeat import automation_upgrade as upgrade
from loopx.control_plane.heartbeat import installed_prompt_update as lifecycle
from loopx.control_plane.quota.should_run import build_quota_should_run
from loopx.control_plane.scheduler.execution_context import (
    scheduler_execution_context_for_runtime_profile,
)
from loopx.control_plane.testing.quota_fixtures import (
    quota_status_payload,
    quota_todo_item,
)


APP_CONTEXT = scheduler_execution_context_for_runtime_profile("codex_app_heartbeat")
CLI_CONTEXT = scheduler_execution_context_for_runtime_profile("codex_cli")
GOAL_ID = "fixture-goal"
AGENT_ID = "agent-a"
THREAD_ID = "thread-a"
FROZEN_BODY = f"Advance `{GOAL_ID}` from registry. --agent-id {AGENT_ID}"
DESIRED_BODY = "LoopX managed heartbeat bootstrap v2"


def _host_with_frozen_body(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "host"
    path = home / "automations/watch/automation.toml"
    path.parent.mkdir(parents=True)
    path.write_text('version = 1\nid = "watch"\nname = "Fixture watch"\nkind = "heartbeat"\n'
                    'status = "PAUSED"\ntarget_thread_id = "' + THREAD_ID + '"\n'
                    'rrule = "FREQ=MINUTELY;INTERVAL=3"\n'
                    'prompt = ' + json.dumps(FROZEN_BODY) + "\n", encoding="utf-8")
    database = home / "sqlite/codex-dev.db"
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE automations (id TEXT PRIMARY KEY, kind TEXT, prompt TEXT,"
                           " status TEXT, target_thread_id TEXT, rrule TEXT, model TEXT,"
                           " updated_at INTEGER, next_run_at INTEGER)")
        connection.execute("INSERT INTO automations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("watch", "heartbeat", FROZEN_BODY, "PAUSED", THREAD_ID,
             "FREQ=MINUTELY;INTERVAL=3", "fixture-model", 123, 456))
    registry = tmp_path / "registry.json"
    state = tmp_path / "STATE.md"
    state.write_text("# Fixture\n", encoding="utf-8")
    registry.write_text(json.dumps({"goals": [{"id": GOAL_ID, "repo": str(tmp_path),
        "state_file": str(state), "registered_agents": [AGENT_ID]}]}), encoding="utf-8")
    return home, registry


def _record_deferred_adoption(tmp_path: Path, home: Path, desired: str) -> None:
    """Store the reviewed request an update-time reconciliation could not apply."""

    lifecycle.update_pending_adoptions(runtime_root=tmp_path / "runtime", codex_home=str(home),
        resolved=[],
        pending=[{"automation_id": "watch", "goal_id": GOAL_ID, "agent_id": AGENT_ID,
            "automation_status": "PAUSED", "codex_home": str(home),
            "expected_prompt_sha256": upgrade.digest(FROZEN_BODY),
            "desired_sha256": upgrade.digest(desired),
            "source": "update_time_reconciliation",
            "api_update_request": upgrade.automation_update_request(automation_id="watch",
                manifest={"name": "Fixture watch", "status": "PAUSED",
                          "rrule": "FREQ=MINUTELY;INTERVAL=3", "target_thread_id": THREAD_ID},
                expected_prompt_sha256=upgrade.digest(FROZEN_BODY), desired_prompt=desired)}])


def _lane_payload(tmp_path: Path, registry: Path) -> dict:
    """One runnable lane whose packet has to carry the recorded obligation."""

    return {
        **quota_status_payload(
            goal_id=GOAL_ID,
            status="active",
            agent_todo_items=[
                quota_todo_item(
                    todo_id="todo_current001",
                    index=1,
                    priority="P1",
                    title="Advance the reviewed slice.",
                    claimed_by=AGENT_ID,
                )
            ],
            recommended_action="Advance the reviewed slice.",
            coordination={"agent_model": "peer_v1", "registered_agents": [AGENT_ID]},
            claim_scope_agent_id=AGENT_ID,
        ),
        "registry": str(registry),
        "runtime_root": str(tmp_path / "runtime"),
    }


def _packet(tmp_path: Path, registry: Path, context):
    return build_quota_should_run(
        _lane_payload(tmp_path, registry),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        scheduler_execution_context=context,
    )


def test_recorded_adoption_is_projected_into_the_lane_packet(tmp_path):
    home, registry = _host_with_frozen_body(tmp_path)
    _record_deferred_adoption(tmp_path, home, DESIRED_BODY)
    hint = _packet(tmp_path, registry, APP_CONTEXT)["scheduler_hint"]
    adoption = hint["app_automation"]["prompt_adoption"]
    assert adoption["status"] == "adoption_required"
    assert adoption["automation_id"] == "watch"
    assert adoption["host_action"] == lifecycle.PENDING_HOST_ACTION
    assert adoption["host_action_contract"] == lifecycle.PENDING_HOST_ACTION_CONTRACT
    assert adoption["spend_policy"] == lifecycle.PENDING_SPEND_POLICY
    assert adoption["api_update_request"]["arguments"] == {
        "mode": "update", "id": "watch", "kind": "heartbeat", "name": "Fixture watch",
        "status": "PAUSED", "rrule": "FREQ=MINUTELY;INTERVAL=3", "targetThreadId": THREAD_ID,
        "notificationPolicy": None, "prompt": DESIRED_BODY}
    # The legacy Codex App projection carries the same recorded obligation.
    assert hint["codex_app"]["prompt_adoption"] == adoption


def test_applied_body_and_non_app_hosts_project_no_adoption(tmp_path):
    home, registry = _host_with_frozen_body(tmp_path)
    _record_deferred_adoption(tmp_path, home, DESIRED_BODY)
    assert "prompt_adoption" not in json.dumps(_packet(tmp_path, registry, CLI_CONTEXT)["scheduler_hint"])
    # A different installed body than the reviewed one stays pending.
    assert _packet(tmp_path, registry, APP_CONTEXT)["scheduler_hint"]["app_automation"]["prompt_adoption"]
    path = home / "automations/watch/automation.toml"
    path.write_text(upgrade._replace_prompt(path.read_text(), DESIRED_BODY), encoding="utf-8")
    assert "prompt_adoption" not in json.dumps(_packet(tmp_path, registry, APP_CONTEXT)["scheduler_hint"])


def test_lane_without_a_record_projects_no_adoption(tmp_path):
    home, registry = _host_with_frozen_body(tmp_path)
    hint = _packet(tmp_path, registry, APP_CONTEXT)["scheduler_hint"]
    assert "prompt_adoption" not in json.dumps(hint)
