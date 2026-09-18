"""Trusted demo-only composition of canonical Todo + Turn; not a fleet service."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

import demo
from scenario import WORKERS, REVISIONS, evidence, validate_report

server = FastMCP("synthetic-research-team")
lock = asyncio.Lock()


def root() -> Path:
    path = Path(os.environ["LOOPX_RESEARCH_DEMO_ROOT"]).resolve()
    if (os.environ.get("LOOPX_TURN_GOAL_ID") != demo.GOAL or os.environ.get("LOOPX_TURN_AGENT_ID") != "lead"
            or Path(os.environ["LOOPX_TURN_WORKSPACE"]).resolve() != path / "lead"):
        raise ValueError("demo_caller_not_bound")
    return path


@server.tool()
def read_assignment() -> dict:
    """Read synthetic inputs, authorized roster and independently checked report contract."""
    root()
    return {"workers": list(WORKERS), "inputs": [evidence(revision) for revision in REVISIONS],
            "objective": "Compare the initial and corrected evidence. Obtain an independently accepted result "
                         "from each worker for each revision. You choose questions/order; revise rejected work. "
                         "Use all four accepted artifacts in the report. Count source families corroborating "
                         "CURRENT-period figures only, excluding historical comparison material. No trades or external information.",
            "report_fields": {"initial_normalized_fcf": "integer", "corrected_normalized_fcf": "integer",
                              "revision_delta": "corrected minus initial", "growth_supported": "boolean",
                              "independent_source_families": "integer", "repost_stale_after_correction": "boolean",
                              "dependencies": {"worker/revision": "artifact_sha256 returned by delegate"}, "reason": "short explanation"}}


@server.tool()
async def delegate(worker: str, revision: str, question: str) -> dict:
    """Assign a question to one registered dsh worker; return only independently accepted evidence or rejection.

    Allowed workers: analyst, reviewer. Revisions: initial, corrected. Two attempts per pair.
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
        validate_report(path)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {"accepted": False, "reason": type(exc).__name__ + ":report_or_dependencies_rejected"}
    return {"accepted": True, "note": "Outer Turn independently revalidates before canonical writeback."}


if __name__ == "__main__":
    server.run(transport="stdio")
