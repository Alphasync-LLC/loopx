from __future__ import annotations

from pathlib import Path

import pytest

import loopx.rollout_event_log as rollout_event_log
from loopx.rollout_event_log import (
    append_rollout_event,
    append_rollout_event_once,
    build_rollout_event,
    load_rollout_events,
)


def test_limited_rollout_event_load_keeps_only_a_bounded_window(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class TrackedEvent(dict[str, int]):
        alive = 0
        peak = 0

        def __init__(self, index: int) -> None:
            super().__init__(index=index)
            type(self).alive += 1
            type(self).peak = max(type(self).peak, type(self).alive)

        def __del__(self) -> None:
            type(self).alive -= 1

    monkeypatch.setattr(
        rollout_event_log,
        "iter_rollout_events",
        lambda _path: (TrackedEvent(index) for index in range(100)),
    )

    events = rollout_event_log.load_rollout_events(tmp_path / "unused", limit=3)

    assert [event["index"] for event in events] == [97, 98, 99]
    assert TrackedEvent.peak <= 4


@pytest.mark.parametrize("idempotent", [False, True])
def test_append_starts_a_new_row_after_a_torn_final_record(
    tmp_path: Path,
    idempotent: bool,
) -> None:
    log_path = tmp_path / "rollout-event-log.jsonl"
    torn_record = '{"schema_version":"loopx_rollout_event_v0"'
    log_path.write_text(torn_record, encoding="utf-8")
    event = build_rollout_event(
        goal_id="goal-a",
        event_kind="quota_should_run",
        agent_id="agent-a",
        run_id="turn-a",
        status="run",
        recorded_at="2026-09-23T00:00:00Z",
    )

    if idempotent:
        written, appended = append_rollout_event_once(
            log_path,
            event,
            identity_fields=("goal_id", "event_kind", "agent_id", "run_id"),
        )
        assert appended is True
    else:
        written = append_rollout_event(log_path, event)

    assert log_path.read_text(encoding="utf-8").startswith(torn_record + "\n")
    assert load_rollout_events(log_path) == [written]
