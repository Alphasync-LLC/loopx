"""Load one Goal's typed progress-review receipts for read models and writebacks.

Both `loopx status` and the refresh-state replan writeback call this so the
obligation a reader shows and the obligation an acknowledgement is judged
against come from the same receipts under the same policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any


def external_progress_review_context(
    goal: Mapping[str, Any],
    runtime_root: Path | None,
) -> dict[str, Any] | None:
    """Return policy, receipts and a compact summary, or None when off.

    `off`, an unknown runtime root or a missing goal id load nothing, so the
    default configuration adds zero work and zero fields.
    """

    from .policy import progress_review_goal_policy
    from .receipt import load_progress_review_receipts, progress_review_receipt_summary

    policy = progress_review_goal_policy(goal)
    goal_id = str(goal.get("id") or "").strip()
    if policy["mode"] == "off" or runtime_root is None or not goal_id:
        return None
    try:
        loaded, rejected = load_progress_review_receipts(Path(runtime_root), goal_id)
    except (OSError, ValueError):
        loaded, rejected = [], 0
    pinned = policy.get("contract_revision")
    if pinned:
        # Receipts bound to another goal contract are history, never current evidence.
        receipts = [item for item in loaded if item["contract_revision"] == pinned]
        stale = len(loaded) - len(receipts)
    else:
        receipts, stale = loaded, 0
    return {
        "policy": policy,
        "receipts": receipts,
        "summary": progress_review_receipt_summary(
            receipts, policy=policy, rejected=rejected, stale=stale
        ),
    }


__all__ = ["external_progress_review_context"]
