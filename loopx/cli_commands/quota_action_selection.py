from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ..control_plane.quota.effective_action import EffectiveAction
from ..control_plane.quota.error_codes import (
    HeartbeatReceiptIdentityConflictError,
    QuotaActionSelectionConflictError,
    QuotaActionSelectionConflictKind,
)
from ..control_plane.quota.heartbeat_receipt import (
    HEARTBEAT_RECEIPT_SCHEMA_VERSION,
    find_heartbeat_receipt,
    heartbeat_receipt_pending_action_todo_id,
    heartbeat_receipt_settlement_replan_obligation_id,
    heartbeat_receipt_settlement_todo_id,
    retain_pending_heartbeat_action_selection,
)
from ..control_plane.scheduler.execution_context import (
    GUIDED_START_TURN_RUNTIME_PROFILES,
    render_scheduler_execution_args,
)
from ..control_plane.todos.contract import normalize_todo_id
from ..control_plane.work_items.action_selection_contract import (
    apply_action_selection_recovery,
)
from .quota_context import QuotaCommandContext


@dataclass(frozen=True, slots=True)
class RequestedQuotaActionSelection:
    requested_todo_id: str | None
    receipt: dict[str, object] | None
    receipt_bound_todo_id: str | None
    receipt_bound_replan_obligation_id: str | None
    receipt_pending_action_todo_id: str | None
    receipt_identity_upgraded: bool

    @property
    def requested_todo_id_for_decision(self) -> str | None:
        if self.receipt_bound_todo_id is not None:
            return None
        return self.requested_todo_id

    @property
    def retained_todo_id_for_decision(self) -> str | None:
        if (
            self.requested_todo_id is not None
            or self.receipt_bound_todo_id is not None
            or self.receipt_bound_replan_obligation_id is not None
        ):
            return None
        return self.receipt_pending_action_todo_id


@dataclass(frozen=True, slots=True)
class ActionSelectionPreflightResult:
    rejected: bool
    receipt: dict[str, object] | None
    receipt_status: str
    receipt_appended: bool


def _requested_quota_action_todo_id(
    args: argparse.Namespace,
) -> str | None:
    if not (
        bool(args.codex_app)
        or bool(getattr(args, "trae_app", False))
        or args.runtime_profile
        in {profile.value for profile in GUIDED_START_TURN_RUNTIME_PROFILES}
    ):
        return None
    return normalize_todo_id(args.todo_id)


def load_requested_quota_action_selection(
    args: argparse.Namespace,
    *,
    runtime_root: Path,
    turn_instance_id: str | None,
) -> RequestedQuotaActionSelection:
    requested_todo_id = _requested_quota_action_todo_id(args)
    if not turn_instance_id:
        return RequestedQuotaActionSelection(
            requested_todo_id=requested_todo_id,
            receipt=None,
            receipt_bound_todo_id=None,
            receipt_bound_replan_obligation_id=None,
            receipt_pending_action_todo_id=None,
            receipt_identity_upgraded=False,
        )
    existing = find_heartbeat_receipt(
        runtime_root,
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        turn_instance_id=turn_instance_id,
    )
    if not existing:
        return RequestedQuotaActionSelection(
            requested_todo_id=requested_todo_id,
            receipt=None,
            receipt_bound_todo_id=None,
            receipt_bound_replan_obligation_id=None,
            receipt_pending_action_todo_id=None,
            receipt_identity_upgraded=False,
        )
    details_value = existing.get("details")
    details: Mapping[str, object] = (
        details_value if isinstance(details_value, Mapping) else {}
    )
    return RequestedQuotaActionSelection(
        requested_todo_id=requested_todo_id,
        receipt=existing,
        receipt_bound_todo_id=heartbeat_receipt_settlement_todo_id(existing),
        receipt_bound_replan_obligation_id=(
            heartbeat_receipt_settlement_replan_obligation_id(existing)
        ),
        receipt_pending_action_todo_id=(
            heartbeat_receipt_pending_action_todo_id(existing)
        ),
        receipt_identity_upgraded=(
            str(details.get("settlement_receipt_revision") or "") == "identity_upgrade"
        ),
    )


