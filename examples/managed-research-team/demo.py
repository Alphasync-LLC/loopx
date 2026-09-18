#!/usr/bin/env python3
"""Prepare and launch one bounded autonomous collaboration; no business phases."""
from __future__ import annotations

import argparse
import importlib.util
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from scenario import WORKERS, REVISIONS, EvidenceRejected, encoded, evidence, task, validate_worker, validate_report

GOAL = "synthetic-managed-research"
HERE = Path(__file__).resolve().parent


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


def cli(root: Path, *args: str, workspace: Path | None = None, timeout: int = 60) -> dict:
    completed = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--registry", str(root / "registry.json"),
         "--runtime-root", str(root / "runtime"), "--format", "json", *args],
        cwd=workspace or root, capture_output=True, text=True, timeout=timeout,
    )
    try:
        result = json.loads(completed.stdout)
    except ValueError as exc:
        raise RuntimeError("loopx_cli_failed_without_json") from exc
    if completed.returncode and "turn" not in args:
        raise RuntimeError("loopx_command_rejected:" + str(result.get("error", "unknown"))[:200])
    return result


def prepare(root: Path) -> None:
    if root.exists():
        raise ValueError("use_a_new_disposable_directory")
    project = root / "project"
    project.mkdir(parents=True)
    (project / ".gitignore").write_text(".local/\nACTIVE_GOAL_STATE.md\n")
    (project / "README.md").write_text("Disposable synthetic research team.\n")
    (project / "ACTIVE_GOAL_STATE.md").write_text(
        "---\nstatus: active\n---\n# Synthetic research\n\n## User Todo\n\n## Agent Todo\n\n## Next Action\n\n- Validate synthetic evidence.\n"
    )
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(project), "-c", "user.name=Demo",
                        "-c", "user.email=demo@example.invalid", *args], check=True, capture_output=True)
    git("init", "-b", "main")
    git("add", ".gitignore", "README.md")
    git("commit", "-s", "-m", "Initialize disposable fixture")
    git("remote", "add", "origin", "https://example.invalid/synthetic/research.git")
    git("worktree", "add", "-b", "lead", str(root / "lead"))
    for worker in WORKERS:
        for revision in REVISIONS:
            workspace = root / worker / revision
            git("worktree", "add", "-b", worker + "-" + revision, str(workspace))
            (workspace / "input.json").write_bytes(encoded(evidence(revision)))
    write(root / "registry.json", {
        "schema_version": 1, "common_runtime_root": str(root / "runtime"),
        "goals": [{"id": GOAL, "domain": "synthetic-research", "status": "active", "repo": str(project),
                   "state_file": "ACTIVE_GOAL_STATE.md", "adapter": {"kind": "fixture_v0", "status": "connected-delivery"},
                   "quota": {"compute": 10.0, "window_hours": 24},
                   "coordination": {"agent_model": "peer_v1", "registered_agents": ["lead", *WORKERS], "write_scope": ["**"]}}],
    })


def assign(root: Path, actor: str, text: str) -> None:
    rows = cli(root, "todo", "list", "--goal-id", GOAL).get("todos", [])
    own = next((row for row in rows if row.get("claimed_by") == actor and row.get("status") == "open"), None)
    if own:
        cli(root, "todo", "update", "--goal-id", GOAL, "--todo-id", own["todo_id"], "--agent-id", actor, "--text", text)
    else:
        cli(root, "todo", "add", "--goal-id", GOAL, "--role", "agent", "--claimed-by", actor, "--text", text, "--action-kind", "implement")


def turn(root: Path, actor: str, workspace: Path, validator: list[str], host_args: list[str], timeout: int) -> dict:
    return cli(root, "turn", "run-once", "--goal-id", GOAL, "--agent-id", actor,
               "--turn-instance-id", actor + "-" + uuid.uuid4().hex,
               "--execution-mode", "isolated-headless", "--project", str(workspace),
               "--validation-command-json", json.dumps(validator), "--validation-failure-kind", "repair_required",
               "--scan-root", str(workspace), "--no-global-sync", "--timeout-seconds", str(timeout),
               *host_args, "--execute", workspace=workspace, timeout=timeout + 60)


