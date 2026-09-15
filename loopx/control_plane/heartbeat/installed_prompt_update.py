"""Update-time discovery and conservative adoption of installed host prompts.

Only a byte-exact generated prompt may opt into unattended replacement. Names,
Goal ids and prose heuristics can suggest review, never authorize replacement.
The App remains the preferred writer while running.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
from typing import Any

from .automation_upgrade import (
    SCHEMA,
    _atomic,
    apply_offline,
    automation_update_request,
    bootstrap_binding,
    build_plan,
    digest,
)
from .bootstrap_prompt import host_bootstrap_binding

PENDING_SCHEMA_VERSION = "loopx_automation_prompt_adoption_pending_v0"
PENDING_HOST_ACTION = "adopt_managed_bootstrap"
PENDING_HOST_ACTION_CONTRACT = "codex_app_automation_prompt_adoption"
PENDING_SPEND_POLICY = "no_spend_for_automation_prompt_adoption"
PENDING_STORE_FILENAME = "app-automation-prompt-adoptions.json"


def pending_store_path(runtime_root: str | Path) -> Path:
    return Path(runtime_root).expanduser().resolve() / PENDING_STORE_FILENAME


def _read_pending_store(runtime_root: str | Path) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(pending_store_path(runtime_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, dict):
        return {}
    return {str(key): dict(value) for key, value in entries.items() if isinstance(value, dict)}


def update_pending_adoptions(*, runtime_root: str | Path, codex_home: str,
                             pending: list[dict[str, Any]], resolved: list[str]) -> Path | None:
    """Replace the adoptions this reconciliation left pending, per automation.

    The store records an update-time observation, never adoption authority: it
    only names entries this run already reviewed, so a later turn can apply the
    reviewed prompt-only request instead of re-classifying the host store.
    One runtime root can front several Codex homes, so only this home's records
    are resolved; another home's pending obligations are left alone.
    """
    path = pending_store_path(runtime_root)
    entries = _read_pending_store(runtime_root)
    for automation_id in resolved:
        if str(entries.get(automation_id, {}).get("codex_home") or "") == codex_home:
            entries.pop(automation_id, None)
    for record in pending:
        entries[str(record["automation_id"])] = record
    if not entries:
        if path.is_file():
            path.unlink()
        return None
    _atomic(path, json.dumps({"schema_version": PENDING_SCHEMA_VERSION, "entries": entries},
        ensure_ascii=False, indent=2) + "\n")
    return path


def load_pending_adoption(*, runtime_root: str | Path | None, goal_id: str,
                          agent_id: str | None) -> dict[str, Any] | None:
    """Project this lane's recorded adoption, or None once the host already applied it.

    The record was reviewed at update time; this read only checks that its
    expected body is still not installed, so a satisfied obligation stops
    projecting itself without re-classifying any lane.
    """
    if not runtime_root or not agent_id:
        return None
    records = [record for record in _read_pending_store(runtime_root).values()
               if record.get("goal_id") == goal_id and record.get("agent_id") == agent_id]
    if len(records) != 1:
        # No record, or several lanes sharing one identifier, is not a lane
        # obligation this turn may act on.
        return None
    record = records[0]
    request = record.get("api_update_request")
    if not isinstance(request, dict) or not record.get("desired_sha256"):
        return None
    if _installed_prompt_matches_digest(record):
        return None
    return {"schema_version": PENDING_SCHEMA_VERSION, "status": "adoption_required",
        "goal_id": goal_id, "agent_id": agent_id,
        "automation_id": str(record.get("automation_id") or ""),
        "automation_status": record.get("automation_status"),
        "host_action": PENDING_HOST_ACTION, "host_action_contract": PENDING_HOST_ACTION_CONTRACT,
        "spend_policy": PENDING_SPEND_POLICY,
        "expected_prompt_sha256": record.get("expected_prompt_sha256"),
        "desired_sha256": record.get("desired_sha256"),
        "source": record.get("source"), "recorded_at": record.get("recorded_at"),
        "reason": "the installed automation body is not the current managed loader; "
            "review this prompt-only request through the App",
        "api_update_request": request}


def _installed_prompt_matches_digest(record: dict[str, Any]) -> bool:
    """True only when this exact automation now carries the desired body."""
    codex_home = str(record.get("codex_home") or "").strip()
    automation_id = str(record.get("automation_id") or "")
    if not codex_home or not automation_id:
        return False
    try:
        manifest = tomllib.loads((Path(codex_home) / "automations" / automation_id
            / "automation.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return False
    return digest(str(manifest.get("prompt") or "")) == record.get("desired_sha256")


def require_closed_app() -> None:
    if sys.platform != "darwin":
        raise ValueError("offline adapter is qualified only on macOS; use the App automation API")
    for name in ("Codex", "ChatGPT"):
        observed = subprocess.run(["/usr/bin/pgrep", "-x", name], capture_output=True, check=False)
        if observed.returncode != 1:
            raise ValueError("close the Codex/ChatGPT App before offline migration; otherwise use automation_update")


def _owned(entry: dict, registry: Path, runtime_root: str | None, cli_bin: str) -> bool:
    prompt = entry.get("current_prompt", "")
    binding = bootstrap_binding(prompt) or host_bootstrap_binding(prompt)
    if binding is not None:
        # Never retarget a canary binary, home, registry or runtime implicitly.
        return (binding["registry"].resolve() == registry.resolve()
                and binding.get("cli_bin", "loopx") == cli_bin
                and binding.get("runtime_root") == runtime_root)
    # Before replacing the installed version, reproduce its uncustomized output.
    # Older/custom bodies which cannot be reproduced remain review-only.
    from loopx.agent_registry import agent_profile_from_registry, registered_agent_ids_from_registry
    from loopx.heartbeat_prompt import build_heartbeat_prompt

    for mode in ("thin", "brief", "compact", "full"):
        try:
            generated = build_heartbeat_prompt(
                goal_id=entry["goal_id"], agent_id=entry["agent_id"],
                registered_agents=registered_agent_ids_from_registry(registry, entry["goal_id"]),
                agent_profile=agent_profile_from_registry(registry, entry["goal_id"], entry["agent_id"]),
                runtime_profile="codex_app_heartbeat", runtime_root=runtime_root,
                cli_bin=cli_bin, **{mode: True},
            )
        except ValueError:
            continue
        if generated.get("ok") and generated.get("task_body") == prompt:
            return True
    return False


def snapshot(*, registry: Path, home: Path, runtime_root: str | None = None,
             cli_bin: str = "loopx") -> dict:
    if not (home / "sqlite/codex-dev.db").is_file():
        return {"ok": True, "status": "not_installed", "entries": []}
    plan = build_plan(registry=registry, home=home, runtime_root=runtime_root, cli_bin=cli_bin)
    for entry in plan["entries"]:
        entry["automatic_eligible"] = (entry["status"] in {"current", "adoption_required"}
            and _owned(entry, registry, runtime_root, cli_bin))
    return plan


def reconcile(*, before: dict, registry: Path, home: Path,
              runtime_root: str | None = None, cli_bin: str = "loopx") -> dict:
    """Re-read after installation; report per-task outcomes without raw prompts."""
    if before.get("status") == "not_installed":
        return {"ok": True, "status": "not_installed", "results": []}
    if before.get("codex_home") != str(home.resolve()):
        raise ValueError("update snapshot belongs to another host home")
    if before.get("schema_version") != SCHEMA:
        raise ValueError("unsupported update snapshot schema")
    current = {entry["automation_id"]: entry for entry in
               build_plan(registry=registry, home=home, runtime_root=runtime_root, cli_bin=cli_bin)["entries"]}
    results = []
    api_updates = []
    pending_records = []
    resolved = []
    recorded_at = datetime.now(timezone.utc).isoformat()
    for old in before["entries"]:
        identifier = old["automation_id"]
        now = current.get(identifier)
        result = {"automation_id": identifier, "status": "review_required"}
        pending_here = False
        if now is None:
            result["status"] = "missing"
        elif now["status"] in {"current", "unmanaged", "blocked"}:
            result["status"] = now["status"]
            if now.get("reason"):
                result["reason"] = now["reason"]
        elif any(old.get(key) != now.get(key) for key in
                 ("source_sha256", "prompt_sha256", "target_thread_id", "goal_id", "agent_id")):
            result["status"] = "changed_since_snapshot"
        elif old.get("automatic_eligible") is True:
            try:
                # The desktop host caches automation rows and can overwrite both
                # mirrors after a direct SQLite update. CAS only fences disk
                # writers; it does not invalidate the host's live scheduler.
                require_closed_app()
                applied = apply_offline(home=home, automation_id=identifier,
                    expected_prompt_sha256=old["prompt_sha256"], desired_prompt=now["desired_prompt"],
                    expected_source_sha256=old["source_sha256"])
                result["status"] = applied["status"]
            except (OSError, ValueError, sqlite3.Error) as error:
                result.update(status="deferred", reason=str(error))
                # The CLI cannot call an in-App tool itself. Give its host a
                # complete prompt-only request, plus a precondition to re-view.
                try:
                    manifest = tomllib.loads((home / "automations" / identifier / "automation.toml").read_text())
                except (OSError, ValueError):
                    manifest = {}
                required = {"name", "status", "rrule", "target_thread_id"}
                if required <= manifest.keys() and manifest.get("prompt") == now["current_prompt"]:
                    request = automation_update_request(automation_id=identifier,
                        manifest=manifest, expected_prompt_sha256=now["prompt_sha256"],
                        desired_prompt=now["desired_prompt"])
                    api_updates.append(request)
                    # A completed report cannot carry the obligation into the
                    # next turn, and nothing else re-observes the installed
                    # body, so record what the host still has to adopt.
                    pending_here = True
                    pending_records.append({"automation_id": identifier,
                        "goal_id": now["goal_id"], "agent_id": now["agent_id"],
                        "automation_status": manifest["status"], "codex_home": str(home),
                        "expected_prompt_sha256": now["prompt_sha256"],
                        "desired_sha256": now["desired_sha256"], "recorded_at": recorded_at,
                        "source": "update_time_reconciliation",
                        "api_update_request": request})
        if not pending_here:
            resolved.append(identifier)
        results.append(result)
    if pending_records or resolved:
        from loopx.control_plane.coordination.local_authority_shadow_adapter import (
            effective_runtime_root,
        )
        update_pending_adoptions(
            runtime_root=effective_runtime_root(registry.resolve(), runtime_root),
            codex_home=str(home),
            pending=pending_records, resolved=resolved)
    pending = any(result["status"] not in {"current", "updated", "unmanaged", "missing"} for result in results)
    return {"ok": not pending, "status": "attention_required" if pending else "current", "results": results,
            "api_updates": api_updates,
            "next_action": "Use automation-prompts plan and the App automation API for pending entries; never rewrite scheduling or thread bindings." if pending else None}


def save_snapshot(path: Path, payload: dict) -> None:
    _atomic(path, json.dumps(payload, ensure_ascii=False))


def update_with_prompts(payload: dict, *, registry: Path, runtime_root: str | None,
                        timeout_seconds: int, runtime_update) -> dict:
    """Capture old-template evidence, then run reconciliation in the NEW runtime.

    Prompt problems are separate from binary installation success. Never report
    the application fully updated merely because its executable was replaced.
    """
    from loopx.upgrade import codex_home

    home = codex_home().expanduser().resolve()
    try:
        before = snapshot(registry=registry, home=home, runtime_root=runtime_root)
    except (ValueError, OSError, sqlite3.Error) as error:
        before = {"ok": False, "status": "discovery_failed", "reason": str(error)}
    updated = runtime_update(payload, timeout_seconds=timeout_seconds)
    # Optional extension qualification is not binary installation readiness.
    # Do not strand managed prompts after a successful install + core doctor,
    # but preserve the failed aggregate result and its original repair action.
    runtime_ready = bool(updated.get("ok"))
    execution = updated.get("execution", {})
    installed = runtime_ready or (updated.get("changes_applied") is True
        and execution.get("install_returncode") == 0
        and execution.get("doctor_returncode") == 0)
    updated["upgrade_complete"] = False
    if not installed:
        updated["automation_prompt_upgrade"] = {"status": "skipped_runtime_update_failed"}
        return updated
    if not before.get("ok") or not before.get("entries"):
        updated["automation_prompt_upgrade"] = {
            key: value for key, value in before.items() if key in {"ok", "status", "reason"}}
        updated["upgrade_complete"] = runtime_ready and before.get("ok") is True
        if not before.get("ok") and runtime_ready:
            updated["recommended_action"] = "Runtime updated; automation discovery failed. Review automation-prompts plan through the App before adopting prompts."
        return updated
    directory = Path(tempfile.mkdtemp(prefix="loopx-prompt-update-"))
    plan_file = directory / "before.json"
    save_snapshot(plan_file, before)
    driver = payload.get("install_lifecycle", {}).get("execution_driver")
    if driver is None and isinstance(payload.get("source"), dict):
        driver = "archive_snapshot"
    command = ([sys.executable, "-m", "loopx.cli"] if driver in {"python_pip", "python_pipx"}
               else [str(Path.home() / ".local/bin/loopx")] if driver == "archive_snapshot"
               else ["loopx"])
    command += ["--format", "json", "--registry", str(registry.resolve())]
    if runtime_root:
        command += ["--runtime-root", runtime_root]
    command += ["automation-prompts", "sync-installed", "--codex-home", str(home),
                "--plan-file", str(plan_file), "--execute"]
    try:
        # Do not accidentally import a checkout through the parent's PYTHONPATH.
        env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        result = subprocess.run(command, capture_output=True, text=True, env=env,
                                timeout=timeout_seconds, cwd=directory)
        report = json.loads(result.stdout)
        if not isinstance(report, dict) or "results" not in report:
            raise ValueError("new runtime returned no prompt migration result")
    except (ValueError, OSError, subprocess.TimeoutExpired):
        report = {"ok": False, "status": "reconciliation_failed"}
    if not report.get("ok"):
        report["snapshot_file"] = str(plan_file)
        if runtime_ready:
            updated["recommended_action"] = "Runtime updated; review pending automation prompts using the App API, or retry sync-installed with the saved snapshot. Custom prompts and alternate loader bindings require explicit review."
            updated["next_action"] = {"kind": "apply_host_prompt_updates", "mutating": True,
                "requires_explicit_approval": any(row.get("status") == "review_required"
                    for row in report.get("results", [])),
                "reason": "Only byte-exact managed prompts have automatic adoption authority; custom entries require separate review.",
                "api_updates": report.get("api_updates", [])}
    else:
        plan_file.unlink()
        directory.rmdir()
    updated["automation_prompt_upgrade"] = report
    updated["upgrade_complete"] = runtime_ready and report.get("ok") is True
    return updated
