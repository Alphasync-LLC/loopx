"""Normalize compatibility input for the one typed succession read policy."""
from __future__ import annotations

from typing import Any

from ..effect_runtime import effect_runtime_result
from .contract import (
    normalize_todo_id, normalize_todo_id_list, normalize_todo_status,
    normalize_todo_task_class, normalize_todo_no_followup,
    normalize_todo_resume_when, normalize_todo_excluded_agents,
)


def succession_facts(item: dict[str, Any]) -> dict[str, Any]:
    resume = normalize_todo_resume_when(item.get("resume_when")) or ""
    return {
        "todo_id": normalize_todo_id(item.get("todo_id")),
        "status": normalize_todo_status(item.get("status")) or ("done" if item.get("done") else "open"),
        "active": (item.get("archive_state") or "active") == "active",
        "advancement": normalize_todo_task_class(item.get("task_class"), text=str(item.get("text") or ""),
            action_kind=item.get("action_kind")) == "advancement_task",
        "no_followup": normalize_todo_no_followup(item.get("no_followup")) is True,
        "successors": normalize_todo_id_list(item.get("successor_todo_ids")),
        "superseded_by": normalize_todo_id(item.get("superseded_by")),
        "unblocks": normalize_todo_id(item.get("unblocks_todo_id")),
        "resumes": normalize_todo_id(resume.partition(":")[2]) if resume.startswith("todo_done:") else None,
        "handoff": bool(normalize_todo_excluded_agents(item.get("excluded_agents")))
            and bool(normalize_todo_id(item.get("unblocks_todo_id"))),
        "context_fields": sorted(key for key, value in item.items()
            if value is not None and key != "succession_evaluation"),
    }


def project_succession(items: list[dict[str, Any]], *, reuse: bool = False) -> list[dict[str, Any]]:
    rows = [succession_facts(item) for item in items]
    # Archived histories repeat field-presence shapes thousands of times. Intern
    # those shapes, preserving the complete graph inside the existing RPC budget.
    contexts: list[list[str]] = []
    context_ids: dict[tuple[str, ...], int] = {}
    for row in rows:
        shape = tuple(row["context_fields"])
        if shape not in context_ids:
            context_ids[shape] = len(contexts)
            contexts.append(list(shape))
        row["context_fields"] = context_ids[shape]
    request: dict[str, Any] = {"schema_version": "todo_succession_request_v0",
        "rows": rows, "context_field_sets": contexts}
    if reuse:
        request["evaluations"] = [item.get("succession_evaluation") for item in items]
    result = effect_runtime_result("todo.succession.project", request)
    if not isinstance(result, dict) or result.get("schema_version") != "todo_succession_result_v0":
        raise ValueError("invalid typed Todo succession result")
    evaluations = result.get("evaluations")
    if not isinstance(evaluations, list) or len(evaluations) != len(items) or any(not isinstance(row, dict) for row in evaluations):
        raise ValueError("invalid typed Todo succession cardinality")
    return evaluations


def evaluate_succession(items: list[dict[str, Any]], lineage: list[dict[str, Any]] | None = None) -> None:
    # Active evaluated rows override their unevaluated source versions; retained
    # history and other roles remain graph evidence but never become active rows.
    if not items:
        return
    # Replace one matching source row, not every occurrence of its identity.
    # Duplicate archive/role identities must remain visible to the TS validator.
    selected = {(normalize_todo_id(item.get("todo_id")), item.get("role"), item.get("archive_state") or "active")
        for item in items}
    source = []
    for item in lineage or []:
        key = (normalize_todo_id(item.get("todo_id")), item.get("role"), item.get("archive_state") or "active")
        if key in selected:
            selected.remove(key)
        else:
            source.append(item)
    source.extend(items)
    evaluations = project_succession(source)
    for item, evaluation in zip(items, evaluations[len(source) - len(items):], strict=True):
        item["succession_evaluation"] = evaluation


def public_todo_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Drop the internal full-graph handoff once a consumer has selected rows."""
    return {**summary, "items": [
        {key: value for key, value in item.items() if key != "succession_evaluation"}
        if isinstance(item, dict) else item
        for item in summary.get("items") or []
    ]}
