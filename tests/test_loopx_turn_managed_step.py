"""Typed tests for the managed-step consumer of same-Turn continuation.

Each test drives ``decide_managed_step`` off a journal shaped exactly as
``loopx turn run-once`` leaves one after a retryable host failure, paired with a
fresh ``loopx_turn_envelope_v0`` decision. The reader must stay pure: it grants
no execution authority, never spends or writes, and treats the Turn journal as
the sole authority for the attempt budget.
"""

from __future__ import annotations

from typing import Any

import pytest

from loopx.control_plane.turn_driver import (
    LOOPX_TURN_RESULT_SCHEMA_VERSION,
    LoopXTurnResultKind,
    build_loopx_turn_transaction_plan,
    validate_loopx_turn_receipt,
)
from loopx.control_plane.turn_driver.host_failure import build_host_failure_record
from loopx.control_plane.turn_driver.managed_step import (
    LOOPX_TURN_MANAGED_STEP_SCHEMA_VERSION,
    decide_managed_step,
    managed_step_receipt_from_journal,
    reconcile_observed_attempt,
)

GOAL_ID = "goal-managed-step"
AGENT_ID = "agent-managed-step"
TODO_ID = "todo-managed-step"


def _lineage() -> dict[str, str]:
    return {"goal_id": GOAL_ID, "agent_id": AGENT_ID, "todo_id": TODO_ID}


def _plan() -> dict[str, Any]:
    """A stored Turn plan shaped as ``build_loopx_turn_plan`` returns it."""

    transaction = build_loopx_turn_transaction_plan(
        planned=True,
        lineage=_lineage(),
        host="dsh",
        execution_mode="interactive-visible",
        session_action="resume",
    )
    return {"transaction": transaction}


def _failed_journal(
    *,
    kind: str = "provider_capacity",
    attempt: int = 1,
    result_kind: LoopXTurnResultKind = LoopXTurnResultKind.HOST_FAILURE,
    status: str = "failed",
    lineage: dict[str, str] | None = None,
) -> dict[str, Any]:
    transaction = build_loopx_turn_transaction_plan(
        planned=True,
        lineage=_lineage() if lineage is None else lineage,
        host="dsh",
        execution_mode="interactive-visible",
        session_action="resume",
    )
    plan = {"transaction": transaction}
    failure_kind = result_kind in {
        LoopXTurnResultKind.HOST_FAILURE,
        LoopXTurnResultKind.VALIDATION_FAILED,
        LoopXTurnResultKind.WRITEBACK_FAILED,
        LoopXTurnResultKind.QUOTA_SPEND_FAILED,
    }
    if failure_kind:
        completed: list[str] = []
        result: dict[str, Any] = {
            "schema_version": LOOPX_TURN_RESULT_SCHEMA_VERSION,
            "turn_key": transaction["turn_key"],
            "result_kind": result_kind.value,
            "completed_phases": completed,
            "failed_phase": "host_execute",
        }
    else:
        completed = ["host_execute", "typed_result", "validation"]
        result = {
            "schema_version": LOOPX_TURN_RESULT_SCHEMA_VERSION,
            "turn_key": transaction["turn_key"],
            "result_kind": result_kind.value,
            "completed_phases": completed,
        }
    receipt = validate_loopx_turn_receipt(transaction, result)
    assert receipt["ok"] is True, receipt
    journal: dict[str, Any] = {
        "schema_version": "loopx_turn_journal_v0",
        "status": status,
        "turn_key": transaction["turn_key"],
        "result_kind": result_kind.value,
        "plan": plan,
        "receipt": receipt,
        "completed_phases": completed,
        "host_attempt_count": attempt,
    }
    if result_kind is LoopXTurnResultKind.HOST_FAILURE:
        journal["host_failure"] = build_host_failure_record(kind, attempt=attempt)
    return journal


def _envelope(
    *,
    should_run: bool = True,
    effective_action: str = "deliver",
    selected_todo_id: str | None = TODO_ID,
    user_action_required: bool = False,
    lineage: dict[str, str] | None = None,
    predecessor_turn_key: str | None = None,
) -> dict[str, Any]:
    lin = _lineage() if lineage is None else lineage
    envelope: dict[str, Any] = {
        "schema_version": "loopx_turn_envelope_v0",
        "goal_id": lin["goal_id"],
        "agent_id": lin["agent_id"],
        "should_run": should_run,
        "effective_action": effective_action,
        "action_signature": {"matches": True, "source_hash": "sha256:test", "envelope_hash": "sha256:test"},
        "compaction": {"within_budget": True},
        "action": {
            "delivery_allowed": True,
            "must_attempt": True,
            "quiet_noop_allowed": False,
            "selected_todo": (
                {"todo_id": selected_todo_id} if selected_todo_id else None
            ),
        },
        "user": {"action_required": user_action_required},
    }
    if predecessor_turn_key is not None:
        envelope["predecessor_turn_key"] = predecessor_turn_key
    return envelope


