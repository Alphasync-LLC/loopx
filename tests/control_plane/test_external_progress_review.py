from __future__ import annotations

import hashlib

from loopx.control_plane.work_items.external_progress_review import (
    EXTERNAL_PROGRESS_REVIEW_TRIGGER_KIND,
    external_progress_review_trigger,
)
from loopx.control_plane.work_items.autonomous_replan_ack import (
    autonomous_replan_ack_recorded,
)

AGENT = "worker"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(sequence: int, *, agent: str = AGENT, turn: str | None = None, ack: bool = False) -> dict[str, object]:
    row: dict[str, object] = {
        "classification": "bounded_delivery",
        "generated_at": f"2026-09-21T00:00:{sequence:02d}Z",
        "agent_id": agent,
        "progress_observation": {
            "schema_version": "typed_progress_observation_v0",
            "result_class": "advanced",
            "hypothesis_id": f"hypothesis-{sequence}",
        },
    }
    if turn is not None:
        row["turn_instance_id"] = turn
    if ack:
        row["autonomous_replan_ack"] = {
            "recorded": True,
            "semantic_delta": {"accepted": True},
        }
    return row


def receipt(
    sequence: int,
    *,
    turn: str | None = None,
    agent: str = AGENT,
    status: str = "completed",
    noul: bool | None = True,
    choice: bool | None = True,
    evidence: str | None = None,
    contract: str = "contract-1",
    reason: str | None = None,
    todo: str | None = None,
) -> dict[str, object]:
    return {
        "receipt_id": _digest(f"event-{sequence}"),
        "event_id": _digest(f"event-{sequence}"),
        "evidence_id": _digest(evidence or f"evidence-{sequence}"),
        "contract_revision": _digest(contract),
        "sequence": sequence,
        "status": status,
        "reason": reason,
        "run": {
            "turn_instance_id": turn,
            "generated_at": f"2026-09-21T00:00:{sequence:02d}Z",
            "agent_id": agent,
            "todo_id": todo,
        },
        "judgments": {"choice": None, "noul": None},
        "drift_signal": {"noul": noul, "choice": choice},
    }


def trigger(runs, receipts, **overrides):
    options = {
        "receipts": receipts,
        "agent_id": AGENT,
        "threshold": 2,
        "signal": "noul",
        "contract_revision": _digest("contract-1"),
        "ack_recorded": autonomous_replan_ack_recorded,
    }
    options.update(overrides)
    return external_progress_review_trigger(runs, **options)


def test_two_consecutive_completed_drift_receipts_trigger() -> None:
    runs = [run(2, turn="t2"), run(1, turn="t1")]
    result = trigger(runs, [receipt(2, turn="t2"), receipt(1, turn="t1")])
    assert result is not None
    assert result["kind"] == EXTERNAL_PROGRESS_REVIEW_TRIGGER_KIND
    assert result["run_count"] == 2
    assert result["latest_generated_at"] == "2026-09-21T00:00:02Z"
    assert result["oldest_counted_generated_at"] == "2026-09-21T00:00:01Z"
    assert result["frontier_identity"] == "progress_review:" + _digest("evidence-2")
    assert result["agent_id"] == AGENT
    assert "delta" not in result and "text" not in result


def test_self_declared_advanced_alone_is_not_enough_without_receipts() -> None:
    assert trigger([run(2, turn="t2"), run(1, turn="t1")], []) is None


def test_unknown_abstained_or_failed_receipt_breaks_the_streak() -> None:
    runs = [run(3, turn="t3"), run(2, turn="t2"), run(1, turn="t1")]
    for middle in (
        receipt(2, turn="t2", noul=None, choice=None, status="abstained"),
        receipt(2, turn="t2", noul=None, choice=None, status="failed"),
        receipt(2, turn="t2", noul=False),
    ):
        receipts = [receipt(3, turn="t3"), middle, receipt(1, turn="t1")]
        assert trigger(runs, receipts) is None


def test_missing_receipt_for_a_transition_breaks_the_streak() -> None:
    runs = [run(3, turn="t3"), run(2, turn="t2"), run(1, turn="t1")]
    assert trigger(runs, [receipt(3, turn="t3"), receipt(1, turn="t1")]) is None


