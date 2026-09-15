"""Fail-closed merge readiness for one already-reviewed exact PR head."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SCHEMA_VERSION = "pull_request_merge_readiness_v0"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


def build_merge_readiness(
    *,
    repository: str,
    expected_exact_head: str,
    item: Mapping[str, Any],
    review_threads: Mapping[str, Any],
    source: str,
) -> dict[str, Any]:
    """Return a read-only pre-merge gate without granting merge authority."""

    number = item.get("number")
    head_oid = _text(item.get("head_oid"))
    observed_exact_head = f"{number}@{head_oid}" if number and head_oid else None
    conclusion = _mapping(item.get("review_conclusion"))
    checks = _mapping(item.get("checks"))
    thread_complete = review_threads.get("complete") is True
    unresolved_threads = review_threads.get("unresolved_count")
    blockers: list[str] = []

    if _text(item.get("state")).upper() != "OPEN":
        blockers.append("pull_request_not_open")
    if item.get("is_draft") is True:
        blockers.append("draft_pull_request")
    if observed_exact_head != expected_exact_head:
        blockers.append("remote_head_mismatch")

    if conclusion.get("valid") is not True:
        blockers.append("current_head_review_missing_or_invalid")
    elif _text(conclusion.get("verdict")).upper() != "APPROVE":
        blockers.append("current_head_conclusion_not_approval")

    author_owned_fallback = bool(
        item.get("author_owned") is True
        and conclusion.get("valid") is True
        and _text(conclusion.get("state")).upper() == "COMMENTED"
        and _text(conclusion.get("verdict")).upper() == "APPROVE"
    )
    review_decision = _text(item.get("review_decision")).upper()
    if review_decision != "APPROVED" and not author_owned_fallback:
        blockers.append("github_review_decision_not_approved")

    if not thread_complete:
        blockers.append("review_threads_incomplete")
    elif type(unresolved_threads) is not int:
        blockers.append("review_threads_incomplete")
    elif unresolved_threads > 0:
        blockers.append("unresolved_review_threads")

    merge_state = _text(item.get("merge_state")).upper()
    if merge_state in {"BEHIND", "DIRTY", "DRAFT"}:
        blockers.append("merge_state_requires_update")
    elif merge_state in {"", "UNKNOWN"}:
        blockers.append("merge_state_unverified")

    blockers = list(dict.fromkeys(blockers))
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "ready": not blockers,
        "repository": repository,
        "source": source,
        "expected_exact_head": expected_exact_head,
        "observed_exact_head": observed_exact_head,
        "url": item.get("url"),
        "state": item.get("state"),
        "merge_state": item.get("merge_state"),
        "review_decision": item.get("review_decision"),
        "review_conclusion": dict(conclusion),
        "checks": dict(checks),
        "review_threads": dict(review_threads),
        "author_owned_commented_approval": author_owned_fallback,
        # BLOCKED is an opaque GitHub protection aggregate, not local evidence.
        "admin_bypass_required": merge_state == "BLOCKED",
        "ci_policy": "not_consulted",
        "blocking_reasons": blockers,
        "authority": {
            "grants_merge_authority": False,
            "admin_bypass_overrides_this_gate": False,
            "required_timing": "immediately_before_merge",
            "head_change_action": "restart_review_and_rerun_gate",
        },
    }
