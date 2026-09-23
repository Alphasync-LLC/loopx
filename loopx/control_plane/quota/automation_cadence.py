"""Transport to the typed automatic-run cadence policy owner."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from ..effect_runtime import effect_runtime_result


def automation_cadence(
    runtime_root: Path | str,
    goal_id: str,
    agent_id: str | None = None,
    automation_id: str | None = None,
    *,
    operation: str = "read",
    **fields: Any,
) -> dict[str, Any]:
    result = effect_runtime_result(
        "quota.automation_cadence.manage",
        {
            "runtime_root": str(runtime_root),
            "goal_id": goal_id,
            "agent_id": agent_id,
            "automation_id": automation_id,
            "operation": operation,
            **fields,
        },
        retry_safe=operation == "read",
    )
    if (
        not isinstance(result, dict)
        or result.get("schema_version") != "automation_cadence_result_v1"
    ):
        raise RuntimeError("automation cadence result mismatch")
    return result


def cadence_progression(progression: list[int], min_interval_minutes: int) -> list[int]:
    return effect_runtime_result(
        "quota.automation_cadence.progression",
        {
            "progression": progression,
            "min_interval_minutes": min_interval_minutes,
        },
    )["progression"]
