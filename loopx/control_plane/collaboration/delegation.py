"""Opt-in local execution of peer requests through existing governed Turns.

The operator binds exact workspaces, tasks and host arguments. Models supply
semantic briefs and stable operation ids, never programs or acceptance rules.
Detached workers survive loss of their requesting MCP conversation. Receipts
are observations, not a second task/lease/acceptance authority.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import stat
from pathlib import Path
import subprocess
import sys
import time

from ...file_lock import exclusive_file_lock, LockAcquisitionPolicy, LockAcquireTimeoutError
from ...todos import list_goal_todos
from ..effect_runtime import effect_runtime_result, EffectRuntimeRemoteError
from ..goals.acceptance import inspect_goal_acceptance, validate_goal_task_acceptance
from ..turn_driver.journal_store import turn_journal_path
from .inbox import _hash, _read, _write, _root, _receipt, _entry
from .peers import _goal, request, return_result


class Delegations:
    def __init__(self, root: Path, registry: Path, goal_id: str, agent_id: str, config: Path):
        self.root, self.registry = root.resolve(), registry.resolve()
        self.goal_id, self.agent_id, self.config = goal_id, agent_id, config.resolve()

    def binding(self, binding_id: str, *, require_active: bool = False) -> dict:
        _goal(self.registry, self.goal_id, self.agent_id, require_active=require_active)
        binding = effect_runtime_result("collaboration.delegation.binding", {
            "config": _read(self.config), "binding_id": binding_id, "agent_id": self.agent_id,
        })
        _goal(self.registry, self.goal_id, binding["agent_id"], require_active=require_active)
        if not Path(binding["workspace"]).is_absolute():
            raise ValueError("delegation workspace must be absolute")
        return binding

    def directory(self) -> dict:
        config = _read(self.config)
        bindings = [self.binding(row["id"]) for row in config["bindings"]
                    if self.agent_id in row.get("requesters", [])]
        return {"bindings": [{key: row[key] for key in ("id", "agent_id", "todo_id")}
                             for row in bindings]}

    def path(self, operation_id: str) -> Path:
        return _root(self.root) / "executions" / _hash([self.goal_id, self.agent_id]) / (_hash(operation_id) + ".json")

    def start(self, binding_id: str, operation_id: str, brief: dict,
              parent_request_id: str | None = None) -> dict:
        binding = self.binding(binding_id, require_active=True)
        delivered = request(self.root, self.registry, self.goal_id, self.agent_id,
                            binding["agent_id"], operation_id, brief, parent_request_id)
        path = self.path(operation_id)
        identity = {"binding": binding, "request_id": delivered["request_id"], "operation_id": operation_id}
        with exclusive_file_lock(path.with_suffix(".dispatch")):
            if path.exists():
                if _read(path)["identity"] != identity:
                    raise ValueError("delegation operation identity conflict")
            else:
                _write(path, {"identity": identity, "status": "prepared", "created_at": time.time()})
                self._spawn(operation_id)
        return self.read(operation_id)

    def _spawn(self, operation_id: str) -> None:
        # No inherited stdio pipes: closing the conversation cannot cancel or
        # hang this bounded execution. The worker owns a kernel single-flight lock.
        subprocess.Popen([
            sys.executable, "-m", "loopx.control_plane.collaboration.delegation", "worker", "--runtime-root", str(self.root),
            "--registry", str(self.registry), "--goal-id", self.goal_id,
            "--agent-id", self.agent_id, "--config", str(self.config), "--operation-id", operation_id,
        ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True)

    def resume(self, operation_id: str) -> dict:
        row = _read(self.path(operation_id))
        self._bound(row)
        if row["status"] not in {"accepted", "rejected"}:
            self.binding(row["identity"]["binding"]["id"], require_active=True)
            self._spawn(operation_id)
        return self.read(operation_id)

    def _bound(self, row: dict, *, require_active: bool = False) -> dict:
        binding = self.binding(row["identity"]["binding"]["id"], require_active=require_active)
        if row["identity"]["binding"] != binding:
            raise ValueError("delegation binding changed; reconcile original execution")
        return binding

    def read(self, operation_id: str) -> dict:
        path = self.path(operation_id)
        if not path.exists():
            raise ValueError("unknown delegation operation; start_delegation returns the operation_id to read")
        row = _read(path)
        binding = self._bound(row)
        active = False
        try:
            with exclusive_file_lock(path, policy=LockAcquisitionPolicy.SINGLE_FLIGHT):
                pass
        except LockAcquireTimeoutError:
            active = True
        result = {"operation_id": operation_id, "request_id": row["identity"]["request_id"],
                  "agent_id": binding["agent_id"], "todo_id": binding["todo_id"],
                  "status": row["status"], "worker_active": active,
                  "recovery_required": not active and row["status"] not in {"accepted", "rejected"}
                  and time.time() - row.get("created_at", 0) > 15}
        if row["status"] == "accepted":
            # A saved receipt cannot hide an amended task, verifier or output.
            artifacts = self._accepted(binding)
            if artifacts != row["artifacts"]:
                raise ValueError("delegation output changed after completion")
            result["artifacts"] = artifacts
        if row.get("error"):
            result["error"] = row["error"]
        return result

    def _observe(self, path: Path, row: dict, status: str, **facts) -> None:
        decision = effect_runtime_result("collaboration.delegation.observe", {
            "from": row["status"], "to": status, **facts,
        })
        row.update(status=decision["status"])
        _write(path, row)

    def _cli(self, binding: dict, *args: str, timeout: int = 60) -> dict:
        completed = subprocess.run([
            sys.executable, "-m", "loopx.cli", "--registry", str(self.registry),
            "--runtime-root", str(self.root), "--format", "json", *args,
        ], cwd=binding["workspace"], capture_output=True, text=True, timeout=timeout)
        try:
            value = json.loads(completed.stdout)
        except ValueError as exc:
            raise ValueError("delegation CLI returned no structured result") from exc
        if completed.returncode and "turn" not in args:
            raise ValueError("delegation canonical command rejected")
        return value

    def _validate(self, binding: dict) -> None:
        value = validate_goal_task_acceptance(registry_path=self.registry, runtime_root=str(self.root),
            goal_id=self.goal_id, agent_id=binding["agent_id"], todo_id=binding["todo_id"])
        if not value["passed"]:
            raise ValueError("delegation task acceptance rejected")

    def _accepted(self, binding: dict) -> list[dict]:
        self._validate(binding)
        todos = list_goal_todos(registry_path=self.registry, goal_id=self.goal_id, runtime_root_arg=str(self.root))
        basis = inspect_goal_acceptance(registry_path=self.registry, goal_id=self.goal_id, runtime_root=str(self.root))
        if todos.get("authority_read", {}).get("provider_revision") != basis.get("provider_revision"):
            raise ValueError("delegation canonical snapshot changed; retry readback")
        todo = next((row for row in todos["todos"] if row["todo_id"] == binding["todo_id"]), {})
        guard = next((row for row in basis["goal_acceptance_contract"]["tasks"]
                      if row["todo_id"] == binding["todo_id"]), {})
        if not todo.get("done") or todo.get("status") != "done" or guard.get("state") != "ready":
            raise ValueError("delegation requires current canonical completion")
        workspace = Path(binding["workspace"]).resolve()
        artifacts = []
        for ref in binding["output_refs"]:
            path = workspace / ref
            if not path.resolve().is_relative_to(workspace) or path.is_symlink() or not path.is_file():
                raise ValueError("delegation artifact unavailable or outside workspace")
            if path.stat().st_size > 128_000:
                raise ValueError("delegation artifact exceeds bounded return size")
            with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)), "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError("delegation artifact must be a regular file")
                content = stream.read(128_001)
            if len(content) > 128_000:
                raise ValueError("delegation artifact exceeds bounded return size")
            artifacts.append({"ref": ref, "sha256": hashlib.sha256(content).hexdigest(),
                              "text": content.decode("utf-8")})
        if len(json.dumps(artifacts).encode()) > 64_000:
            raise ValueError("delegation aggregate return exceeds limit")
        return artifacts

    def execute(self, operation_id: str) -> None:
        path = self.path(operation_id)
        with exclusive_file_lock(path, policy=LockAcquisitionPolicy.SINGLE_FLIGHT):
            row = _read(path)
            if row["status"] in {"accepted", "rejected"}:
                return
            binding = self._bound(row, require_active=True)
            row.pop("error", None)
            _write(path, row)
            # Different request ids cannot run the same assigned task concurrently.
            task_lock = _root(self.root) / "execution-slots" / _hash([self.goal_id, binding["todo_id"]])
            with exclusive_file_lock(task_lock, policy=LockAcquisitionPolicy.SINGLE_FLIGHT):
                try:
                    self._execute(path, row, binding)
                except (ValueError, KeyError, subprocess.TimeoutExpired, EffectRuntimeRemoteError) as exc:
                    row["error"] = str(exc)[:180] if isinstance(exc, (ValueError, EffectRuntimeRemoteError)) else type(exc).__name__
                    _write(path, row)
                    if row["status"] == "prepared":
                        self._observe(path, row, "rejected")

    def _execute(self, path: Path, row: dict, binding: dict) -> None:
        request_id = row["identity"]["request_id"]
        common = ["--goal-id", self.goal_id, "--agent-id", binding["agent_id"]]
        host = binding["host_args"]
        validator = [sys.executable, "-m", "loopx.control_plane.collaboration.delegation", "validate", "--runtime-root", str(self.root),
                     "--registry", str(self.registry), "--goal-id", self.goal_id,
                     "--agent-id", self.agent_id, "--config", str(self.config),
                     "--operation-id", row["identity"]["operation_id"]]
        execution = ["--execution-mode", "isolated-headless", "--project", binding["workspace"],
                     "--scan-root", binding["workspace"], "--no-global-sync",
                     "--timeout-seconds", str(binding["timeout_seconds"]),
                     "--validation-command-json", json.dumps(validator),
                     "--validation-failure-kind", "repair_required", *host]
        if row["status"] == "prepared":
            _write(Path(binding["workspace"]) / "DELEGATION.json", {
                "request_id": request_id, "brief": _entry(self.root, self.goal_id, binding["agent_id"], request_id)["brief"],
                "instruction": "Read context and assess this request independently before working. Return results through the bound tools.",
            })
            plan = self._cli(binding, "turn", "plan", *common, "--todo-id", binding["todo_id"],
                             "--turn-instance-id", "delegation-" + request_id[:32],
                             "--execution-mode", "isolated-headless", "--scan-root", binding["workspace"],
                             "--host", host[host.index("--host") + 1],
                             "--iteration-context", host[host.index("--iteration-context") + 1] if "--iteration-context" in host else "resume-if-available",
                             "--include-transaction-detail")
            row["turn_key"] = plan["transaction"]["turn_key"]
            self._observe(path, row, "running")
        try:
            if row["status"] == "running":
                journal = turn_journal_path(self.root, goal_id=self.goal_id, turn_key=row["turn_key"])
                selector = (["--resume-turn-key", row["turn_key"]] if journal.exists() else
                            ["--todo-id", binding["todo_id"], "--turn-instance-id", "delegation-" + request_id[:32]])
                result = self._cli(binding, "turn", "run-once", *common, *selector, *execution,
                                   "--execute", timeout=binding["timeout_seconds"] + 60)
                row["turn_result"] = {key: result.get(key) for key in ("status", "result_kind", "resume_turn_key", "reason", "host_failure", "error")}
                self._observe(path, row, "turn_returned")
            result = row["turn_result"]
            if result.get("status") != "committed" or result.get("result_kind") != "validated_progress":
                self._observe(path, row, "rejected")
                raise ValueError("delegation Turn rejected; inspect the original Turn before retrying")
            decision, error = _receipt(self.root, "decisions", _entry(self.root, self.goal_id, binding["agent_id"], request_id))
            if error or not decision or decision["decision"] != "adopt":
                self._observe(path, row, "rejected")
                raise ValueError("delegation receiver did not adopt the request")
            self._bound(row, require_active=True)  # revocation or rebinding while the model ran
            self._cli(binding, "todo", "complete", *common, "--todo-id", binding["todo_id"],
                      "--no-follow-up", "--note", "Bounded delegated work; requester owns synthesis.")
            row["artifacts"] = self._accepted(binding)
            if not (_root(self.root) / "replies" / request_id / "conclusion.json").exists():
                return_result(self.root, self.goal_id, binding["agent_id"], request_id,
                              json.dumps({"todo_id": binding["todo_id"], "status": "accepted",
                                          "artifacts": [{k: v for k, v in item.items() if k != "text"} for item in row["artifacts"]]}))
            self._observe(path, row, "accepted", canonical_done=True, acceptance_ready=True, artifacts_current=True)
        except (ValueError, KeyError, subprocess.TimeoutExpired, EffectRuntimeRemoteError) as exc:
            # Retain uncertain execution for explicit same-operation recovery.
            # No fresh Turn is ever created because its client timed out.
            row["error"] = str(exc)[:180] if isinstance(exc, (ValueError, EffectRuntimeRemoteError)) else type(exc).__name__
            _write(path, row)


def register_tools(server, delegations: Delegations) -> None:
    @server.tool()
    def list_execution_bindings() -> dict:
        """Read operator-authorized peer task bindings; registration alone cannot launch."""
        return delegations.directory()

    @server.tool()
    def start_delegation(binding_id: str, operation_id: str, brief: dict,
                         parent_request_id: str | None = None) -> dict:
        """Start one bounded peer Turn. Reuse the same operation id after lost replies.

        Supply brief with schema_version="collaboration_brief_v0", purpose, context,
        constraints (strings), inputs (relative ref/description/optional sha256),
        acceptance (strings), return_requirement. Work continues independently of this MCP
        conversation. Read its durable operation later; do not repeat timed-out work.
        """
        return delegations.start(binding_id, operation_id, brief, parent_request_id)

    @server.tool()
    def read_delegation(operation_id: str) -> dict:
        """Read current work/result by original id; accepted requires canonical readback."""
        return delegations.read(operation_id)

    @server.tool()
    async def wait_delegation(operation_id: str) -> dict:
        """Wait at most 15 seconds for an original operation; returning running is normal."""
        for _ in range(5):
            result = await asyncio.to_thread(delegations.read, operation_id)
            if result["status"] in {"accepted", "rejected"} or result["recovery_required"]:
                return result
            await asyncio.sleep(3)
        return result

    @server.tool()
    def resume_delegation(operation_id: str) -> dict:
        """Reconnect an interrupted original execution; never launch a replacement Turn."""
        return delegations.resume(operation_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["worker", "validate"])
    for name in ("runtime-root", "registry", "config"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("goal-id", "agent-id", "operation-id"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    service = Delegations(args.runtime_root, args.registry, args.goal_id, args.agent_id, args.config)
    if args.action == "validate":
        service._validate(service._bound(_read(service.path(args.operation_id))))
    else:
        try:
            service.execute(args.operation_id)
        except LockAcquireTimeoutError:
            pass  # the original worker retains responsibility


if __name__ == "__main__":
    main()