def _apply_requested_quota_action_selection_preflight(
    payload: dict[str, object],
    *,
    requested_todo_id: str | None,
    receipt_bound_todo_id: str | None,
    receipt_bound_replan_obligation_id: str | None,
    receipt_pending_action_todo_id: str | None,
    receipt_identity_upgraded: bool,
) -> bool:
    if not requested_todo_id:
        return False
    if receipt_bound_todo_id:
        if requested_todo_id != receipt_bound_todo_id:
            raise HeartbeatReceiptIdentityConflictError(
                "heartbeat receipt settlement identity conflicts with the "
                "current selected Todo: explicitly requested Todo differs"
            )
        return False
    selected_todo = payload.get("selected_todo")
    selected_todo_id = (
        normalize_todo_id(selected_todo.get("todo_id"))
        if isinstance(selected_todo, Mapping)
        else None
    )
    qualification_value = payload.get("action_selection_qualification")
    qualification: Mapping[str, object] = (
        qualification_value if isinstance(qualification_value, Mapping) else {}
    )
    if selected_todo_id is None and str(qualification.get("state") or "") == (
        "qualified"
    ):
        # Recovery names the prior Turn's Todo in the qualification instead of
        # projecting it as the current selected Todo.
        qualification_selected = qualification.get("selected_todo")
        selected_todo_id = (
            normalize_todo_id(qualification_selected.get("todo_id"))
            if isinstance(qualification_selected, Mapping)
            else None
        )
    if receipt_bound_replan_obligation_id:
        if not receipt_identity_upgraded:
            # A Turn that began in autonomous replan has no Todo selection
            # authority to replace. A later same-Turn selection is a replay.
            return False
        if requested_todo_id == receipt_pending_action_todo_id:
            return False
        raise QuotaActionSelectionConflictError(
            QuotaActionSelectionConflictKind.CONFLICT,
            requested_todo_id=requested_todo_id,
            selected_todo_id=receipt_pending_action_todo_id,
            qualification_state="retained_selection",
        )
    selection_binding = (
        selected_todo.get("selection_binding")
        if isinstance(selected_todo, Mapping)
        else None
    )
    execution_obligation_value = payload.get("execution_obligation")
    execution_obligation: Mapping[str, object] = (
        execution_obligation_value
        if isinstance(execution_obligation_value, Mapping)
        else {}
    )
    interaction_value = payload.get("interaction_contract")
    interaction: Mapping[str, object] = (
        interaction_value if isinstance(interaction_value, Mapping) else {}
    )
    agent_channel_value = interaction.get("agent_channel")
    agent_channel: Mapping[str, object] = (
        agent_channel_value if isinstance(agent_channel_value, Mapping) else {}
    )
    pending_selection_delivery_qualified = (
        selection_binding == "pending_action_selection"
        and payload.get("normal_delivery_allowed") is True
    )
    pending_selection_workspace_repair_qualified = (
        selection_binding == "pending_action_selection"
        and payload.get("workspace_repair_allowed") is True
        and payload.get("effective_action")
        == EffectiveAction.AGENT_WORKSPACE_REPAIR.value
        and execution_obligation.get("kind") == "agent_workspace_repair"
        and execution_obligation.get("must_attempt_work") is True
        and agent_channel.get("must_attempt") is True
        and agent_channel.get("delivery_allowed") is False
    )
    exact_current_obligation_qualified = (
        selection_binding != "pending_action_selection"
        and execution_obligation.get("must_attempt_work") is True
        and agent_channel.get("must_attempt") is True
    )
    if (
        selected_todo_id == requested_todo_id
        and payload.get("ok") is True
        and payload.get("should_run") is True
        and (
            pending_selection_delivery_qualified
            or pending_selection_workspace_repair_qualified
            or exact_current_obligation_qualified
        )
    ):
        return False

    if not isinstance(qualification_value, Mapping):
        raise QuotaActionSelectionConflictError(
            QuotaActionSelectionConflictKind.UNQUALIFIED,
            requested_todo_id=requested_todo_id,
            selected_todo_id=selected_todo_id,
        )
    qualification_state = str(qualification.get("state") or "")
    if qualification_state not in {"deferred", "rejected"}:
        raise QuotaActionSelectionConflictError(
            QuotaActionSelectionConflictKind.CONFLICT,
            requested_todo_id=requested_todo_id,
            selected_todo_id=selected_todo_id,
            qualification_state=qualification_state,
        )
    qualification_reason = str(
        qualification.get("reason") or "candidate_not_currently_eligible"
    )
    deferred = qualification_state == "deferred"
    auxiliary_monitor = (
        qualification_reason == "auxiliary_monitor_not_selectable_in_advancement_lane"
    )
    error_code = (
        "quota_action_selection_deferred"
        if deferred
        else "quota_action_selection_rejected"
    )
    payload.update(
        {
            "ok": False,
            "decision": "skip",
            "should_run": False,
            "effective_action": EffectiveAction.QUOTA_SKIP.value,
            "state": error_code,
            "waiting_on": "codex",
            "status": error_code,
            "error_code": error_code,
            "reason": (
                "explicit action selection was deferred by the current "
                f"delivery frontier: {qualification_reason}"
                if deferred
                else "explicit action selection is not currently eligible: "
                f"{qualification_reason}"
            ),
            "recommended_action": (
                "handle the current delivery preemption, then rerun quota "
                "should-run with the same --turn-instance-id; omit --todo-id "
                "first when a refreshed action portfolio is needed"
                if deferred
                else "the due monitor is visible as auxiliary context, not an "
                "independently selectable action in the current advancement lane; "
                "choose a current advancement Todo, or rerun after the monitor "
                "becomes the hard lane"
                if auxiliary_monitor
                else "rerun quota should-run with the same --turn-instance-id "
                "without --todo-id, then choose a currently eligible Todo"
            ),
        }
    )
    return True