def test_acknowledged_replan_rearms_the_trigger() -> None:
    runs = [run(3, turn="t3"), run(2, turn="t2", ack=True), run(1, turn="t1")]
    receipts = [receipt(3, turn="t3"), receipt(2, turn="t2"), receipt(1, turn="t1")]
    assert trigger(runs, receipts) is None
    runs = [run(4, turn="t4"), run(3, turn="t3"), run(2, turn="t2", ack=True)]
    receipts = [receipt(4, turn="t4"), receipt(3, turn="t3"), receipt(2, turn="t2")]
    assert trigger(runs, receipts) is not None


def test_same_turn_retry_and_same_evidence_count_once() -> None:
    runs = [run(3, turn="t2"), run(2, turn="t2"), run(1, turn="t1")]
    receipts = [receipt(2, turn="t2"), receipt(1, turn="t1")]
    result = trigger(runs, receipts)
    assert result is not None and result["run_count"] == 2
    same_evidence = [receipt(2, turn="t2", evidence="shared"), receipt(1, turn="t1", evidence="shared")]
    assert trigger([run(2, turn="t2"), run(1, turn="t1")], same_evidence) is None


def test_contract_revision_change_invalidates_earlier_receipts() -> None:
    runs = [run(2, turn="t2"), run(1, turn="t1")]
    receipts = [receipt(2, turn="t2", contract="contract-2"), receipt(1, turn="t1")]
    assert trigger(runs, receipts) is None
    # Receipts that agree with each other but not with the pinned goal contract
    # are history, never current evidence.
    old = [receipt(2, turn="t2", contract="contract-0"), receipt(1, turn="t1", contract="contract-0")]
    assert trigger(runs, old) is None
    assert trigger(runs, old, contract_revision=_digest("contract-0")) is not None


def test_assist_without_a_pinned_contract_never_triggers() -> None:
    runs = [run(2, turn="t2"), run(1, turn="t1")]
    receipts = [receipt(2, turn="t2"), receipt(1, turn="t1")]
    assert trigger(runs, receipts, contract_revision=None) is None
    assert trigger(runs, receipts, contract_revision="") is None


def test_turn_match_still_requires_matching_agent_and_todo() -> None:
    runs = [run(2, turn="t2"), run(1, turn="t1")]
    assert trigger(runs, [receipt(2, turn="t2", agent="someone-else"), receipt(1, turn="t1")]) is None
    runs_with_todo = [dict(run(2, turn="t2"), todo_id="todo-a"), run(1, turn="t1")]
    assert trigger(runs_with_todo, [receipt(2, turn="t2", todo="todo-b"), receipt(1, turn="t1")]) is None
    assert trigger(runs_with_todo, [receipt(2, turn="t2", todo="todo-a"), receipt(1, turn="t1")]) is not None
    # A receipt that names no todo does not conflict with a run that does.
    assert trigger(runs_with_todo, [receipt(2, turn="t2"), receipt(1, turn="t1")]) is not None


def test_ambiguous_fallback_identity_is_never_attributed() -> None:
    runs = [run(2), run(1)]
    two_for_one = [receipt(3, evidence="other"), receipt(2), receipt(1)]
    # receipt 3 and 2 have no turn id and share (generated_at, agent) of run 2.
    two_for_one[0]["run"]["generated_at"] = two_for_one[1]["run"]["generated_at"]
    assert trigger(runs, two_for_one) is None


def pending(n: int, turn: str) -> dict[str, object]:
    return receipt(n, turn=turn, status="not_evaluated", noul=None, choice=None, reason="pending_evaluation")


