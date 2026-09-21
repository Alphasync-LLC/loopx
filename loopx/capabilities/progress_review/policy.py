"""Per-goal policy for the optional scoped progress-review sentinel.

The policy decides only whether typed external review receipts are recorded
(`shadow`) or may become the existing autonomous replan obligation (`assist`).
It grants no file, provider, pause, or settlement authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PROGRESS_REVIEW_POLICY_SCHEMA_VERSION = "progress_review_policy_v0"
PROGRESS_REVIEW_MODES: tuple[str, ...] = ("off", "shadow", "assist")
PROGRESS_REVIEW_SIGNALS: tuple[str, ...] = ("noul", "choice")
PROGRESS_REVIEW_DEFAULT_MODE = "off"
PROGRESS_REVIEW_DEFAULT_SIGNAL = "noul"
PROGRESS_REVIEW_DEFAULT_DRIFT_THRESHOLD = 2
PROGRESS_REVIEW_MIN_DRIFT_THRESHOLD = 2
PROGRESS_REVIEW_MAX_DRIFT_THRESHOLD = 20


def normalize_progress_review_mode(value: Any) -> str:
    mode = str(value or "").strip()
    if mode not in PROGRESS_REVIEW_MODES:
        raise ValueError(
            "progress_review.mode must be one of: " + ", ".join(PROGRESS_REVIEW_MODES)
        )
    return mode


def normalize_progress_review_signal(value: Any) -> str:
    signal = str(value or "").strip()
    if signal not in PROGRESS_REVIEW_SIGNALS:
        raise ValueError(
            "progress_review.signal must be one of: "
            + ", ".join(PROGRESS_REVIEW_SIGNALS)
        )
    return signal


def normalize_progress_review_drift_threshold(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("progress_review.drift_threshold must be an integer")
    if not (
        PROGRESS_REVIEW_MIN_DRIFT_THRESHOLD
        <= value
        <= PROGRESS_REVIEW_MAX_DRIFT_THRESHOLD
    ):
        raise ValueError(
            "progress_review.drift_threshold must be between "
            f"{PROGRESS_REVIEW_MIN_DRIFT_THRESHOLD} and "
            f"{PROGRESS_REVIEW_MAX_DRIFT_THRESHOLD}"
        )
    return int(value)


def _default_policy() -> dict[str, Any]:
    return {
        "schema_version": PROGRESS_REVIEW_POLICY_SCHEMA_VERSION,
        "mode": PROGRESS_REVIEW_DEFAULT_MODE,
        "signal": PROGRESS_REVIEW_DEFAULT_SIGNAL,
        "drift_threshold": PROGRESS_REVIEW_DEFAULT_DRIFT_THRESHOLD,
    }


def progress_review_goal_policy(goal: Mapping[str, Any]) -> dict[str, Any]:
    """Return the effective policy; any malformed stored block fails closed to off."""

    control_plane = goal.get("control_plane")
    raw = (
        control_plane.get("progress_review")
        if isinstance(control_plane, Mapping)
        else None
    )
    if not isinstance(raw, Mapping):
        return _default_policy()
    try:
        return {
            "schema_version": PROGRESS_REVIEW_POLICY_SCHEMA_VERSION,
            "mode": normalize_progress_review_mode(
                raw.get("mode", PROGRESS_REVIEW_DEFAULT_MODE)
            ),
            "signal": normalize_progress_review_signal(
                raw.get("signal", PROGRESS_REVIEW_DEFAULT_SIGNAL)
            ),
            "drift_threshold": normalize_progress_review_drift_threshold(
                raw.get("drift_threshold", PROGRESS_REVIEW_DEFAULT_DRIFT_THRESHOLD)
            ),
        }
    except (TypeError, ValueError):
        return {**_default_policy(), "invalid_configuration": True}


def progress_review_goal_policy_summary(goal: Mapping[str, Any]) -> dict[str, Any]:
    policy = progress_review_goal_policy(goal)
    summary = {
        "mode": policy["mode"],
        "signal": policy["signal"],
        "drift_threshold": policy["drift_threshold"],
    }
    if policy.get("invalid_configuration"):
        summary["invalid_configuration"] = True
    return summary


__all__ = [
    "PROGRESS_REVIEW_DEFAULT_DRIFT_THRESHOLD",
    "PROGRESS_REVIEW_DEFAULT_MODE",
    "PROGRESS_REVIEW_DEFAULT_SIGNAL",
    "PROGRESS_REVIEW_MAX_DRIFT_THRESHOLD",
    "PROGRESS_REVIEW_MIN_DRIFT_THRESHOLD",
    "PROGRESS_REVIEW_MODES",
    "PROGRESS_REVIEW_POLICY_SCHEMA_VERSION",
    "PROGRESS_REVIEW_SIGNALS",
    "normalize_progress_review_drift_threshold",
    "normalize_progress_review_mode",
    "normalize_progress_review_signal",
    "progress_review_goal_policy",
    "progress_review_goal_policy_summary",
]
