"""Trusted demo-only composition of canonical Todo + Turn; not a fleet service."""
from __future__ import annotations

import asyncio
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

import research_team as demo
from scenario import REVISIONS, assignments, evidence, upstream, encoded
from acceptance import validate_delivery, validate_member, canonical_tasks, require_completed

server = FastMCP("synthetic-research-team")
worker_server = FastMCP("synthetic-research-member")
lock = asyncio.Lock()
worker_identity: tuple[str, str] | None = None


def root(actor: str = "lead", revision: str = "report") -> Path:
    path = Path(os.environ["LOOPX_RESEARCH_DEMO_ROOT"]).resolve()
    workspace = path / "lead" if actor == "lead" else path / actor / revision
    if (os.environ.get("LOOPX_TURN_GOAL_ID") != demo.GOAL or os.environ.get("LOOPX_TURN_AGENT_ID") != actor
            or Path(os.environ["LOOPX_TURN_WORKSPACE"]).resolve() != workspace):
        raise ValueError("demo_caller_not_bound")
    return path


@server.tool()
def read_assignment() -> dict:
    """Read synthetic inputs, authorized roster and independently checked report contract."""
    path = root()
    return {"assignments": assignments(path), "inputs": [evidence(revision) for revision in REVISIONS],
            "objective": "Compare the initial and corrected evidence. Obtain an independently accepted result "
                         "for each authorized worker/revision assignment. You choose questions/order; revise rejected work. "
                         "Use all four accepted artifacts in the report. Count source families corroborating "
                         "CURRENT-period figures only, excluding historical comparison material. No trades or external information.",
            "report_fields": {"initial_normalized_fcf": "integer", "corrected_normalized_fcf": "integer",
                              "revision_delta": "corrected minus initial", "growth_supported": "boolean",
                              "independent_source_families": "integer", "repost_stale_after_correction": "boolean",
                              "dependencies": {"worker/revision": "artifact_sha256 returned by delegate"}, "reason": "short explanation"}}


@server.tool()
async def delegate(worker: str, revision: str, question: str) -> dict:
    """Assign a question to a registered member; return independently accepted evidence or rejection.

    Use the exact worker/revision pairs from read_assignment. Two attempts per pair.
    Exact accepted dependencies are reused, not rerun. Canonical Todo/Turn own admission and acceptance.
    """
    async with lock:
        return await asyncio.to_thread(demo.delegate, root(), worker, revision, question)


@server.tool()
def write_report(report: dict) -> dict:
    """Write the synthesized report and check all dependency hashes and substantive conclusions."""
    path = root()
    if len(json.dumps(report)) > 16_000:
        raise ValueError("report_too_large")
    demo.write(path / "lead" / "report.json", report)
    try:
        validate_delivery(path)
    except ValueError as exc:
        return {"accepted": False, "reason": str(exc)[:200]}
    except (OSError, KeyError, TypeError) as exc:
        return {"accepted": False, "reason": type(exc).__name__ + ":report_or_dependencies_rejected"}
    return {"accepted": True, "note": "Artifact checks passed. Host revalidates before canonical Todo completion; Goal stays active."}


def worker_workspace() -> tuple[Path, str]:
    if worker_identity is None:
        raise ValueError("worker_identity_required")
    actor, revision = worker_identity
    path = root(actor, revision)
    if not any(row["worker"] == actor and row["revision"] == revision for row in assignments(path)):
        raise ValueError("worker_assignment_not_authorized")
    if os.environ.get("LOOPX_TURN_TODO_ID") != demo.todo_id(actor, revision):
        raise ValueError("worker_todo_not_bound")
    return path / actor / revision, revision


@worker_server.tool()
def read_input() -> dict:
    """Read only this member's assigned synthetic input and output contract."""
    workspace, _ = worker_workspace()
    raw = (workspace / "input.json").read_bytes()
    dependency = upstream(workspace.parent.parent, workspace.parent.name, workspace.name)
    adopted = {}
    if dependency:
        actor, revision = dependency.split("/")
        path = workspace.parent.parent
        require_completed(canonical_tasks(path), actor, revision)
        artifact = validate_member(path, actor, revision)
        adopted = {"identity": dependency, "artifact": artifact, "artifact_sha256": sha256(encoded(artifact)).hexdigest()}
    return {"input": json.loads(raw), "input_sha256": sha256(raw).hexdigest(), "upstream": adopted,
            "task": (workspace / "TASK.md").read_text(),
            "instruction": "Use write_output to submit output.json. Host validation and canonical completion follow separately."}


@worker_server.tool()
def write_output(output: dict) -> dict:
    """Write only this assignment's output.json; return independent domain-check feedback."""
    workspace, revision = worker_workspace()
    if len(json.dumps(output)) > 16_000:
        raise ValueError("output_too_large")
    demo.write(workspace / "output.json", output)
    try:
        validate_member(workspace.parent.parent, workspace.parent.name, revision)
    except ValueError as exc:
        return {"artifact_checks_passed": False, "reason": str(exc)[:200]}
    return {"artifact_checks_passed": True, "note": "Return validated_progress; the host owns canonical completion."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-lead-root", type=Path)
    parser.add_argument("--worker")
    parser.add_argument("--revision", choices=REVISIONS)
    args = parser.parse_args()
    if args.local_lead_root:
        if args.worker or args.revision:
            parser.error("local lead and cloud member bindings are exclusive")
        path = args.local_lead_root.resolve()
        # The local operator's fixed Cordis command supplies this binding,
        # like the existing collaboration MCP CLI. It is not model input.
        os.environ.update({"LOOPX_RESEARCH_DEMO_ROOT": str(path), "LOOPX_TURN_GOAL_ID": demo.GOAL,
                           "LOOPX_TURN_AGENT_ID": "lead", "LOOPX_TURN_WORKSPACE": str(path / "lead")})
        if not os.environ.get("ARK_API_KEY") or not os.environ.get("DEEPSEEK_API_KEY"):
            raise ValueError("local_team_tool_requires_explicit_provider_environment")
    if args.worker or args.revision:
        if not args.worker or not args.revision:
            parser.error("worker and revision required together")
        worker_identity = (args.worker, args.revision)
        worker_server.run(transport="stdio")
    else:
        server.run(transport="stdio")