def _decide(
    journal: dict[str, Any],
    *,
    envelope: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Decide one managed step, binding the fresh decision to the receipt."""

    return decide_managed_step(
        journal,
        (
            _envelope(predecessor_turn_key=str(journal["turn_key"]))
            if envelope is None
            else envelope
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        turn_key=str(journal["turn_key"]),
        **kwargs,
    )


def test_retryable_failure_with_budget_returns_wait_with_typed_continuation() -> None:
    journal = _failed_journal(kind="provider_capacity", attempt=1)

    payload = _decide(journal)

    assert payload["schema_version"] == LOOPX_TURN_MANAGED_STEP_SCHEMA_VERSION
    assert payload["disposition"] == "wait"
    assert payload["turn_key"] == journal["turn_key"]
    assert payload["attempt"] == 1
    continuation = payload["retry_continuation"]
    assert continuation == {
        "same_turn": True,
        "retry_failed_turn": True,
        "strategy": "same_configuration",
        "retry_after_seconds": 30,
        "attempt": 1,
        "max_attempts": 3,
        "fresh_envelope_required": True,
        "model_fallback_allowed": False,
    }
    assert payload["max_attempts"] == 3


def test_exhausted_budget_requests_repair_instead_of_waiting() -> None:
    journal = _failed_journal(kind="provider_capacity", attempt=3)

    payload = _decide(journal)

    assert payload["disposition"] == "repair"
    assert "retry_continuation" not in payload
    assert payload["attempt"] == 3


def test_non_retryable_failure_is_refused_before_the_controller() -> None:
    journal = _failed_journal(kind="auth_failed", attempt=1)

    with pytest.raises(ValueError, match="not retryable"):
        _decide(journal)


def test_committed_journal_is_not_a_managed_step_input() -> None:
    journal = _failed_journal(
        result_kind=LoopXTurnResultKind.VALIDATED_PROGRESS,
        status="committed",
    )

    with pytest.raises(ValueError, match="failed Turn journal"):
        _decide(journal)


def test_forged_observed_attempt_is_refused() -> None:
    journal = _failed_journal(kind="provider_capacity", attempt=1)

    with pytest.raises(ValueError, match="observed_attempt disagrees"):
        _decide(journal, observed_attempt=99)


def test_forged_observed_max_attempts_is_refused() -> None:
    journal = _failed_journal(kind="provider_capacity", attempt=1)

    with pytest.raises(ValueError, match="observed_max_attempts disagrees"):
        _decide(journal, observed_max_attempts=99)


def test_matching_observation_is_accepted() -> None:
    journal = _failed_journal(kind="rate_limited", attempt=2)

    payload = _decide(journal, observed_attempt=2, observed_max_attempts=3)

    assert payload["disposition"] == "wait"
    # Backoff doubles per attempt off the policy base (60s for rate_limited).
    assert payload["retry_continuation"]["retry_after_seconds"] == 120


def test_observation_must_be_a_positive_integer() -> None:
    journal = _failed_journal(kind="provider_capacity", attempt=1)

    with pytest.raises(ValueError, match="positive integer"):
        _decide(journal, observed_attempt=0)
    with pytest.raises(ValueError, match="positive integer"):
        _decide(journal, observed_attempt=True)


def test_foreign_lineage_is_refused() -> None:
    journal = _failed_journal(
        lineage={"goal_id": "other-goal", "agent_id": AGENT_ID, "todo_id": TODO_ID}
    )

    with pytest.raises(ValueError, match="lineage does not match"):
        _decide(journal)


def test_blocked_recovery_audit_is_refused() -> None:
    journal = _failed_journal(kind="provider_capacity", attempt=1)
    journal["recovery_audit"] = {
        "schema_version": "loopx_turn_recovery_audit_v0",
        "planned": {
            "schema_version": "loopx_turn_recovery_decision_v0",
            "action": "blocked",
            "can_continue": False,
            "resume_from": None,
            "reinvoke_host": False,
            "reason": "journal consistency violation",
            "retry_failed": True,
            "checks": [],
        },
        "actual": {
            "status": "finished",
            "journal_status": "failed",
            "completed_phases": [],
            "host_invoked": True,
        },
    }

    with pytest.raises(ValueError, match="replay is blocked"):
        _decide(journal)


def test_fresh_decision_must_agree_on_goal_and_agent_lineage() -> None:
    journal = _failed_journal(kind="provider_capacity", attempt=1)
    foreign = _envelope(
        lineage={"goal_id": "other-goal", "agent_id": AGENT_ID, "todo_id": TODO_ID}
    )

    with pytest.raises(ValueError, match="fresh decision goal_id"):
        _decide(journal, envelope=foreign)


def test_managed_step_never_spends_or_writes() -> None:
    """The reader is pure: no effects, no host invocation, no quota spend."""

    journal = _failed_journal(kind="provider_capacity", attempt=1)

    payload = _decide(journal)

    for forbidden in ("effects", "quota_slot_spend_count", "host_invoked", "writeback"):
        assert forbidden not in payload
    # A wait decision must not carry any field that could be mistaken for
    # authority to execute now.
    assert "accepted_turn_keys" not in payload
    assert payload["disposition"] == "wait"


def test_reconcile_accepts_omitted_observations() -> None:
    journal = _failed_journal(kind="provider_capacity", attempt=1)

    assert reconcile_observed_attempt(
        journal, observed_attempt=None, observed_max_attempts=None
    ) is None


def test_receipt_from_journal_projects_lineage_and_kind() -> None:
    journal = _failed_journal(kind="provider_capacity", attempt=1)

    receipt = managed_step_receipt_from_journal(
        journal,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        turn_key=str(journal["turn_key"]),
    )

    assert receipt.result_kind is LoopXTurnResultKind.HOST_FAILURE
    assert receipt.lineage["todo_id"] == TODO_ID
    assert receipt.host_failure is not None
    assert receipt.host_failure["kind"] == "provider_capacity"


def test_journal_without_stored_plan_is_refused() -> None:
    journal = _failed_journal(kind="provider_capacity", attempt=1)
    journal.pop("plan")

    with pytest.raises(TypeError, match="no stored plan"):
        _decide(journal)


def test_journal_turn_key_mismatch_is_refused() -> None:
    journal = _failed_journal(kind="provider_capacity", attempt=1)
    journal["turn_key"] = "sha256:" + "0" * 64

    with pytest.raises(ValueError, match="turn_key"):
        _decide(journal)