def delegate(root: Path, worker: str, revision: str, question: str) -> dict:
    if worker not in WORKERS or revision not in REVISIONS or not question or len(question) > 1500:
        raise ValueError("invalid_assignment")
    accepted = root / "accepted" / (worker + "-" + revision + ".json")
    workspace = root / worker / revision
    if accepted.exists():
        entry = json.loads(accepted.read_text())
        if entry["evidence"] != validate_worker(workspace, revision):
            raise ValueError("accepted_artifact_changed")
        return entry
    attempts = root / "attempts" / (worker + "-" + revision + ".json")
    count = json.loads(attempts.read_text())["count"] if attempts.exists() else 0
    if count >= 2:
        raise ValueError("worker_attempt_budget_exhausted")
    write(attempts, {"count": count + 1})
    (workspace / "TASK.md").write_text(task(revision, question))
    assign(root, worker, "Read TASK.md. Produce independently checked output.json for " + revision + ".")
    settings = json.loads((root / "settings.json").read_text())
    result = turn(root, worker, workspace,
                  [sys.executable, str(HERE / "demo.py"), "validate-worker", str(workspace), "--revision", revision],
                  ["--host", "dsh", "--dsh-model", settings["dsh_model"], "--dsh-reasoning-effort", "high",
                   "--dsh-home", str(root / "homes" / (worker + "-" + revision + "-" + str(count)))], 240)
    summary = {key: result.get(key) for key in ("status", "result_kind", "validation", "resume_turn_key", "error")}
    write(root / "turns" / (worker + "-" + revision + "-" + str(count) + ".json"), summary)
    if result.get("status") != "committed" or result.get("result_kind") != "validated_progress":
        reason = "independent_turn_rejected"
        if result.get("result_kind") == "validation_failed":
            try:
                validate_worker(workspace, revision)
            except EvidenceRejected as exc:
                reason = str(exc)
            except ValueError:
                reason = "invalid_worker_json"
            except OSError:
                reason = "worker_output_missing"
        elif result.get("status") == "unavailable":
            reason = "worker_runtime_unavailable"
        return {"worker": worker, "revision": revision, "accepted": False, "reason": reason}
    output = validate_worker(workspace, revision)
    entry = {"worker": worker, "revision": revision, "accepted": True, "turn_status": "committed",
             "evidence": output, "artifact_sha256": sha256(encoded(output)).hexdigest()}
    write(accepted, entry)
    return entry


def launch(root: Path, model: str, environment_id: str, dsh_model: str) -> dict:
    if importlib.util.find_spec("deepseek_harness") is None:
        raise ValueError("install_loopx_deepseek_harness_extra_in_this_interpreter")
    if not os.environ.get("ARK_API_KEY") or not os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("ARK_API_KEY_and_DEEPSEEK_API_KEY_required")
    prepare(root)
    write(root / "settings.json", {"dsh_model": dsh_model})
    os.environ["LOOPX_RESEARCH_DEMO_ROOT"] = str(root)
    assign(root, "lead", "Read the assignment with read_assignment. Organize the two registered local workers to "
           "independently analyze both synthetic filing revisions. Decide delegation questions and order yourself. "
           "Review their accepted results, resolve differences, then write_report with evidence hashes. "
           "Do not claim growth from incomparable periods or count a repost as independent. "
           "Only return validated_progress after write_report confirms independent acceptance.")
    command = [sys.executable, "-m", "loopx_ark_turn.cli", "--model", model, "--environment-id", environment_id,
               "--workspace", str(root / "lead"), "--state-dir", str(root / "provider-receipts"),
               "--timeout-seconds", "1100", "--tool-timeout-seconds", "300", "--max-tool-calls", "16",
               "--mcp-command-json", json.dumps([sys.executable, str(HERE / "server.py")]),
               "--mcp-env", "LOOPX_RESEARCH_DEMO_ROOT", "--mcp-env", "DEEPSEEK_API_KEY",
               "--tool", "read_assignment", "--tool", "delegate", "--tool", "write_report"]
    result = turn(root, "lead", root / "lead", [sys.executable, str(HERE / "demo.py"), "validate-report", str(root)],
                  ["--host", "generic-cli", "--iteration-context", "fresh", "--host-command-json", json.dumps(command)], 1200)
    summary = {key: result.get(key) for key in ("status", "result_kind", "validation", "resume_turn_key", "error", "host_failure")}
    write(root / "lead-turn.json", summary)
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["run", "validate-worker", "validate-report"])
    p.add_argument("root", type=Path)
    p.add_argument("--revision", choices=REVISIONS)
    p.add_argument("--model", default=os.environ.get("ARK_MODEL_ID"))
    p.add_argument("--environment-id", default=os.environ.get("ARK_ENVIRONMENT_ID"))
    p.add_argument("--dsh-model", default="deepseek-v4-flash")
    args = p.parse_args()
    if args.command == "run":
        if not args.model or not args.environment_id:
            p.error("explicit model and existing environment required")
        result = launch(args.root.resolve(), args.model, args.environment_id, args.dsh_model)
        print(json.dumps(result))
        if result.get("status") != "committed" or result.get("result_kind") != "validated_progress":
            raise SystemExit(1)
    elif args.command == "validate-worker":
        validate_worker(args.root, args.revision)
        print("Independent worker acceptance passed")
    else:
        validate_report(args.root)
        print("Independent collaboration acceptance passed")


if __name__ == "__main__":
    main()