def reconcile_requested_quota_action_selection(
    payload: dict[str, object],
    args: argparse.Namespace,
    *,
    registry_path: Path,
    context: QuotaCommandContext,
    selection: RequestedQuotaActionSelection,
) -> ActionSelectionPreflightResult:
    rejected = _apply_requested_quota_action_selection_preflight(
        payload,
        requested_todo_id=selection.requested_todo_id,
        receipt_bound_todo_id=selection.receipt_bound_todo_id,
        receipt_bound_replan_obligation_id=(
            selection.receipt_bound_replan_obligation_id
        ),
        receipt_pending_action_todo_id=selection.receipt_pending_action_todo_id,
        receipt_identity_upgraded=selection.receipt_identity_upgraded,
    )
    if not rejected:
        return ActionSelectionPreflightResult(
            rejected=False,
            receipt=selection.receipt,
            receipt_status="replayed",
            receipt_appended=False,
        )

    apply_action_selection_recovery(
        payload,
        registry_path=str(registry_path),
        runtime_root=str(context.runtime_root),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        turn_instance_id=context.heartbeat_turn_id,
        available_capabilities=args.available_capabilities,
        scheduler_args=render_scheduler_execution_args(
            scheduler_execution_context=context.scheduler_context
        ),
    )
    obligation = payload.get("execution_obligation")
    if isinstance(obligation, dict):
        obligation.update(
            must_attempt_work=False,
            delivery_allowed=False,
            reason=payload["recommended_action"],
        )
    receipt, receipt_status, receipt_appended = _retain_deferred_action_selection(
        payload,
        args,
        runtime_root=context.runtime_root,
        turn_instance_id=context.heartbeat_turn_id,
        selection=selection,
    )
    return ActionSelectionPreflightResult(
        rejected=True,
        receipt=receipt,
        receipt_status=receipt_status,
        receipt_appended=receipt_appended,
    )


def attach_uncommitted_action_selection_receipt(
    payload: dict[str, object],
    *,
    turn_instance_id: str,
) -> None:
    """Expose an accurate non-durable receipt for a rejected preflight."""

    payload["heartbeat_receipt"] = {
        "schema_version": HEARTBEAT_RECEIPT_SCHEMA_VERSION,
        "turn_instance_id": turn_instance_id,
        "status": "not_committed",
        "stall_observation": "not_evaluated",
        "reason_code": str(
            payload.get("error_code") or "quota_action_selection_rejected"
        ),
    }


def commit_requested_action_selection(
    payload: Mapping[str, object],
    *,
    requested_todo_id: str | None,
) -> None:
    """Project the exact requested selection only after receipt reconciliation."""

    selected_todo = payload.get("selected_todo")
    if (
        requested_todo_id
        and isinstance(selected_todo, dict)
        and normalize_todo_id(selected_todo.get("todo_id")) == requested_todo_id
    ):
        selected_todo["selection_binding"] = "heartbeat_receipt"


def _retain_deferred_action_selection(
    payload: Mapping[str, object],
    args: argparse.Namespace,
    *,
    runtime_root: Path,
    turn_instance_id: str | None,
    selection: RequestedQuotaActionSelection,
) -> tuple[dict[str, object] | None, str, bool]:
    """Append a deferred explicit choice without granting settlement authority."""

    qualification = payload.get("action_selection_qualification")
    if (
        not turn_instance_id
        or selection.receipt is None
        or selection.requested_todo_id is None
        or not isinstance(qualification, Mapping)
        or qualification.get("state") != "deferred"
    ):
        return selection.receipt, "replayed", False
    retained, appended = retain_pending_heartbeat_action_selection(
        runtime_root,
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        turn_instance_id=turn_instance_id,
        todo_id=selection.requested_todo_id,
        reason=str(qualification.get("reason") or "current_delivery_gate"),
    )
    return retained, "selection_retained" if appended else "replayed", appended
