from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from .todos.contract import normalize_todo_claimed_by
from .operator_inbox_binding import operator_inbox_binding


def reward_memory_host_coverage() -> list[dict[str, str]]:
    """Project actual host lifecycle wiring without inferring parity."""

    return [
        {
            "host_id": "codex_cli_turn",
            "automatic_recall": "connected",
            "automatic_ingest": "connected_post_settlement",
        },
        {
            "host_id": "generic_cli_turn",
            "automatic_recall": "connected",
            "automatic_ingest": "uncovered",
        },
        {
            "host_id": "dsh_turn",
            "automatic_recall": "connected_task_body",
            "automatic_ingest": "uncovered",
        },
        {
            "host_id": "codex_app_quota",
            "automatic_recall": "connected",
            "automatic_ingest": "connected_refresh_spend_post_settlement",
        },
        {
            "host_id": "lark",
            "automatic_recall": "status_projection_only",
            "automatic_ingest": "uncovered",
        },
    ]


def reward_memory_goal_policy(goal: Mapping[str, Any]) -> dict[str, Any]:
    """Return the provider-neutral opt-in policy for one goal."""

    control_plane = (
        goal.get("control_plane")
        if isinstance(goal.get("control_plane"), Mapping)
        else {}
    )
    raw = (
        control_plane.get("reward_memory")
        if isinstance(control_plane.get("reward_memory"), Mapping)
        else {}
    )
    enabled_agents: list[str] = []
    for value in raw.get("enabled_agents") or []:
        agent_id = normalize_todo_claimed_by(value)
        if agent_id and agent_id not in enabled_agents:
            enabled_agents.append(agent_id)
    experimental = raw.get("experimental") is True
    enablement_receipts: dict[str, dict[str, Any]] = {}
    raw_receipts = raw.get("enablement_receipts")
    if isinstance(raw_receipts, Mapping):
        for agent_id in enabled_agents:
            receipt = raw_receipts.get(agent_id)
            if not isinstance(receipt, Mapping):
                continue
            enablement_receipts[agent_id] = {
                key: receipt[key]
                for key in (
                    "schema_version",
                    "status",
                    "goal_id",
                    "agent_id",
                    "config_digest",
                    "provider_id",
                    "isolation_mode",
                    "actor_binding_verified",
                    "writability_verified",
                    "exact_readback_verified",
                    "probe_count",
                    "write_count",
                    "external_writes_performed",
                    "observed_at",
                    "provider_preflight_performed",
                    "reason_codes",
                )
                if key in receipt
            }
    return {
        "enabled": raw.get("enabled") is True and experimental,
        "experimental": experimental,
        "config_path": str(raw.get("config_path") or "").strip(),
        "config_digest": str(raw.get("config_digest") or "").strip(),
        "enabled_agents": enabled_agents,
        "enablement_receipts": enablement_receipts,
        "automation": (
            dict(raw["automation"])
            if isinstance(raw.get("automation"), Mapping)
            else {}
        ),
        "automation_intent": (
            dict(raw["automation_intent"])
            if isinstance(raw.get("automation_intent"), Mapping)
            else {}
        ),
    }


def reward_memory_goal_policy_summary(goal: Mapping[str, Any]) -> dict[str, Any]:
    policy = reward_memory_goal_policy(goal)
    binding_revision = ""
    if policy["config_path"] and policy["config_digest"]:
        binding_revision = "sha256:" + hashlib.sha256(
            (
                f"{policy['config_path']}\0{policy['config_digest']}\0"
                + "\0".join(policy["enabled_agents"])
            ).encode("utf-8")
        ).hexdigest()
    binding = operator_inbox_binding(
        project=str(goal.get("repo") or ""),
        config_path=policy["config_path"],
        expected_digest=policy["config_digest"],
    )
    recorded_verified_agents = sorted(
        agent_id
        for agent_id, receipt in policy["enablement_receipts"].items()
        if receipt.get("status") == "verified"
        and receipt.get("writability_verified") is True
        and receipt.get("exact_readback_verified") is True
    )
    # Import at the projection boundary: the capability consumes the policy above.
    # Reuse its full local validation rather than maintaining a second receipt rule.
    from ..capabilities.reward_memory.experiment import (
        resolve_goal_reward_memory_experiment,
    )

    effective_verified_agents = []
    for agent_id in recorded_verified_agents:
        try:
            status, _ = resolve_goal_reward_memory_experiment(
                goal=goal, agent_id=agent_id
            )
        except ValueError:
            continue
        if status.get("available") is True:
            effective_verified_agents.append(agent_id)
    effective_available = bool(effective_verified_agents)
    return {
        "enabled": policy["enabled"],
        "binding_status": binding["status"],
        "effective_available": effective_available,
        "desired_automation": dict(policy["automation"]),
        "recorded_verified_agents": recorded_verified_agents,
        "experimental": policy["experimental"],
        "config_pointer_registered": bool(policy["config_path"]),
        "binding_revision": binding_revision,
        "automatic_ingest": effective_available
        and policy["automation"].get("automatic_ingest") is True,
        "automatic_recall": effective_available
        and policy["automation"].get("automatic_recall") is True,
        "automation_intent": dict(policy["automation_intent"]),
        "host_coverage": reward_memory_host_coverage(),
        "enabled_agents": list(policy["enabled_agents"]),
        "enablement_verified_agents": effective_verified_agents,
    }


__all__ = [
    "reward_memory_goal_policy",
    "reward_memory_goal_policy_summary",
    "reward_memory_host_coverage",
]
