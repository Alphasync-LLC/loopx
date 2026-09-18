"""The example oracle must reject false conclusions and unadopted dependencies."""
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "examples" / "managed-research-team"))
from scenario import encoded, evidence, validate_worker, validate_report  # noqa: E402


def fixture(root: Path) -> dict:
    dependencies = {}
    for worker in ("analyst", "reviewer"):
        for revision, raw, normalized, stale, source in (
            ("initial", 90, 40, False, "filing-initial"),
            ("corrected", 75, 25, True, "filing-correction"),
        ):
            work = root / worker / revision
            work.mkdir(parents=True)
            input_bytes = encoded(evidence(revision))
            (work / "input.json").write_bytes(input_bytes)
            output = {"revision": revision, "input_sha256": sha256(input_bytes).hexdigest(),
                      "raw_fcf": raw, "normalized_fcf": normalized, "period_comparable": False,
                      "growth_supported": False, "independent_source_families": 1, "repost_stale": stale,
                      "source_refs": [source, "prior-filing", "repost"], "reason": "Different periods; one source family."}
            (work / "output.json").write_bytes(encoded(output))
            (root / "accepted").mkdir(exist_ok=True)
            (root / "accepted" / (worker + "-" + revision + ".json")).write_bytes(encoded({"turn_status": "committed", "evidence": output}))
            dependencies[worker + "/" + revision] = sha256(encoded(output)).hexdigest()
    report = {"initial_normalized_fcf": 40, "corrected_normalized_fcf": 25, "revision_delta": -15,
              "growth_supported": False, "independent_source_families": 1,
              "repost_stale_after_correction": True, "dependencies": dependencies,
              "reason": "Correction reduces normalized cash; growth is unsupported."}
    (root / "lead").mkdir()
    (root / "lead" / "report.json").write_bytes(encoded(report))
    return report


def test_valid_dependency_adoption(tmp_path):
    fixture(tmp_path)
    assert validate_report(tmp_path)["revision_delta"] == -15


@pytest.mark.parametrize("field,value", [("normalized_fcf", 75), ("period_comparable", True),
                                         ("growth_supported", True), ("independent_source_families", 2),
                                         ("independent_source_families", True), ("repost_stale", False)])
def test_worker_rejects_wrong_semantics(tmp_path, field, value):
    fixture(tmp_path)
    work = tmp_path / "reviewer" / "corrected"
    output = json.loads((work / "output.json").read_text())
    output[field] = value
    (work / "output.json").write_bytes(encoded(output))
    with pytest.raises(ValueError, match="rejected"):
        validate_worker(work, "corrected")


@pytest.mark.parametrize("mutation", ["stale_hash", "unaccepted", "changed_input", "missing_output", "wrong_aggregate"])
def test_report_rejects_broken_dependencies(tmp_path, mutation):
    report = fixture(tmp_path)
    if mutation == "stale_hash":
        report["dependencies"]["analyst/corrected"] = report["dependencies"]["analyst/initial"]
    elif mutation == "wrong_aggregate":
        report["growth_supported"] = True
    elif mutation == "unaccepted":
        path = tmp_path / "accepted" / "analyst-corrected.json"
        row = json.loads(path.read_text())
        row["turn_status"] = "failed"
        path.write_bytes(encoded(row))
    elif mutation == "changed_input":
        (tmp_path / "analyst" / "corrected" / "input.json").write_text("{}")
    else:
        (tmp_path / "analyst" / "corrected" / "output.json").unlink()
    (tmp_path / "lead" / "report.json").write_bytes(encoded(report))
    with pytest.raises((ValueError, FileNotFoundError)):
        validate_report(tmp_path)


def test_delegation_returns_actionable_oracle_failure_without_accepting_it(tmp_path, monkeypatch):
    import demo

    fixture(tmp_path)
    (tmp_path / "accepted" / "analyst-initial.json").unlink()
    (tmp_path / "settings.json").write_text(json.dumps({"dsh_model": "fixture"}))
    work = tmp_path / "analyst" / "initial"
    output = json.loads((work / "output.json").read_text())
    output["independent_source_families"] = 2
    (work / "output.json").write_bytes(encoded(output))
    monkeypatch.setattr(demo, "assign", lambda *args: None)
    monkeypatch.setattr(demo, "turn", lambda *args: {"status": "failed", "result_kind": "validation_failed"})
    result = demo.delegate(tmp_path, "analyst", "initial", "Check current-period evidence.")
    assert result["accepted"] is False
    assert result["reason"] == "worker_evidence_rejected:independent_source_families"
    assert not (tmp_path / "accepted" / "analyst-initial.json").exists()