def test_pending_newest_evaluations_are_skipped_but_bounded() -> None:
    runs = [run(3, turn="t3"), run(2, turn="t2"), run(1, turn="t1")]
    result = trigger(runs, [pending(3, "t3"), receipt(2, turn="t2"), receipt(1, turn="t1")])
    assert result is not None and result["run_count"] == 2 and result["pending_skipped"] == 1
    runs = [run(5, turn="t5"), run(4, turn="t4"), run(3, turn="t3"), run(2, turn="t2"), run(1, turn="t1")]
    receipts = [pending(5, "t5"), pending(4, "t4"), pending(3, "t3"), receipt(2, turn="t2"), receipt(1, turn="t1")]
    assert trigger(runs, receipts) is None
    # A pending receipt in the middle of a streak is still a gap.
    runs = [run(3, turn="t3"), run(2, turn="t2"), run(1, turn="t1")]
    assert trigger(runs, [receipt(3, turn="t3"), pending(2, "t2"), receipt(1, turn="t1")]) is None
    # Other non-completed newest receipts break rather than skip.
    assert trigger(runs, [receipt(3, turn="t3", status="failed", noul=None, choice=None, reason="deadline_exceeded"), receipt(2, turn="t2"), receipt(1, turn="t1")]) is None


def test_signal_selection_and_agent_scoping() -> None:
    runs = [run(2, turn="t2"), run(1, turn="t1")]
    receipts = [receipt(2, turn="t2", noul=False, choice=True), receipt(1, turn="t1", noul=False, choice=True)]
    assert trigger(runs, receipts) is None
    assert trigger(runs, receipts, signal="choice") is not None
    assert trigger(runs, receipts, signal="prose") is None
    other = [run(2, agent="other", turn="t2"), run(1, turn="t1")]
    assert trigger(other, [receipt(2, turn="t2", agent="other"), receipt(1, turn="t1")]) is None


def test_fallback_identity_uses_generated_at_and_agent() -> None:
    runs = [run(2), run(1)]
    receipts = [receipt(2), receipt(1)]
    result = trigger(runs, receipts)
    assert result is not None and result["run_count"] == 2
    assert trigger([run(2), run(1)], [receipt(2), receipt(1, agent="someone-else")]) is None


def test_threshold_floor_is_two_and_higher_thresholds_wait() -> None:
    runs = [run(2, turn="t2"), run(1, turn="t1")]
    receipts = [receipt(2, turn="t2"), receipt(1, turn="t1")]
    assert trigger(runs, receipts, threshold=1) is not None
    assert trigger(runs, receipts, threshold=3) is None


# --- obligation and status wiring -------------------------------------------

from loopx.control_plane.work_items.project_asset import (  # noqa: E402
    attach_active_state_project_asset_fields,
)
from loopx.status import (  # noqa: E402
    autonomous_replan_obligation_from_runs,
    external_progress_review_context,
)


def _context(mode: str, receipts: list[dict[str, object]], *, signal: str = "noul", threshold: int = 2, pin: str | None = _digest("contract-1")) -> dict[str, object]:
    return {
        "policy": {"mode": mode, "signal": signal, "drift_threshold": threshold, "contract_revision": pin},
        "receipts": receipts,
        "summary": {"schema_version": "progress_review_status_v0", "mode": mode, "receipt_count": len(receipts)},
    }


def test_assist_policy_turns_receipts_into_the_existing_obligation() -> None:
    runs = [run(2, turn="t2"), run(1, turn="t1")]
    receipts = [receipt(2, turn="t2"), receipt(1, turn="t1")]
    obligation = autonomous_replan_obligation_from_runs(
        runs, agent_todos=None, external_progress_review=_context("assist", receipts)
    )
    assert obligation is not None
    assert obligation["required"] is True
    assert obligation["triggers"][0]["kind"] == EXTERNAL_PROGRESS_REVIEW_TRIGGER_KIND
    assert obligation["frontier_identity"].startswith("progress_review:")
    assert obligation["external_progress_review"]["run_count"] == 2
    assert obligation["external_progress_review"]["authority"] == "advisory_evidence_only"
    assert any("acceptance criterion" in action["text"] for action in obligation["todo_actions"])
    assert "off-goal" in obligation["recommended_action"]
    assert obligation["stop_condition"]


def test_shadow_and_off_policies_never_raise_an_obligation() -> None:
    runs = [run(2, turn="t2"), run(1, turn="t1")]
    receipts = [receipt(2, turn="t2"), receipt(1, turn="t1")]
    assert (
        autonomous_replan_obligation_from_runs(
            runs, agent_todos=None, external_progress_review=_context("assist", receipts, pin=None)
        )
        is None
    )
    for mode in ("shadow", "off"):
        assert (
            autonomous_replan_obligation_from_runs(
                runs, agent_todos=None, external_progress_review=_context(mode, receipts)
            )
            is None
        )
    assert autonomous_replan_obligation_from_runs(runs, agent_todos=None) is None


