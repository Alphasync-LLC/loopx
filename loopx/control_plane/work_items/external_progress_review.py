"""Turn typed external progress-review receipts into a replan trigger.

Receipts are written outside every core transaction by an optional observer
that evaluates scoped file deltas. This module reads only the normalized
receipt contract: no prose, no provider call, no authority. Its single output
is evidence for the existing autonomous replan obligation, and only when the
goal policy is `assist` and pins the goal contract revision the receipts must
be bound to.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .progress_observation import _progress_turn_instance_id

EXTERNAL_PROGRESS_REVIEW_TRIGGER_KIND = "external_progress_review_drift"
EXTERNAL_PROGRESS_REVIEW_TRIGGER_SCHEMA_VERSION = "external_progress_review_trigger_v0"
EXTERNAL_PROGRESS_REVIEW_SIGNALS: tuple[str, ...] = ("noul", "choice")
EXTERNAL_PROGRESS_REVIEW_FRONTIER_PREFIX = "progress_review:"
EXTERNAL_PROGRESS_REVIEW_PENDING_REASON = "pending_evaluation"
# Newest transitions whose evaluation has not finished yet are neither counted
# nor allowed to dissolve an existing streak; beyond this many the streak breaks.
EXTERNAL_PROGRESS_REVIEW_MAX_PENDING_SKIP = 2

RunKey = tuple[str, str]
AckRecorded = Callable[[dict[str, Any]], bool]


def _run_key(run: Mapping[str, Any]) -> RunKey:
    return (
        str(run.get("generated_at") or "").strip(),
        str(run.get("agent_id") or "").strip(),
    )


def index_progress_review_receipts(
    receipts: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[RunKey, Mapping[str, Any] | None]]:
    """Index receipts by turn identity and by (generated_at, agent_id) fallback.

    Two receipts sharing one fallback key make that key ambiguous; it maps to
    None so the caller treats the transition as unattributable.
    """

    by_turn: dict[str, Mapping[str, Any]] = {}
    by_key: dict[RunKey, Mapping[str, Any] | None] = {}
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            continue
        run = receipt.get("run")
        if not isinstance(run, Mapping):
            continue
        sequence = receipt.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            continue
        turn = str(run.get("turn_instance_id") or "").strip()
        if turn:
            previous = by_turn.get(turn)
            if previous is None or int(previous.get("sequence") or 0) < sequence:
                by_turn[turn] = receipt
            continue
        key = _run_key(run)
        if not key[0]:
            continue
        if key in by_key:
            existing = by_key[key]
            if existing is None or str(existing.get("evidence_id")) != str(
                receipt.get("evidence_id")
            ):
                by_key[key] = None
            elif int(existing.get("sequence") or 0) < sequence:
                by_key[key] = receipt
        else:
            by_key[key] = receipt
    return by_turn, by_key


def _identity_conflict(run: Mapping[str, Any], receipt: Mapping[str, Any]) -> bool:
    """A receipt found by turn must also name the same Agent and Todo when both do."""

    receipt_run = receipt.get("run")
    if not isinstance(receipt_run, Mapping):
        return True
    for field in ("agent_id", "todo_id"):
        mine = str(run.get(field) or "").strip()
        theirs = str(receipt_run.get(field) or "").strip()
        if mine and theirs and mine != theirs:
            return True
    return False


def _single_agent_id(runs: list[dict[str, Any]]) -> str | None:
    agent_ids = {
        str(run.get("agent_id") or "").strip() for run in runs if run.get("agent_id")
    }
    agent_ids.discard("")
    return next(iter(agent_ids)) if len(agent_ids) == 1 else None


def external_progress_review_trigger(
    newest_first_runs: Iterable[dict[str, Any]],
    *,
    receipts: Iterable[Mapping[str, Any]],
    agent_id: str | None,
    threshold: int,
    signal: str,
    contract_revision: str | None,
    ack_recorded: AckRecorded,
) -> dict[str, Any] | None:
    """Return a trigger for consecutive completed drift receipts, else None.

    Streak rules, applied newest-first:
    - without a pinned goal contract revision nothing triggers;
    - an acknowledged autonomous replan ends the scan (re-arm);
    - up to EXTERNAL_PROGRESS_REVIEW_MAX_PENDING_SKIP newest transitions whose
      receipt is still `pending_evaluation` are skipped, not counted;
    - a transition without a receipt, an ambiguous or identity-conflicting
      receipt, a receipt that is not `completed`, whose drift signal is not
      True, or bound to another contract revision, ends the scan;
    - retries of the same logical turn are one transition;
    - the same evidence id counts once.
    """

    if signal not in EXTERNAL_PROGRESS_REVIEW_SIGNALS:
        return None
    pinned = str(contract_revision or "").strip()
    if not pinned:
        return None
    required = max(2, int(threshold))
    normalized_agent_id = str(agent_id or "").strip()
    by_turn, by_key = index_progress_review_receipts(receipts)
    counted: list[tuple[dict[str, Any], Mapping[str, Any]]] = []
    seen_turns: set[str] = set()
    seen_evidence: set[str] = set()
    pending_skipped = 0
    for run in newest_first_runs:
        if not isinstance(run, dict):
            continue
        if ack_recorded(run):
            break
        run_agent_id = str(run.get("agent_id") or "").strip()
        if normalized_agent_id and run_agent_id not in {"", normalized_agent_id}:
            continue
        turn = _progress_turn_instance_id(run)
        if turn and turn in seen_turns:
            continue
        receipt = by_turn.get(turn) if turn else by_key.get(_run_key(run))
        if receipt is None:
            break
        if turn:
            seen_turns.add(turn)
        if _identity_conflict(run, receipt):
            break
        if (
            receipt.get("status") == "not_evaluated"
            and receipt.get("reason") == EXTERNAL_PROGRESS_REVIEW_PENDING_REASON
            and not counted
            and pending_skipped < EXTERNAL_PROGRESS_REVIEW_MAX_PENDING_SKIP
        ):
            pending_skipped += 1
            continue
        if receipt.get("status") != "completed":
            break
        drift_signal = receipt.get("drift_signal")
        if not isinstance(drift_signal, Mapping) or drift_signal.get(signal) is not True:
            break
        if str(receipt.get("contract_revision") or "") != pinned:
            break
        evidence_id = str(receipt.get("evidence_id") or "")
        if evidence_id in seen_evidence:
            continue
        seen_evidence.add(evidence_id)
        counted.append((run, receipt))
        if len(counted) >= required:
            break
    if len(counted) < required:
        return None
    latest_run, latest_receipt = counted[0]
    oldest_run = counted[-1][0]
    return {
        "kind": EXTERNAL_PROGRESS_REVIEW_TRIGGER_KIND,
        "schema_version": EXTERNAL_PROGRESS_REVIEW_TRIGGER_SCHEMA_VERSION,
        "section": "run_history",
        "signal": signal,
        "run_count": len(counted),
        "threshold": required,
        "pending_skipped": pending_skipped,
        "agent_id": normalized_agent_id
        or _single_agent_id([run for run, _ in counted]),
        "contract_revision": pinned,
        "evidence_ids": [str(receipt["evidence_id"]) for _, receipt in counted],
        "receipt_ids": [str(receipt["receipt_id"]) for _, receipt in counted],
        "latest_generated_at": str(latest_run.get("generated_at") or ""),
        "oldest_counted_generated_at": str(oldest_run.get("generated_at") or ""),
        "latest_judgments": latest_receipt.get("judgments"),
        "frontier_identity": EXTERNAL_PROGRESS_REVIEW_FRONTIER_PREFIX
        + str(latest_receipt["evidence_id"]),
        "authority": "advisory_evidence_only",
    }


def external_progress_review_obligation(
    newest_first_runs: list[dict[str, Any]],
    *,
    external_progress_review: Mapping[str, Any] | None,
    agent_id: str | None,
    ack_recorded: AckRecorded,
    build_obligation: Callable[..., dict[str, Any] | None],
    agent_todos: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Raise the existing obligation from receipts only under an `assist` policy."""

    if not isinstance(external_progress_review, Mapping):
        return None
    policy = external_progress_review.get("policy")
    if not isinstance(policy, Mapping) or policy.get("mode") != "assist":
        return None
    raw_receipts = external_progress_review.get("receipts")
    trigger = external_progress_review_trigger(
        newest_first_runs,
        receipts=raw_receipts if isinstance(raw_receipts, list) else [],
        agent_id=agent_id,
        threshold=int(policy.get("drift_threshold") or 2),
        signal=str(policy.get("signal") or "noul"),
        contract_revision=(
            str(policy["contract_revision"]) if policy.get("contract_revision") else None
        ),
        ack_recorded=ack_recorded,
    )
    if not trigger:
        return None
    return build_obligation([trigger], agent_todos=agent_todos)


__all__ = [
    "EXTERNAL_PROGRESS_REVIEW_FRONTIER_PREFIX",
    "EXTERNAL_PROGRESS_REVIEW_MAX_PENDING_SKIP",
    "EXTERNAL_PROGRESS_REVIEW_PENDING_REASON",
    "EXTERNAL_PROGRESS_REVIEW_SIGNALS",
    "EXTERNAL_PROGRESS_REVIEW_TRIGGER_KIND",
    "EXTERNAL_PROGRESS_REVIEW_TRIGGER_SCHEMA_VERSION",
    "external_progress_review_obligation",
    "external_progress_review_trigger",
    "index_progress_review_receipts",
]
