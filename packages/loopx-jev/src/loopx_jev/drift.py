"""D1 shadow lifecycle. Private evidence and model results never enter authority."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import time
from typing import Any, Callable

from loopx.file_lock import exclusive_file_lock

from .config import Config, load_config, read_json
from .drift_capture import delta, digest, stable_capture, validate_paths
from .runner import SECRET, assess_one, read_basis
from .store import RunStore, atomic_json, initialize_run

SCHEMA = "jev_drift_shadow_v0"
MAX_EVENTS = 256
MAX_PENDING = 16


def policy(path: Path | None) -> Config:
    config = load_config(path)
    if config.mode == "assist":
        raise ValueError("drift_supports_off_or_shadow_only")
    if config.mode != "off" and "progress_review" not in config.scenarios:
        raise ValueError("enable_progress_review_scenario")
    return config


def state(root: Path) -> dict[str, Any]:
    value, _ = read_json(root / "state.json", 4 * 1024 * 1024)
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("invalid_drift_state")
    required = {
        "goal_id",
        "repo",
        "basis_path",
        "config_path",
        "paths",
        "baseline",
        "contract_revision",
        "configuration_epoch",
        "events",
        "seen_evidence",
        "capture_failures",
    }
    if not required <= value.keys() or not isinstance(value["events"], dict):
        raise ValueError("invalid_drift_state")
    return value


def contract(path: Path, repo: Path) -> tuple[dict[str, Any], str, Callable[[], bool]]:
    basis, guard = read_basis(path, repo)
    if not isinstance(basis.get("goal_id"), str) or not basis["goal_id"].strip():
        raise ValueError("missing_goal_identity")
    _, revision = read_json(path, 32768)
    return basis, revision, guard


def initialize(
    root: Path, repo: Path, basis_path: Path, config_path: Path, paths: list[str]
) -> dict[str, Any]:
    config = policy(config_path)
    if config.mode == "off":
        return {"status": "disabled"}
    repo = repo.resolve()
    paths = validate_paths(repo, paths)
    basis, revision, guard = contract(basis_path, repo)
    baseline = stable_capture(repo, paths)
    baseline["external_evidence"] = basis.get("evidence", [])
    if SECRET.search(str(baseline)) or not guard():
        raise ValueError("unsafe_or_changed_initial_evidence")
    if root.exists():
        raise ValueError("state_exists_use_existing_state_or_new_explicit_budget")
    root.mkdir(parents=True, mode=0o700)
    (root / "jobs").mkdir(mode=0o700)
    (root / "results").mkdir(mode=0o700)
    initialize_run(root / "requests", config.max_requests_per_run)
    atomic_json(
        root / "state.json",
        {
            "schema": SCHEMA,
            "goal_id": basis["goal_id"],
            "repo": str(repo),
            "basis_path": str(basis_path.resolve()),
            "config_path": str(config_path.resolve()),
            "paths": paths,
            "baseline": baseline,
            "contract_revision": revision,
            "events": {},
            "seen_evidence": [],
            "capture_failures": 0,
            "configuration_epoch": 0,
        },
    )
    return {
        "status": "baseline_created",
        "goal_id": basis["goal_id"],
        "scope_file_count": len(paths),
        "authority": "none",
    }


def prepare(root: Path, config_path: Path) -> dict[str, Any]:
    current = state(root)
    if str(config_path.resolve()) != current["config_path"]:
        raise ValueError("configuration_path_mismatch")
    config = policy(config_path)
    if config.mode != "shadow":
        raise ValueError("shadow_disabled")
    repo = Path(current["repo"])
    basis, revision, guard = contract(Path(current["basis_path"]), repo)
    snapshot = stable_capture(repo, current["paths"])
    snapshot["external_evidence"] = basis.get("evidence", [])
    if basis["goal_id"] != current["goal_id"] or not guard():
        raise ValueError("goal_or_evidence_changed")
    if SECRET.search(str(snapshot)) or SECRET.search(str(basis)):
        raise ValueError("credential_like_evidence")
    return {
        "snapshot": snapshot,
        "basis": basis,
        "contract_revision": revision,
        "config_generation": config.generation,
        "baseline_digest": digest(current["baseline"]),
        "configuration_epoch": current["configuration_epoch"],
        "evidence_guard": guard,
    }


def invalidate_baseline(root: Path) -> None:
    """Do not compare across a missed/failed capture as if it were one work round."""
    with exclusive_file_lock(root / "capture.lock"):
        current = state(root)
        current["baseline"] = None
        current["capture_failures"] += 1
        atomic_json(root / "state.json", current)


def enqueue(
    root: Path,
    prepared: dict[str, Any],
    record_path: Path,
    *,
    prepare_ns: int | None = None,
    owner_command_ns: int | None = None,
) -> dict[str, Any]:
    started = time.perf_counter_ns()
    record, record_digest = read_json(record_path, 4 * 1024 * 1024)
    with exclusive_file_lock(root / "capture.lock"):
        current = state(root)
        if record.get("goal_id") != current["goal_id"] or not record.get(
            "generated_at"
        ):
            raise ValueError("run_goal_or_identity_mismatch")
        # Checkpoint supplements for the same bound Turn are the same transition.
        identity = (
            {
                "turn": record["turn_instance_id"],
                "goal": current["goal_id"],
                "agent": record.get("agent_id"),
                "todo": record.get("todo_id"),
            }
            if record.get("turn_instance_id")
            else {"run_digest": record_digest}
        )
        event_id = digest(identity)
        if event_id in current["events"]:
            return {"status": "duplicate_event", "event_id": event_id}
        if len(current["events"]) >= MAX_EVENTS:
            raise ValueError("event_retention_budget_exhausted")
        live = prepare(root, Path(current["config_path"]))
        if (
            live["snapshot"] != prepared["snapshot"]
            or live["contract_revision"] != prepared["contract_revision"]
            or live["config_generation"] != prepared["config_generation"]
            or live["configuration_epoch"] != prepared["configuration_epoch"]
            or not prepared["evidence_guard"]()
        ):
            raise ValueError("evidence_changed_during_refresh")
        previous = current["baseline"]
        captured = prepared["snapshot"]
        status = "queued"
        text = ""
        if (
            previous is None
            or current["contract_revision"] != prepared["contract_revision"]
            or digest(previous) != prepared["baseline_digest"]
        ):
            status = "baseline_reset"
        else:
            text = delta(previous, captured)
            if not text:
                status = (
                    "no_delta"
                    if previous["index_digest"] == captured["index_digest"]
                    else "index_only_change_unknown"
                )
        # Equal patches against different surrounding source are different evidence.
        context = {
            "before": previous["files"] if previous else None,
            "after": captured["files"],
        }
        evidence_id = digest(
            {
                "contract": prepared["contract_revision"],
                "delta": text,
                "context": context,
            }
        )
        if status == "queued" and evidence_id in current["seen_evidence"]:
            status = "duplicate_evidence"
        if status == "queued":
            pending = sum(
                row["status"] == "queued" for row in current["events"].values()
            )
            if pending >= MAX_PENDING:
                raise ValueError("pending_evidence_budget_exhausted")
            basis = dict(prepared["basis"])
            basis["evidence"] = [
                *basis.get("evidence", []),
                {
                    "ref": "scoped-checkpoint-context",
                    "text": json.dumps(context, ensure_ascii=False, sort_keys=True),
                    "origin": "host_scoped_file_read",
                    "sha256": digest(context),
                },
                {
                    "ref": "captured-workspace-delta",
                    "text": text,
                    "origin": "host_scoped_file_comparison",
                    "sha256": digest(text),
                },
            ]
            basis["horizon"] = (
                "Historical net change between two explicit checkpoints in the listed files only. "
                "Do not infer whole-task progress, tool success, or exclusive authorship. "
                "Missing surrounding context requires unknown."
            )
            snapshot = {
                "schema": "jev_progress_input_v0",
                "scenario": "progress_review",
                "source": {
                    "owner": "scoped_checkpoint_capture",
                    "revision": evidence_id,
                },
                "facts": {
                    "work_summary": "Inspect the host-captured scoped delta; no Agent self-report supplied.",
                    "history_available": True,
                },
            }
            job = {
                "event_id": event_id,
                "evidence_id": evidence_id,
                "record_digest": record_digest,
                "contract_revision": prepared["contract_revision"],
                "config_generation": prepared["config_generation"],
                "configuration_epoch": prepared["configuration_epoch"],
                "source_record": str(record_path.resolve()),
                "basis": basis,
                "snapshot": snapshot,
                "paths": current["paths"],
            }
            atomic_json(root / "jobs" / f"{event_id}.json", job)
            current["seen_evidence"].append(evidence_id)
        current["baseline"] = captured
        current["contract_revision"] = prepared["contract_revision"]
        current["events"][event_id] = {
            "sequence": len(current["events"]),
            "status": status,
            "evidence_id": evidence_id,
            "capture_ns": time.perf_counter_ns() - started,
            "prepare_ns": prepare_ns,
            "owner_command_ns": owner_command_ns,
        }
        atomic_json(root / "state.json", current)
    return {"event_id": event_id, "status": status, "authority": "none"}


def drain(
    root: Path,
    config_path: Path | None,
    *,
    transport: Callable[..., dict[str, Any]] | None = None,
    credential: Callable[[], str | None] | None = None,
) -> dict[str, Any]:
    config = policy(config_path)
    if config.mode == "off":
        return {"status": "disabled"}
    processed = []
    # This is an extension-only consumer lock. Capture and LoopX use other locks.
    # A concurrent consumer cannot finalize an in-flight reservation as a failure.
    with exclusive_file_lock(root / "consumer.lock"):
        initial = state(root)
        if config_path is None or str(config_path.resolve()) != initial["config_path"]:
            raise ValueError("configuration_path_mismatch")
        for event_id, row in sorted(
            initial["events"].items(), key=lambda item: item[1]["sequence"]
        ):
            if row["status"] != "queued":
                continue
            job_path = root / "jobs" / f"{event_id}.json"
            job, job_digest = read_json(job_path, 256 * 1024)

            def current() -> bool:
                try:
                    now = policy(config_path)
                    return (
                        now.mode == "shadow"
                        and now.generation == job["config_generation"]
                        and state(root)["configuration_epoch"]
                        == job["configuration_epoch"]
                        and read_json(Path(initial["basis_path"]), 32768)[1]
                        == job["contract_revision"]
                        and read_json(job_path, 256 * 1024)[1] == job_digest
                        and read_json(Path(job["source_record"]), 4 * 1024 * 1024)[1]
                        == job["record_digest"]
                    )
                except (OSError, ValueError, KeyError, TypeError):
                    return False

            options: dict[str, Any] = {}
            if transport is not None:
                options["transport"] = transport
            if credential is not None:
                options["credential"] = credential
            started = time.perf_counter_ns()
            result = assess_one(
                job["snapshot"],
                job["basis"],
                config,
                RunStore(root / "requests"),
                current,
                **options,
            )
            report = {
                "schema": SCHEMA,
                "event_id": event_id,
                "evidence_id": job["evidence_id"],
                "mode": "shadow",
                "authority": "none",
                "worker_influence": "none",
                "historical_only": True,
                "assessment": result,
                "evaluation_ns": time.perf_counter_ns() - started,
            }
            atomic_json(root / "results" / f"{event_id}.json", report)
            with exclusive_file_lock(root / "capture.lock"):
                latest = state(root)
                latest["events"][event_id]["status"] = result["status"]
                atomic_json(root / "state.json", latest)
            # Raw delta is no longer needed after the immutable result is saved.
            job_path.unlink()
            processed.append({"event_id": event_id, "status": result["status"]})
    return {"status": "drained", "processed": processed, "authority": "none"}


def status(root: Path) -> dict[str, Any]:
    current = state(root)
    counts: dict[str, int] = {}
    rows = []
    for event_id, item in sorted(
        current["events"].items(), key=lambda item: item[1]["sequence"]
    ):
        counts[item["status"]] = counts.get(item["status"], 0) + 1
        row = {"event_id": event_id, **item}
        report_path = root / "results" / f"{event_id}.json"
        if report_path.is_file():
            report, _ = read_json(report_path)
            assessment = report["assessment"]
            row.update(
                judgments=assessment.get("assessment", {}).get("judgments"),
                reason=assessment.get("reason"),
                evaluation_ns=report["evaluation_ns"],
                request_id=assessment.get("request_id"),
                usage=assessment.get("usage"),
                assessment_timing_ns=assessment.get("assessment_timing_ns"),
                transport_timing_ns=assessment.get("transport_timing_ns"),
                worker_timing_ns=assessment.get("worker_timing_ns"),
                cached_provider_measurements=assessment.get(
                    "cached_provider_measurements", False
                ),
            )
        rows.append(row)
    configured = policy(Path(current["config_path"]))
    return {
        "schema": SCHEMA,
        "goal_id": current["goal_id"],
        "mode": configured.mode,
        "authority": "none",
        "worker_influence": "none",
        "historical_only": True,
        "counts": counts,
        "capture_failures": current["capture_failures"],
        "scope_file_count": len(current["paths"]),
        "model": configured.model,
        "allow_egress": configured.allow_egress,
        "label_probability_threshold": configured.minimum_label_probability,
        "events": rows,
        "limits": {
            k: v
            for k, v in asdict(configured).items()
            if k in {"deadline_ms", "max_requests_per_run", "max_request_bytes"}
        },
    }


def configure(root: Path, mode: str) -> dict[str, Any]:
    if mode not in {"off", "shadow"}:
        raise ValueError("drift_supports_off_or_shadow_only")
    with exclusive_file_lock(root / "capture.lock"):
        current = state(root)
        config_path = Path(current["config_path"])
        configured = policy(config_path)
        if mode == "shadow" and (
            not configured.model.strip()
            or "latest" in configured.model.lower()
            or "progress_review" not in configured.scenarios
        ):
            raise ValueError("shadow_requires_pinned_model_and_progress_scenario")
        value, _ = read_json(config_path, 16384)
        value["mode"] = mode
        current["configuration_epoch"] += 1
        current["baseline"] = None
        atomic_json(root / "state.json", current)
        atomic_json(config_path, value)
    return status(root)
