"""Role classification rules for the advisory consumer evidence report (RFC B5).

The rules come from the RFC, not from scanner output: a consumer reads or
accepts a value, and interpreter and pass-through are subroles of consumer
rather than a partition of modules. Every fixture here is finite and states
which side of the boundary it sits on -- a genuine read, a forward that changes
nothing, a branch on the value, and an access no name-keyed scan can resolve.

The negative fixtures matter as much as the positive ones. A report that
classifies everything would be wrong, so these pin what the scan must *not*
claim: a same-prefix identifier is a different slot, a bare mention is not a
read, and sequence indexing is not an unresolved mapping read.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from loopx.semantics.consumer_report import (
    ANY_VOCABULARY,
    CONSUMER_SCAN_ROOTS,
    ConsumerEvidence,
    collect_consumer_evidence,
    render_consumer_evidence,
    scan_dynamic_reads,
    scan_python_consumers,
    slot_name,
)
from loopx.semantics.inventory import SourceFile, load_sources

VALUES = ("alpha", "beta", "gamma")


def _source(text: str, path: str = "loopx/control_plane/probe.py") -> SourceFile:
    return SourceFile(path=path, suffix=".py", text=text)


def _roles(text: str, *, slot: str = "probe_slot", owners=None, modules=None) -> dict[tuple[str, int], str]:
    rows = scan_python_consumers(
        _source(text), vocabulary="probe", slot=slot, values=VALUES, owners=owners, modules=modules
    )
    return {(row.site.split("::")[1], row.line): row.role for row in rows}


def _rows(text: str, *, slot: str = "probe_slot", owners=None, modules=None):
    return scan_python_consumers(
        _source(text), vocabulary="probe", slot=slot, values=VALUES, owners=owners, modules=modules
    )


# --- positive fixtures: one role each -------------------------------------


def test_a_bound_read_that_goes_nowhere_is_a_read() -> None:
    """The site reads the slot and neither branches on it nor forwards it."""
    rows = _rows('def consume(payload):\n    current = payload["probe_slot"]\n    return None\n')
    assert [(row.role, row.anchor) for row in rows] == [("read", "slot_read")]
    assert rows[0].site == "loopx/control_plane/probe.py::consume"
    assert rows[0].line == 2
    assert "slot_name_keyed" in rows[0].limitation
    assert rows[0].blocker is None


def test_a_presence_check_is_a_read_not_a_branch_on_the_value() -> None:
    """``"slot" in payload`` reads whether the slot is there, not which value."""
    rows = _rows('def consume(payload):\n    if "probe_slot" in payload:\n        return 1\n    return 0\n')
    assert [(row.role, row.anchor) for row in rows] == [("read", "slot_presence")]
    assert rows[0].observed == ()


@pytest.mark.parametrize(
    "body",
    [
        'def forward(payload):\n    return payload["probe_slot"]\n',
        'def forward(payload):\n    return {"copied": payload["probe_slot"]}\n',
        'def forward(payload, out):\n    out["copied"] = payload["probe_slot"]\n',
        'def forward(payload, sink):\n    sink(payload["probe_slot"])\n',
        'def forward(payload):\n    return f"got {payload[\'probe_slot\']}"\n',
        'def forward(record):\n    return str(record.probe_slot)\n',
        'def forward(payload):\n    return payload.get("probe_slot")\n',
    ],
)
def test_a_site_that_only_moves_the_value_is_a_pass_through(body: str) -> None:
    """Serializing, returning, copying and displaying do not change meaning."""
    rows = _rows(body)
    assert [row.role for row in rows] == ["pass_through"], body
    assert "forward_target_untraced" in rows[0].limitation


def test_an_enum_unwrap_into_a_payload_stays_a_pass_through() -> None:
    """``.value`` serializes the member; the climb must not stop at it."""
    rows = _rows('def forward(snapshot):\n    return {"probe_slot": snapshot.probe_slot.value}\n')
    assert [row.role for row in rows] == ["pass_through"]


@pytest.mark.parametrize(
    "body",
    [
        'def decide(payload):\n    if payload["probe_slot"] == "alpha":\n        return 1\n    return 0\n',
        'def decide(payload):\n    return payload["probe_slot"] in ("alpha", "beta")\n',
        'def decide(payload):\n    match payload["probe_slot"]:\n        case "alpha":\n            return 1\n    return 0\n',
        'def decide(payload, table):\n    return table[payload["probe_slot"]]\n',
        'def decide(payload):\n    current = payload["probe_slot"]\n    if current == "alpha":\n        return 1\n    return 0\n',
    ],
)
def test_a_site_that_branches_on_the_value_is_an_interpreter(body: str) -> None:
    rows = _rows(body)
    assert [row.role for row in rows] == ["interpret"], body
    assert "branch_operands_only" in rows[0].limitation


def test_the_interpreter_records_only_the_registered_values_it_names() -> None:
    """Observed values are a subdomain of the registered domain, never wider."""
    rows = _rows('def decide(payload):\n    return payload["probe_slot"] in ("alpha", "not_registered")\n')
    assert rows[0].domain == ("alpha", "beta", "gamma")
    assert rows[0].observed == ("alpha",)


def test_interpreting_outranks_forwarding_when_a_site_does_both() -> None:
    """The subroles are not exclusive; the stronger claim is reported."""
    rows = _rows(
        'def decide(payload, sink):\n'
        '    current = payload["probe_slot"]\n'
        '    sink(current)\n'
        '    if current == "beta":\n'
        '        return 1\n'
        '    return 0\n'
    )
    assert [row.role for row in rows] == ["interpret"]
    assert rows[0].observed == ("beta",)


def test_an_owner_member_comparison_is_an_interpreter_without_the_slot_name() -> None:
    """The registered owner class anchors sites that never spell the slot."""
    owner = _source(
        'from enum import Enum\n\n\nclass ProbeKind(str, Enum):\n'
        '    ALPHA = "alpha"\n    BETA = "beta"\n',
        path="loopx/control_plane/owner.py",
    )
    consumer = (
        'from loopx.control_plane.owner import ProbeKind\n\n\n'
        'def decide(decision):\n'
        '    if decision.kind is ProbeKind.ALPHA:\n'
        '        return 1\n'
        '    return 0\n'
    )
    rows = scan_python_consumers(
        _source(consumer), vocabulary="probe", slot="probe_slot", values=VALUES,
        owners={"loopx/control_plane/owner.py::ProbeKind": {"ALPHA": "alpha", "BETA": "beta"}},
        modules={owner.path: owner},
    )
    assert [(row.role, row.anchor, row.observed) for row in rows] == [("interpret", "owner_member", ("alpha",))]


# --- unknowns, each with a recorded reason ---------------------------------


def test_a_computed_mapping_key_is_unknown_for_every_vocabulary_at_once() -> None:
    """No name-keyed scan can prove this site is not a reader of some slot."""
    rows = scan_dynamic_reads(_source('def consume(payload, key):\n    return payload.get(key)\n'))
    assert [(row.vocabulary, row.role, row.blocker) for row in rows] == [
        (ANY_VOCABULARY, "unknown", "dynamic_key")
    ]
    assert rows[0].line == 2
    assert "unresolved, not absent" in rows[0].limitation


def test_a_reassigned_local_is_unknown_rather_than_guessed() -> None:
    rows = _rows(
        'def consume(payload, flag):\n'
        '    current = payload["probe_slot"]\n'
        '    if flag:\n'
        '        current = "beta"\n'
        '    return current\n'
    )
    assert [(row.role, row.blocker) for row in rows] == [("unknown", "unstable_local")]


def test_a_local_that_escapes_into_a_nested_scope_is_unknown() -> None:
    rows = _rows(
        'def consume(payload):\n'
        '    current = payload["probe_slot"]\n'
        '\n'
        '    def inner():\n'
        '        return current\n'
        '    return inner\n'
    )
    assert [(row.role, row.blocker) for row in rows] == [("unknown", "nested_scope_escape")]


def test_an_unresolved_row_still_carries_its_location_and_domain() -> None:
    """An unknown is a visible site, not a dropped one."""
    rows = _rows('def consume(payload, flag):\n    current = payload["probe_slot"]\n'
                 '    current = flag\n    return current\n')
    assert rows[0].site == "loopx/control_plane/probe.py::consume"
    assert rows[0].line == 2
    assert rows[0].domain == ("alpha", "beta", "gamma")


# --- negative fixtures: what the scan must not claim ------------------------


def test_a_same_prefix_identifier_is_a_different_slot() -> None:
    """``probe_slot_repair`` is its own field, not a use of ``probe_slot``."""
    assert _rows('def consume(payload):\n    return payload["probe_slot_repair"]\n') == []
    assert _rows('def consume(record):\n    return record.probe_slot_repair\n') == []


def test_sequence_indexing_is_not_an_unresolved_mapping_read() -> None:
    """``rows[index]`` and ``payload[key]`` are the same syntax; neither counts.

    Counting computed subscripts would inflate the unknown until it stopped
    carrying information, so only unambiguous mapping accessors are counted.
    """
    assert scan_dynamic_reads(_source('def consume(rows, index):\n    return rows[index]\n')) == []


def test_a_prose_mention_is_never_reported_as_a_read() -> None:
    """A docstring carries the token without touching the value."""
    assert _rows('def consume(payload):\n    """Handle the probe_slot field."""\n    return payload\n') == []


def test_an_unimported_owner_symbol_yields_no_owner_anchor() -> None:
    """A locally defined class of the same name is not the registered owner."""
    owner = _source(
        'from enum import Enum\n\n\nclass ProbeKind(str, Enum):\n    ALPHA = "alpha"\n',
        path="loopx/control_plane/owner.py",
    )
    rows = scan_python_consumers(
        _source(
            'class ProbeKind:\n    ALPHA = "alpha"\n\n\n'
            'def decide(decision):\n    return decision.kind is ProbeKind.ALPHA\n'
        ),
        vocabulary="probe", slot="probe_slot", values=VALUES,
        owners={"loopx/control_plane/owner.py::ProbeKind": {"ALPHA": "alpha"}},
        modules={owner.path: owner},
    )
    assert rows == []


def test_the_slot_name_falls_back_to_the_vocabulary_id() -> None:
    assert slot_name("probe", {}) == "probe"
    assert slot_name("probe", {"literal_scan": {"field": "declared_slot"}}) == "declared_slot"


# --- whole-scan shape ------------------------------------------------------


@pytest.fixture
def scan_repo(tmp_path: Path) -> Path:
    def write(relative: str, text: str) -> None:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    write(
        "loopx/control_plane/decide.py",
        'def decide(payload):\n'
        '    if payload["probe"] == "alpha":\n'
        '        return 1\n'
        '    return 0\n'
        '\n'
        '\n'
        'def lookup(payload, key):\n'
        '    return payload.get(key)\n',
    )
    write("loopx/control_plane/notes.py", '"""Mentions probe in prose only."""\n')
    write("loopx/control_plane/twin.ts", 'export const PROBE = "probe";\n')
    write("loopx/capabilities/out_of_reach.py", 'def decide(payload):\n    return payload["probe"]\n')
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.email=t@e", "-c", "user.name=t",
                                                 "commit", "-qm", "fixture"]):
        subprocess.run(["git", *argv], cwd=tmp_path, check=True, stdout=subprocess.DEVNULL)
    return tmp_path


REGISTRY = {"vocabularies": {"probe": {"values": list(VALUES), "owners": {}}}}


def _evidence(root: Path) -> ConsumerEvidence:
    return collect_consumer_evidence(root, REGISTRY, load_sources(root))


def test_every_row_carries_a_location_a_domain_and_a_limitation(scan_repo: Path) -> None:
    evidence = _evidence(scan_repo)
    assert evidence.rows
    for row in evidence.rows:
        assert row.site.count("::") == 1 and row.line >= 1
        assert row.limitation
        assert (row.blocker is None) == (row.role != "unknown")


def test_the_scan_records_the_commit_it_ran_against(scan_repo: Path) -> None:
    evidence = _evidence(scan_repo)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=scan_repo, check=True,
                          stdout=subprocess.PIPE).stdout.decode().strip()
    assert evidence.source_sha == head
    assert evidence.worktree_dirty is False
    (scan_repo / "loopx/control_plane/decide.py").write_text("x = 1\n", encoding="utf-8")
    assert _evidence(scan_repo).worktree_dirty is True


def test_the_scan_reach_is_code_owned_and_excludes_what_it_did_not_walk(scan_repo: Path) -> None:
    """A module outside the roots yields no row, and the reach is reported."""
    evidence = _evidence(scan_repo)
    assert CONSUMER_SCAN_ROOTS == ("loopx/control_plane", "loopx/cli_commands")
    assert not any("capabilities" in row.site for row in evidence.rows)
    assert evidence.scanned_files == 2 and evidence.tracked_files == 4


def test_a_mention_the_grammar_does_not_recognize_is_unknown_not_absent(scan_repo: Path) -> None:
    """Otherwise the per-vocabulary tables would read as complete."""
    evidence = _evidence(scan_repo)
    blockers = {(row.site, row.blocker) for row in evidence.rows if row.role == "unknown"}
    assert ("loopx/control_plane/notes.py::<module>", "mention_without_recognized_anchor") in blockers
    assert ("loopx/control_plane/twin.ts::<module>", "typescript_not_walked") in blockers
    assert ("loopx/control_plane/decide.py::lookup", "dynamic_key") in blockers


def test_the_report_states_both_unknown_shares_and_never_gates(scan_repo: Path) -> None:
    evidence = _evidence(scan_repo)
    assert evidence.counts()["interpret"] == 1
    assert 0.0 < evidence.unknown_share() < 1.0
    printed = "\n".join(render_consumer_evidence(evidence, top=5))
    assert "advisory" in printed and "not proved data flow" in printed
    assert "unknown_share=" in printed and "attributed_unknown_share=" in printed
    assert "unknown_reasons: " in printed


def test_the_same_tree_reports_the_same_rows(scan_repo: Path) -> None:
    assert _evidence(scan_repo).rows == _evidence(scan_repo).rows
