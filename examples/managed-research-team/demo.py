#!/usr/bin/env python3
"""Prepare and launch one bounded autonomous collaboration; no business phases."""
from __future__ import annotations

import argparse
import importlib.util
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from scenario import REVISIONS, EvidenceRejected, assignments, roster, encoded, evidence, task, validate_worker
from acceptance import GOAL, canonical_tasks, require_completed, todo_id, validate_delivery, validate_member
from execution import host_arguments

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
        raise RuntimeError("loopx_command_rejected:" + str(result.get("reason_code", "")) + ":" +
                           str(result.get("error", result.get("reason", "unknown")))[:200])
    return result


def prepare(root: Path, provider: str = "file", topology: str = "cloud-led") -> None:
    if root.exists():
        raise ValueError("use_a_new_disposable_directory")
    project = root / "project"
    project.mkdir(parents=True)
    members = roster(topology)
    write(project / "team.json", members)
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
    for member in members:
        worker, revision = member["worker"], member["revision"]
        workspace = root / worker / revision
        git("worktree", "add", "-b", worker + "-" + revision, str(workspace))
        (workspace / "input.json").write_bytes(encoded(evidence(revision)))
    write(root / "registry.json", {
        "schema_version": 1, "common_runtime_root": str(root / "runtime"),
        "goals": [{"id": GOAL, "domain": "synthetic-research", "status": "active", "repo": str(project),
                   "state_file": "ACTIVE_GOAL_STATE.md", "adapter": {"kind": "fixture_v0", "status": "connected-delivery"},
                   "quota": {"compute": 10.0, "window_hours": 24},
                   "coordination": {"agent_model": "peer_v1", "registered_agents": ["lead", *sorted({row["worker"] for row in members})], "write_scope": ["**"]}}],
    })
    validation = project / "validation"
    validation.mkdir()
    for name in ("scenario.py", "acceptance.py"):
        shutil.copyfile(HERE / name, validation / name)
    pins = [{"path": "validation/" + name, "sha256": sha256((validation / name).read_bytes()).hexdigest()}
            for name in ("scenario.py", "acceptance.py")]
    pins.append({"path": "team.json", "sha256": sha256((project / "team.json").read_bytes()).hexdigest()})
    pairs = [(row["worker"], row["revision"]) for row in members] + [("lead", "report")]
    tasks, criteria, bindings = [], [], []
    for actor, revision in pairs:
        identity = todo_id(actor, revision)
        text = (
            "Use the research_team MCP tools. Read the assignment with read_assignment. Organize the registered "
            "members to analyze their authorized synthetic filing revisions. Decide delegation questions and order yourself. Review their "
            "accepted results, resolve differences, then write_report with all four evidence hashes. "
            "Only return validated_progress after write_report confirms independent checks."
            if actor == "lead" else
            "Read TASK.md locally, or use read_input/write_output when running remotely. Produce independently checked output.json for " + revision + "."
        )
        tasks.append({"todo_id": identity, "text": text, "claimed_by": actor})
        criteria.append({"id": actor + "-" + revision, "description": "Independent checks for " + actor + " " + revision,
                         "validation_argv": [sys.executable, "validation/acceptance.py", str(root),
                                             *(["report"] if actor == "lead" else [actor, revision])],
                         "validation_timeout_seconds": 5, "validation_files": pins})
        bindings.append({"todo_id": identity, "criterion_ids": [actor + "-" + revision]})
    write(root / "bootstrap.json", {"tasks": tasks, "document": {
        "objective": "Deliver a revision-aware synthetic research report with four completed dependencies",
        "non_goals": ["Trading", "External research", "Owner approval of the whole Goal"],
        "criteria": criteria, "bindings": bindings,
    }})
    initialized = subprocess.run(
        ["node", "--no-warnings", "--experimental-sqlite", "--experimental-strip-types",
         str(HERE / "bootstrap.ts"), str(root), provider],
        capture_output=True, text=True, timeout=45,
    )
    if initialized.returncode:
        raise RuntimeError("disposable_canonical_initialization_failed:" + initialized.stderr[-1000:])
    write(root / "owner-acceptance.json", json.loads(initialized.stdout))


def complete(root: Path, actor: str, revision: str) -> dict:
    result = cli(root, "todo", "complete", "--goal-id", GOAL, "--agent-id", actor,
                 "--todo-id", todo_id(actor, revision), "--no-follow-up",
                 "--note", "Bounded artifact task; synthesis consumes dependencies through its separately bound task.",
                 workspace=root / "project")
    require_completed(canonical_tasks(root), actor, revision)
    return result


def turn(root: Path, actor: str, revision: str, workspace: Path, validator: list[str], host_args: list[str], timeout: int) -> dict:
    return cli(root, "turn", "run-once", "--goal-id", GOAL, "--agent-id", actor,
               "--todo-id", todo_id(actor, revision),
               "--turn-instance-id", actor + "-" + uuid.uuid4().hex,
               "--execution-mode", "isolated-headless", "--project", str(workspace),
               "--validation-command-json", json.dumps(validator), "--validation-failure-kind", "repair_required",
               "--scan-root", str(workspace), "--no-global-sync", "--timeout-seconds", str(timeout),
               *host_args, "--execute", workspace=workspace, timeout=timeout + 60)


