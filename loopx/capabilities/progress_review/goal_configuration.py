from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .policy import (
    PROGRESS_REVIEW_POLICY_SCHEMA_VERSION,
    normalize_progress_review_drift_threshold,
    normalize_progress_review_mode,
    normalize_progress_review_signal,
    progress_review_goal_policy,
    progress_review_goal_policy_summary,
)

GoalProgressReviewChange = tuple[bool, str | None, str | None, int | None]


def configuration_summary(goal: Mapping[str, Any]) -> dict[str, Any] | None:
    control_plane = goal.get("control_plane")
    if not isinstance(control_plane, Mapping) or not isinstance(
        control_plane.get("progress_review"), Mapping
    ):
        return None
    return dict(progress_review_goal_policy_summary(goal))


def normalize_change(
    mode: str | None,
    signal: str | None,
    drift_threshold: int | None,
    *,
    clear: bool,
) -> GoalProgressReviewChange:
    if clear and any(value is not None for value in (mode, signal, drift_threshold)):
        raise ValueError(
            "--clear-progress-review-configuration cannot be combined with "
            "progress-review settings"
        )
    normalized_mode = normalize_progress_review_mode(mode) if mode is not None else None
    normalized_signal = (
        normalize_progress_review_signal(signal) if signal is not None else None
    )
    normalized_threshold = (
        normalize_progress_review_drift_threshold(drift_threshold)
        if drift_threshold is not None
        else None
    )
    return clear, normalized_mode, normalized_signal, normalized_threshold


def apply_change(goal: dict[str, Any], change: GoalProgressReviewChange) -> None:
    clear, mode, signal, drift_threshold = change
    if not clear and all(value is None for value in (mode, signal, drift_threshold)):
        return
    raw_control_plane = goal.get("control_plane")
    control_plane: dict[str, Any] = (
        dict(raw_control_plane) if isinstance(raw_control_plane, dict) else {}
    )
    if clear:
        control_plane.pop("progress_review", None)
        if control_plane:
            goal["control_plane"] = control_plane
        else:
            goal.pop("control_plane", None)
        return
    current = progress_review_goal_policy(goal)
    control_plane["progress_review"] = {
        "schema_version": PROGRESS_REVIEW_POLICY_SCHEMA_VERSION,
        "mode": mode if mode is not None else current["mode"],
        "signal": signal if signal is not None else current["signal"],
        "drift_threshold": (
            drift_threshold
            if drift_threshold is not None
            else current["drift_threshold"]
        ),
    }
    goal["control_plane"] = control_plane


__all__ = [
    "GoalProgressReviewChange",
    "apply_change",
    "configuration_summary",
    "normalize_change",
]