def test_typed_fuse_keeps_precedence_over_external_review() -> None:
    fused = []
    for sequence in (2, 1):
        row = run(sequence, turn=f"t{sequence}")
        row["progress_observation"] = {
            "schema_version": "typed_progress_observation_v0",
            "result_class": "unchanged",
            "hypothesis_id": "same",
        }
        fused.append(row)
    receipts = [receipt(2, turn="t2"), receipt(1, turn="t1")]
    obligation = autonomous_replan_obligation_from_runs(
        fused, agent_todos=None, external_progress_review=_context("assist", receipts)
    )
    assert obligation is not None
    assert obligation["triggers"][0]["kind"] == "typed_progress_repeat"


def test_attach_surfaces_summary_and_binds_review_into_obligation() -> None:
    runs = [run(2, turn="t2"), run(1, turn="t1")]
    receipts = [receipt(2, turn="t2"), receipt(1, turn="t1")]
    item: dict[str, object] = {"project_asset": {}}
    attached = attach_active_state_project_asset_fields(
        item,
        latest_runs=runs,
        autonomous_replan_obligation_from_runs=autonomous_replan_obligation_from_runs,
        external_progress_review=_context("assist", receipts),
    )
    assert item["external_progress_review"]["receipt_count"] == 2
    assert attached["external_progress_review"]["mode"] == "assist"
    assert item["autonomous_replan_obligation"]["triggers"][0]["kind"] == EXTERNAL_PROGRESS_REVIEW_TRIGGER_KIND
    plain: dict[str, object] = {"project_asset": {}}
    attach_active_state_project_asset_fields(
        plain,
        latest_runs=runs,
        autonomous_replan_obligation_from_runs=autonomous_replan_obligation_from_runs,
    )
    assert "external_progress_review" not in plain
    assert "autonomous_replan_obligation" not in plain


def test_context_loader_is_silent_for_off_and_reads_receipts_when_on(tmp_path) -> None:
    from loopx.capabilities.progress_review.receipt import write_progress_review_receipt

    goal = {"id": "ctx-goal", "control_plane": {"progress_review": {"mode": "shadow"}}}
    assert external_progress_review_context({"id": "ctx-goal"}, tmp_path) is None
    assert external_progress_review_context(goal, None) is None
    loaded = external_progress_review_context(goal, tmp_path)
    assert loaded is not None and loaded["receipts"] == [] and loaded["summary"]["receipt_count"] == 0
    stored = {
        **receipt(1, turn="t1"),
        "schema_version": "progress_review_receipt_v0",
        "signal_rule_version": "progress_review_signal_rule_v1",
        "goal_id": "ctx-goal",
        "question_version": "scoped-progress-sentinel-v2",
        "model": "fixture-v1",
        "judgments": {
            "choice": {"relation": "off_goal", "increment": "no_new_evidence"},
            "noul": {"behavior_change": 0.05, "serves_acceptance": 0.04, "evidence_increment": 0.1},
        },
        "label_probability_threshold": 0.6,
        "recorded_at": 1.0,
    }
    write_progress_review_receipt(tmp_path, "ctx-goal", stored)
    loaded = external_progress_review_context(goal, tmp_path)
    assert loaded is not None and loaded["summary"]["receipt_count"] == 1
    assert loaded["summary"]["latest"]["drift_signal"] == {"noul": True, "choice": True}
    # A pinned revision partitions receipts into current and stale.
    pinned = {"id": "ctx-goal", "control_plane": {"progress_review": {"mode": "assist", "contract_revision": _digest("contract-2")}}}
    loaded = external_progress_review_context(pinned, tmp_path)
    assert loaded is not None and loaded["receipts"] == [] and loaded["summary"]["stale_receipts"] == 1
    unpinned = {"id": "ctx-goal", "control_plane": {"progress_review": {"mode": "assist"}}}
    loaded = external_progress_review_context(unpinned, tmp_path)
    assert loaded is not None and loaded["summary"]["assist_blocked_reason"] == "contract_revision_unpinned"