def delegate(root: Path, worker: str, revision: str, question: str) -> dict:
    member = next((row for row in assignments(root) if row["worker"] == worker and row["revision"] == revision), None)
    if member is None or not question or len(question) > 1500:
        raise ValueError("invalid_assignment")
    accepted = root / "accepted" / (worker + "-" + revision + ".json")
    workspace = root / worker / revision
    rows = canonical_tasks(root)
    if member.get("upstream"):
        previous_actor, previous_revision = member["upstream"].split("/")
        try:
            require_completed(rows, previous_actor, previous_revision)
        except ValueError:
            return {"accepted": False, "reason": "complete_dependency_first:" + member["upstream"]}
    if rows[todo_id(worker, revision)]["done"]:
        require_completed(rows, worker, revision)
        output = validate_member(root, worker, revision)
        return accepted_entry(worker, revision, output)
    attempts = root / "attempts" / (worker + "-" + revision + ".json")
    count = json.loads(attempts.read_text())["count"] if attempts.exists() else 0
    if count >= 2:
        raise ValueError("worker_attempt_budget_exhausted")
    write(attempts, {"count": count + 1})
    (workspace / "TASK.md").write_text(task(revision, question))
    if member.get("upstream"):
        with (workspace / "TASK.md").open("a") as prompt:
            prompt.write("\nUse read_input to obtain the accepted upstream artifact. Independently verify it against the filing. "
                         "Include adopted_dependencies mapping its worker/revision identity to its exact artifact_sha256.\n")
    result = turn(root, worker, revision, workspace,
                  [sys.executable, str(HERE / "demo.py"), "validate-worker", str(workspace), "--revision", revision],
                  host_arguments(root, worker, revision, host=member["host"], attempt=count), 240)
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
    output = validate_member(root, worker, revision)
    try:
        complete(root, worker, revision)
    except (RuntimeError, ValueError) as exc:
        return {"worker": worker, "revision": revision, "accepted": False, "reason": str(exc)[:300]}
    entry = accepted_entry(worker, revision, output)
    write(accepted, entry)
    return entry


def accepted_entry(worker: str, revision: str, output: dict) -> dict:
    return {"worker": worker, "revision": revision, "accepted": True,
            "todo_id": todo_id(worker, revision), "todo_status": "done",
            "evidence": output, "artifact_sha256": sha256(encoded(output)).hexdigest()}


def launch(root: Path, model: str, environment_id: str, dsh_model: str, topology: str = "local-led") -> dict:
    if importlib.util.find_spec("deepseek_harness") is None:
        raise ValueError("install_loopx_deepseek_harness_extra_in_this_interpreter")
    if not os.environ.get("ARK_API_KEY") or not os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("ARK_API_KEY_and_DEEPSEEK_API_KEY_required")
    prepare(root, topology=topology)
    write(root / "settings.json", {"dsh_model": dsh_model, "ark_model": model, "environment_id": environment_id})
    os.environ["LOOPX_RESEARCH_DEMO_ROOT"] = str(root)
    result = turn(root, "lead", "report", root / "lead", [sys.executable, str(HERE / "demo.py"), "validate-report", str(root)],
                  host_arguments(root, "lead", "report", host="dsh" if topology == "local-led" else "ark"), 1200)
    summary = {key: result.get(key) for key in ("status", "result_kind", "validation", "resume_turn_key", "error", "host_failure")}
    write(root / "lead-turn.json", summary)
    if result.get("status") == "committed" and result.get("result_kind") == "validated_progress":
        complete(root, "lead", "report")
        rows = canonical_tasks(root)
        summary["canonical_completed_todos"] = [identity for identity, row in rows.items() if row["done"]]
        summary["goal_status"] = json.loads((root / "registry.json").read_text())["goals"][0]["status"]
        write(root / "completion.json", summary)
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["run", "validate-worker", "validate-report"])
    p.add_argument("root", type=Path)
    p.add_argument("--revision", choices=REVISIONS)
    p.add_argument("--model", default=os.environ.get("ARK_MODEL_ID"))
    p.add_argument("--environment-id", default=os.environ.get("ARK_ENVIRONMENT_ID"))
    p.add_argument("--dsh-model", default="deepseek-v4-flash")
    p.add_argument("--topology", choices=["local-led", "cloud-led"], default="local-led")
    args = p.parse_args()
    if args.command == "run":
        if not args.model or not args.environment_id:
            p.error("explicit model and existing environment required")
        result = launch(args.root.resolve(), args.model, args.environment_id, args.dsh_model, args.topology)
        print(json.dumps(result))
        if result.get("status") != "committed" or result.get("result_kind") != "validated_progress":
            raise SystemExit(1)
    elif args.command == "validate-worker":
        validate_member(args.root.parent.parent, args.root.parent.name, args.revision)
        print("Independent worker acceptance passed")
    else:
        validate_delivery(args.root)
        print("Independent collaboration acceptance passed")


if __name__ == "__main__":
    main()
