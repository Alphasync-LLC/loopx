"""An explicit --todo-id must reach the Goal's own rows, not only displayed lanes."""

from __future__ import annotations

from pathlib import Path

from loopx.control_plane.agents.agent_lane_recommendation import (
    build_explicit_advancement_next_action,
)
from loopx.control_plane.quota.should_run_prepare import (
    _authoritative_requested_agent_rows,
)
from loopx.control_plane.todos.quota_summary import (
    select_planning_inventory_source_items,
)

GOAL_ID = "goal-beyond-lanes"
AGENT_ID = "agent-beyond-lanes"
WANTED_TODO_ID = "todo_beyond_lanes"
OTHER_AGENT_ID = "agent-somebody-else"


def _row(todo_id: str, *, claimed_by: str = AGENT_ID, status: str = "open") -> str:
    return (
        f"- [ ] [P1] row {todo_id}\n"
        "  <!-- loopx:todo "
        f"status={status} task_class=advancement_task claimed_by={claimed_by} "
        f"todo_id={todo_id} -->"
    )


def _fixture(tmp_path: Path, rows: list[str]) -> tuple[dict, Path]:
    project = tmp_path / "project"
    state = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state.parent.mkdir(parents=True)
    state.write_text(
        "# Active Goal State\n\n## Agent Todo\n\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    goal = {
        "id": GOAL_ID,
        "status": "active",
        "repo": str(project),
        "state_file": str(state.relative_to(project)),
        "coordination": {"agent_model": "peer_v1", "registered_agents": [AGENT_ID]},
    }
    return goal, state


def _candidate(rows: list[dict], todo_id: str):
    return build_explicit_advancement_next_action(
        agent_identity={"agent_id": AGENT_ID},
        agent_todo_items=rows,
        available_capabilities=["network", "filesystem_write"],
        todo_id=todo_id,
        selection_binding="pending_action_selection",
    )


def test_a_row_outside_the_presented_lanes_is_reachable_by_id(tmp_path: Path) -> None:
    rows = [_row(f"todo_presented_{index}") for index in range(1, 6)]
    rows.append(_row(WANTED_TODO_ID))
    goal, _state = _fixture(tmp_path, rows)
    # The presented lanes carry a bounded selection, so the row the caller
    # worked on is absent from them.
    presented_summary = {
        "items": [
            {"todo_id": "todo_presented_1", "text": "[P1] row", "status": "open", "task_class": "advancement_task", "claimed_by": AGENT_ID},
            {"todo_id": "todo_presented_2", "text": "[P1] row", "status": "open", "task_class": "advancement_task", "claimed_by": AGENT_ID},
        ]
    }
    presented = select_planning_inventory_source_items(presented_summary, None)
    assert WANTED_TODO_ID not in {item.get("todo_id") for item in presented}
    assert _candidate(presented, WANTED_TODO_ID) is None

    authoritative = _authoritative_requested_agent_rows(
        registry_goal=goal,
        todo_id=WANTED_TODO_ID,
    )

    assert [row["todo_id"] for row in authoritative] == [WANTED_TODO_ID]
    assert _candidate(authoritative, WANTED_TODO_ID) is not None


def test_unknown_id_or_unreadable_state_resolves_nothing(tmp_path: Path) -> None:
    goal, _state = _fixture(tmp_path, [_row(WANTED_TODO_ID)])

    assert _authoritative_requested_agent_rows(registry_goal=goal, todo_id="todo_unknown") == []
    assert _authoritative_requested_agent_rows(registry_goal=goal, todo_id=None) == []
    assert (
        _authoritative_requested_agent_rows(
            registry_goal={"id": GOAL_ID, "repo": str(tmp_path / "missing"), "state_file": "none.md"},
            todo_id=WANTED_TODO_ID,
        )
        == []
    )


def test_predicates_still_refuse_another_agents_or_blocked_rows(tmp_path: Path) -> None:
    goal, _state = _fixture(
        tmp_path,
        [
            _row("todo_other_agent", claimed_by=OTHER_AGENT_ID),
            _row("todo_blocked_row", status="blocked"),
        ],
    )

    other_agent_rows = _authoritative_requested_agent_rows(
        registry_goal=goal,
        todo_id="todo_other_agent",
    )
    blocked_rows = _authoritative_requested_agent_rows(
        registry_goal=goal,
        todo_id="todo_blocked_row",
    )

    assert _candidate(other_agent_rows, "todo_other_agent") is None
    assert _candidate(blocked_rows, "todo_blocked_row") is None
