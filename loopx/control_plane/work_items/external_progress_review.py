"""Turn typed external progress-review receipts into a replan trigger.

Receipts are written outside every core transaction by an optional observer
that evaluates scoped file deltas. This module reads only the normalized
receipt contract: no prose, no provider call, no authority. Its single output
is evidence for the existing autonomous replan obligation, and only when the
goal policy is `assist`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .progress_observation import _progress_turn_instance_id

EXTERNAL_PROGRESS_REVIEW_TRIGGER_KIND = "external_progress_review_drift"
EXTERNAL_PROGRESS_REVIEW_TRIGGER_SCHEMA_VERSION = "external_progress_review_trigger_v0"
EXTERNAL_PROGRESS_REVIEW_SIGNALS: tuple[str, ...] = ("noul", "choice")
EXTERNAL_PROGRESS_REVIEW_FRONTIER_PREFIX = "progress_review:"

RunKey = tuple[str, str]


def _run_key(run: Mapping[str, Any]) -> RunKey:
    return (
        str(run.get("generated_at") or "").strip(),
        str(run.get("agent_id") or "").strip(),
    )


def index_progress_review_receipts(
    receipts: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[RunKey, Mapping[str, Any]]]:
    """Index receipts by turn identity and by (generated_at, agent_id) fallback."""

    by_turn: dict[str, Mapping[str, Any]] = {}
    by_key: dict[RunKey, Mapping[str, Any]] = {}
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
        key = _run_key(run)
        if turn:
            previous = by_turn.get(turn)
            if previous is None or int(previous.get("sequence") or 0) < sequence:
                by_turn[turn] = receipt
        elif key[0]:
            previous = by_key.get(key)
            if previous is None or int(previous.get("sequence") or 0) < sequence:
                by_key[key] = receipt
    return by_turn, by_key


def _single_agent_id(runs: list[Mapping[str, Any]]) -> str | None:
    agent_ids = {
        str(run.get("agent_id") or "").strip() for run in runs if run.get("agent_id")
    }
    agent_ids.discard("")
    return next(iter(agent_ids)) if len(agent_ids) == 1 else None


def external_progress_review_trigger(
    newest_first_runs: Iterable[Mapping[str, Any]],
    *,
    receipts: Iterable[Mapping[str, Any]],
    agent_id: str | None,
    threshold: int,
    signal: str,
    ack_recorded: Callable[[Mapping[str, Any]], bool],
) -> dict[str, Any] | None:
    """Return a trigger for consecutive completed drift receipts, else None.

    Streak rules, applied newest-first:
    - an acknowledged autonomous replan ends the scan (re-arm);
    - a transition without a receipt, or a receipt that is not `completed`,
      or whose drift signal is not True, ends the scan without a trigger;
    - retries of the same logical turn are one transition;
    - the same evidence id counts once;
    - every counted receipt must share one goal contract revision.
    """

    if signal not in EXTERNAL_PROGRESS_REVIEW_SIGNALS:
        return None
    required = max(2, int(threshold))
    normalized_agent_id = str(agent_id or "").strip()
    by_turn, by_key = index_progress_review_receipts(receipts)
    counted: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    seen_turns: set[str] = set()
    seen_evidence: set[str] = set()
    contract_revision: str | None = None
    for run in newest_first_runs:
        if not isinstance(run, Mapping):
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
        if receipt.get("status") != "completed":
            break
        drift_signal = receipt.get("drift_signal")
        if not isinstance(drift_signal, Mapping) or drift_signal.get(signal) is not True:
            break
        revision = str(receipt.get("contract_revision") or "")
        if contract_revision is None:
            contract_revision = revision
        elif revision != contract_revision:
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
        "agent_id": normalized_agent_id
        or _single_agent_id([run for run, _ in counted]),
        "contract_revision": contract_revision,
        "evidence_ids": [str(receipt["evidence_id"]) for _, receipt in counted],
        "receipt_ids": [str(receipt["receipt_id"]) for _, receipt in counted],
        "latest_generated_at": str(latest_run.get("generated_at") or ""),
        "oldest_counted_generated_at": str(oldest_run.get("generated_at") or ""),
        "latest_judgments": latest_receipt.get("judgments"),
        "frontier_identity": EXTERNAL_PROGRESS_REVIEW_FRONTIER_PREFIX
        + str(latest_receipt["evidence_id"]),
        "authority": "advisory_evidence_only",
    }


__all__ = [
    "EXTERNAL_PROGRESS_REVIEW_FRONTIER_PREFIX",
    "EXTERNAL_PROGRESS_REVIEW_SIGNALS",
    "EXTERNAL_PROGRESS_REVIEW_TRIGGER_KIND",
    "EXTERNAL_PROGRESS_REVIEW_TRIGGER_SCHEMA_VERSION",
    "external_progress_review_trigger",
    "index_progress_review_receipts",
]
