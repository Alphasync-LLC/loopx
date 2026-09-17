"""Run the semantic vocabulary drift smoke inside the pull-request pytest sweep.

The canary fleet discovers ``examples/**/*-smoke.py`` on its own, but the fleet
runs after merge and on a schedule, and ``loopx canary premerge`` selects smokes
by changed-path tokens. Neither is a commit-time check for a diff that only
touches ``loopx/``. This wrapper is the PR-path obligation named in the RFC
``docs/architecture/rfcs/semantic-vocabulary-convergence-v0.md`` (Section 10):
the smoke fails closed here on every pull request that runs the Python tests.
"""

from __future__ import annotations

import copy
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE = REPO_ROOT / "examples" / "semantic-vocabulary-drift-smoke.py"


def test_semantic_vocabulary_registry_matches_the_code() -> None:
    completed = subprocess.run(
        [sys.executable, "-B", str(SMOKE)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, (
        "semantic vocabulary drift smoke failed; the registry, computed inventory, or an "
        "anchor no longer matches the code:\n" + completed.stdout + completed.stderr
    )
    assert completed.stdout.startswith("semantic-vocabulary-drift-smoke: ok"), (
        completed.stdout
    )


@pytest.mark.parametrize("mutation", ["twin_budget", "twin_root", "scan_root"])
def test_registry_cannot_relax_scan_scope_or_twin_budget(mutation: str) -> None:
    smoke = runpy.run_path(str(SMOKE))
    registry = copy.deepcopy(smoke["load_registry"]())
    if mutation == "twin_budget":
        registry["dual_runtime_twins"]["module_budget"] += 1
    elif mutation == "twin_root":
        registry["dual_runtime_twins"]["root"] = "loopx/semantics"
    else:
        registry["vocabularies"]["effective_action"]["literal_scan"]["roots"] = ["loopx/control_plane"]
    with pytest.raises(smoke["Drift"]):
        smoke["check_coverage_floor"](registry)
        smoke["check_dual_runtime_twins"](registry)


@pytest.mark.parametrize("suffix", [".py", ".ts"])
@pytest.mark.parametrize("quote", ["'", '\"'])
def test_literal_scan_rejects_unknown_value_with_either_quote(suffix: str, quote: str) -> None:
    smoke = runpy.run_path(str(SMOKE))
    text = f"effective_action = {quote}unregistered_action{quote}"
    sources = [smoke["SourceFile"]("loopx/probe" + suffix, suffix, text)]
    with pytest.raises(smoke["Drift"], match="unregistered_action"):
        smoke["check_literal_vocabularies"](smoke["load_registry"](), sources)


def test_candidate_decisions_are_exhaustive_and_default_to_unknown() -> None:
    smoke = runpy.run_path(str(SMOKE))
    registry = smoke["load_registry"]()
    candidate_decisions = registry["formal_model"]["candidate_decisions"]
    assert candidate_decisions["default"] == "unknown"
    assert set(candidate_decisions["values"]) == {
        "reuse_existing",
        "extend_vocabulary",
        "create_vocabulary",
        "local_only",
        "external_input",
        "compatibility_only",
        "unknown",
    }

    registry["formal_model"]["candidate_decisions"]["default"] = "reuse_existing"
    with pytest.raises(smoke["Drift"], match="default unresolved candidates"):
        smoke["check_formal_model"](registry["formal_model"])


def test_bounded_producer_scan_rejects_unregistered_write() -> None:
    smoke = runpy.run_path(str(SMOKE))
    source = smoke["SourceFile"](
        "loopx/control_plane/quota/probe.py",
        ".py",
        'def produce():\n    return {"effective_action": "unregistered_action"}\n',
    )
    with pytest.raises(smoke["Drift"], match="unregistered_action"):
        smoke["check_producers"](
            {
                "relations": {"shared_field_names": [{"field": "effective_action", "slots": [{
                    "slot": "should_run.effective_action",
                    "vocabularies": ["effective_action", "agent_scope_frontier_action"],
                }]}]},
                "vocabularies": {
                    "agent_scope_frontier_action": {"values": ["frontier_wait"]},
                    "effective_action": {
                        "tier": "kernel",
                        "owners": {"python": None, "typescript": None},
                        "values": ["registered_action"],
                        "producers": ["loopx/control_plane/quota/probe.py::produce"],
                        "literal_scan": {"field": "effective_action", "roots": ["loopx"], "suffixes": [".py"]},
                    }
                }
            },
            [source],
        )


def test_bounded_producer_scan_does_not_treat_consumer_reads_as_writes() -> None:
    smoke = runpy.run_path(str(SMOKE))
    source = smoke["SourceFile"](
        "loopx/control_plane/quota/probe.py",
        ".py",
        'def consume(payload):\n    return payload.get("effective_action") == "registered_action"\n',
    )
    assert smoke["_producer_literals"]("effective_action", source) == set()


@pytest.mark.parametrize('suffix, text, expected', [
    ('.py', 'effective_action == Action.NORMAL.value or state == "not_an_action"', set()),
    ('.ts', 'effective_action === Action.NORMAL || state === "not_an_action";', set()),
    ('.py', '# effective_action = "comment"\nexample = \'effective_action == "example"\'', set()),
    ('.ts', '// effective_action = "comment"\nconst example = \'effective_action === "example"\';', set()),
    ('.py', 'effective_action = "run" if state == "condition" else "wait"', {'run', 'wait'}),
    ('.ts', 'effective_action = state === "condition" ? "run" : "wait";', {'run', 'wait'}),
    ('.py', 'str(packet.get("effective_action") or "") in {"run", "wait"}', {'run', 'wait'}),
    ('.ts', '["run", "wait"].includes(packet.effective_action);', {'run', 'wait'}),
    ('.py', 'match packet["effective_action"]:\n    case "run" | "wait": pass', {'run', 'wait'}),
    ('.ts', 'switch (packet.effective_action) { case "run": break; case "wait": break; }', {'run', 'wait'}),
    ('.ts', 'const packet = {["effective_action"]: "run"};', {'run'}),
    ('.ts', 'const packet = {[`effective_action`]: "run"};', {'run'}),
    ('.ts', 'const packet = {[effective_action]: "not_a_static_key"};', set()),
    ('.py', '(p.get("effective_action") and p["state"]) == "eligible"', set()),
    ('.py', '(p.get("effective_action") or p["state"]) == "eligible"', set()),
    ('.ts', '(packet.effective_action || packet.state) === "eligible";', set()),
    ('.ts', '(packet.effective_action ?? "") === "run";', {'run'}),
])
def test_literal_uses_belong_to_the_field_not_neighboring_syntax(suffix, text, expected):
    smoke = runpy.run_path(str(SMOKE))
    source = smoke['SourceFile']('loopx/probe' + suffix, suffix, text)
    assert set(smoke['scan_literals']('effective_action', ['loopx'], [suffix], [source])) == expected


@pytest.mark.parametrize('value', ['normal_run', 'agent_scope_wait'])
@pytest.mark.parametrize('suffix', ['.py', '.ts'])
def test_registered_root_action_literals_still_require_owner_import(value, suffix):
    smoke = runpy.run_path(str(SMOKE))
    source = smoke['SourceFile']('loopx/probe' + suffix, suffix, f'effective_action = "{value}"')
    with pytest.raises(smoke['Drift'], match='import EffectiveAction or AgentScopeFrontierAction'):
        smoke['check_literal_vocabularies'](smoke['load_registry'](), [source])


def test_real_monitor_membership_cannot_revert_to_bare_action_literals():
    smoke = runpy.run_path(str(SMOKE))
    path = 'loopx/control_plane/quota/monitor_poll_commit.ts'
    source = (REPO_ROOT / path).read_text()
    old = 'AgentScopeFrontierAction.AGENT_SCOPE_WAIT, EffectiveAction.MONITOR_QUIET_SKIP'
    assert old in source
    changed = source.replace(old, '"agent_scope_wait", "monitor_quiet_skip"')
    with pytest.raises(smoke['Drift'], match='bare action literals'):
        smoke['check_literal_vocabularies'](smoke['load_registry'](), [smoke['SourceFile'](path, '.ts', changed)])


@pytest.mark.parametrize('name, metadata, selection', [
    ('effective_action', 'call_producers', ['state']),
    ('loop_disposition', 'call_producers', ['state']),
    ('agent_scope_frontier_action', 'return_paths', ['action']),
    ('turn_route', 'return_paths', ['action']),
])
def test_registry_cannot_add_unanchored_output_selectors(name, metadata, selection):
    smoke = runpy.run_path(str(SMOKE))
    registry = copy.deepcopy(smoke['load_registry']())
    registry['vocabularies'][name].setdefault(metadata, {})[
        'loopx/control_plane/quota/decision_summary.py::quota_effective_action'
    ] = selection
    with pytest.raises(smoke['Drift'], match='anchored output evidence exactly'):
        smoke['check_coverage_floor'](registry)


def test_bounded_context_scope_excludes_only_declared_multi_value_fork() -> None:
    smoke = runpy.run_path(str(SMOKE))
    registry = smoke["load_registry"]()
    sources = smoke["load_sources"](REPO_ROOT)
    inventory = smoke["build_inventory"](REPO_ROOT, sources=sources)
    assert smoke["check_scope_declarations"](registry, inventory) == 3


def test_renaming_one_side_of_a_fork_launders_the_semantic_budget() -> None:
    """Pin the RFC Section 9 known limit so a future fix cannot be a silent edit.

    Collisions are keyed by name, so renaming one module's definition removes the
    name from ``multi_value_forks`` and lowers the semantic budget by one while
    the drift stays in the tree. This test asserts the limit as it is documented,
    not as it should be: if a change makes renaming refuse to lower the budget,
    this test must fail so the RFC's known-limits section is updated with it.
    """
    smoke = runpy.run_path(str(SMOKE))
    registry = smoke["load_registry"]()
    sources = smoke["load_sources"](REPO_ROOT)
    before = smoke["build_inventory"](REPO_ROOT, sources=sources)
    assert smoke["check_scope_declarations"](registry, before) == 3

    path = "loopx/state_projection.py"
    name = "AGENT_TODO_HEADER_MARKERS"
    renamed = [
        smoke["SourceFile"](source.path, source.suffix, source.text.replace(name, name + "_RENAMED", 1))
        if source.path == path
        else source
        for source in sources
    ]
    after = smoke["build_inventory"](REPO_ROOT, sources=renamed)
    assert smoke["check_scope_declarations"](registry, after) == 2, (
        "a rename no longer lowers the semantic budget; the RFC known-limits entry "
        "('Renames launder a collision') is now stale and must be revised"
    )
    assert after["summary"]["multi_value_forks"] == before["summary"]["multi_value_forks"] - 1


def test_divergent_value_sets_lists_the_names_a_rename_would_hide() -> None:
    """The reviewer-facing signal for the laundering limit above.

    ``merge_candidate_groups`` groups *different* names with *identical* value
    sets, so it cannot see a fork at all -- a fork is one name whose value sets
    disagree. Renaming one side hides the name from both the budget and that
    grouping, so this advisory is keyed by name and still lists the abandoned
    name whenever the surviving definitions disagree.
    """
    from loopx.semantics.inventory import divergent_value_sets

    smoke = runpy.run_path(str(SMOKE))
    sources = smoke["load_sources"](REPO_ROOT)
    inventory = smoke["build_inventory"](REPO_ROOT, sources=sources)
    listed = {row["name"] for row in divergent_value_sets(inventory)}
    assert {"AGENT_TODO_HEADER_MARKERS", "USER_TODO_HEADER_MARKERS", "RAW_MATERIAL_KEY_HINTS"} <= listed

    # The advisory is not a budget input: it must not appear in the committed
    # inventory, which stays the single computed authority.
    assert "divergent_value_sets" not in inventory


def _restate(smoke, sources, path, name, replacement):
    return [
        smoke["SourceFile"](source.path, source.suffix, source.text.replace(name, replacement, 1))
        if source.path == path
        else source
        for source in sources
    ]


def test_rename_visibility_splits_into_three_cases() -> None:
    """The complete boundary, measured, so no reader has to re-derive it.

    Case 1: a partial rename of a **declared** name is rejected outright -- the
    declaration names every defining module and the renamed side no longer
    matches, so the rename cannot lower the budget.

    Cases 2 and 3 are the RFC Section 9 limit, and this test records it as it
    actually behaves rather than as the limit's heading suggests: renaming one
    side leaves the name with a single definition, so it stops being a fork and
    drops out of ``divergent_value_sets`` exactly as it drops out of the budget.
    The advisory makes *surviving* forks visible by name; it does not detect the
    rename. Both cases assert that so a future claim of coverage fails here.
    """
    from loopx.semantics.inventory import divergent_value_sets

    smoke = runpy.run_path(str(SMOKE))
    registry = smoke["load_registry"]()
    sources = smoke["load_sources"](REPO_ROOT)
    name = "AGENT_TODO_HEADER_MARKERS"

    def renamed_in(paths):
        out = sources
        for path in paths:
            out = [
                smoke["SourceFile"](source.path, source.suffix, source.text.replace(name, name + "_RENAMED", 1))
                if source.path == path
                else source
                for source in out
            ]
        return out

    # Case 1: declared name, one side renamed -> the declaration no longer resolves.
    declared = _restate(smoke, sources, "loopx/global_todos.py", "SOURCE_SURFACES", "GT_SOURCE_SURFACES")
    with pytest.raises(smoke["Drift"], match="every defining module"):
        smoke["check_scope_declarations"](registry, smoke["build_inventory"](REPO_ROOT, sources=declared))

    # Case 2: undeclared name, one side renamed -> gone from the budget AND the advisory.
    partial = smoke["build_inventory"](REPO_ROOT, sources=renamed_in(["loopx/state_projection.py"]))
    assert name not in {entry["name"] for entry in partial["duplicate_definitions"]["multi_value_forks"]}
    assert name not in {row["name"] for row in divergent_value_sets(partial)}

    # Case 3: every side renamed -> also invisible; indistinguishable from an honest rename.
    whole = smoke["build_inventory"](
        REPO_ROOT,
        sources=renamed_in([
            "loopx/state_projection.py",
            "loopx/control_plane/goals/active_state_metadata.py",
        ]),
    )
    assert name not in {entry["name"] for entry in whole["duplicate_definitions"]["multi_value_forks"]}
    assert name not in {row["name"] for row in divergent_value_sets(whole)}

    # The surviving forks are what the advisory does list, by name.
    assert "USER_TODO_HEADER_MARKERS" in {row["name"] for row in divergent_value_sets(partial)}


def test_bounded_context_scope_requires_every_distinct_defining_module() -> None:
    smoke = runpy.run_path(str(SMOKE))
    registry = copy.deepcopy(smoke["load_registry"]())
    registry["scope_declarations"]["SOURCE_SURFACES"]["contexts"] = registry["scope_declarations"]["SOURCE_SURFACES"]["contexts"][:-1]
    sources = smoke["load_sources"](REPO_ROOT)
    inventory = smoke["build_inventory"](REPO_ROOT, sources=sources)
    with pytest.raises(smoke["Drift"], match="every defining module"):
        smoke["check_scope_declarations"](registry, inventory)


@pytest.mark.parametrize("text, expected", [
    ('payload["effective_action"] = "new_action"', {"new_action"}),
    ('route.effective_action: str = "new_action"', {"new_action"}),
    ('Packet(effective_action="new_action")', {"new_action"}),
    ('payload = {"effective_action":\n "left" if flag == "condition" else "right"}', {"left", "right"}),
    ('effective_action = payload.get("effective_action", "fallback")', set()),
    ('effective_action == "not_produced"', set()),
    ('# effective_action = "comment"', set()),
    ('example = \'effective_action = "example"\'', set()),
])
def test_python_production_forms_separate_result_from_context(text, expected) -> None:
    smoke = runpy.run_path(str(SMOKE))
    source = smoke["SourceFile"]("loopx/control_plane/quota/probe.py", ".py", text)
    assert smoke["_producer_literals"]("effective_action", source) == expected


def test_return_producer_scope_cannot_be_removed_from_registry():
    smoke = runpy.run_path(str(SMOKE))
    registry = copy.deepcopy(smoke['load_registry']())
    registry['vocabularies']['effective_action']['return_producers'] = []
    with pytest.raises(smoke['Drift'], match='RETURN_PRODUCER_ANCHOR'):
        smoke['check_coverage_floor'](registry)


@pytest.mark.parametrize('name', ['turn_route', 'loop_disposition', 'agent_scope_frontier_action'])
def test_registered_kernel_producer_coverage_cannot_be_removed(name):
    smoke = runpy.run_path(str(SMOKE))
    registry = copy.deepcopy(smoke['load_registry']())
    registry['vocabularies'][name].pop('producers')
    with pytest.raises(smoke['Drift'], match='PRODUCER_VOCABULARY_ANCHOR'):
        smoke['check_coverage_floor'](registry)


@pytest.mark.parametrize('metadata,name', [
    ('call_producers', 'loop_disposition'),
    ('call_producers', 'agent_scope_frontier_action'),
    ('call_producers', 'turn_result_kind'),
    ('return_paths', 'turn_route'),
    ('return_paths', 'turn_result_kind'),
])
def test_explicit_output_evidence_cannot_be_removed_or_redirected(metadata, name):
    smoke = runpy.run_path(str(SMOKE))
    registry = copy.deepcopy(smoke['load_registry']())
    registry['vocabularies'][name][metadata] = {}
    with pytest.raises(smoke['Drift'], match='anchored output evidence'):
        smoke['check_coverage_floor'](registry)


@pytest.mark.parametrize('name', [
    'turn_result_kind',
    'turn_route',
    'loop_disposition',
    'agent_scope_frontier_action',
])
def test_turn_kernel_values_each_carry_a_note(name):
    """A Turn kernel value with no note sends every reader back to the code.

    The registry already settles who owns a vocabulary and which values are
    legal. These four decide what one Turn did and what the outer loop does
    next, so a new value here is a new control-flow case. Requiring the note in
    the same diff keeps that case reviewable instead of leaving it as a bare
    token whose meaning lives only in the controller rules.
    """
    smoke = runpy.run_path(str(SMOKE))
    vocabulary = smoke['load_registry']()['vocabularies'][name]
    notes = vocabulary.get('value_notes', {})
    undocumented = [
        value for value in vocabulary['values']
        if not str(notes.get(value) or '').strip()
    ]
    assert not undocumented, f'{name}: values with no value_notes entry: {undocumented}'


@pytest.mark.parametrize("legacy_report", [None, "not even JSON"])
def test_live_inventory_ignores_missing_or_stale_reports(tmp_path, monkeypatch, legacy_report):
    smoke = runpy.run_path(str(SMOKE))
    registry = smoke["load_registry"]()
    sources = smoke["load_sources"](REPO_ROOT)
    if legacy_report is not None:
        path = tmp_path / "loopx/semantics/inventory_v0.json"
        path.parent.mkdir(parents=True)
        path.write_text(legacy_report)
    monkeypatch.setitem(smoke["check_inventory"].__globals__, "REPO_ROOT", tmp_path)
    inventory, _ = smoke["check_inventory"](registry, sources)
    assert inventory["summary"]["source_files"] == len(sources)
    # A newly observed duplicate must still fail; an old or missing report cannot hide it.
    duplicate = [smoke["SourceFile"](f"loopx/q9_{name}.py", ".py", 'Q9_DUPLICATE = "same"\n')
                 for name in ("first", "second")]
    with pytest.raises(smoke["Drift"], match="same_runtime_forks grew"):
        smoke["check_inventory"](registry, sources + duplicate)


@pytest.mark.parametrize('name', ['effective_action', 'lease_action'])
def test_remaining_kernel_values_each_carry_a_note(name):
    """The two kernel vocabularies that are not Turn control flow still need notes.

    ``effective_action`` is the overloaded should-run slot M1 is due to split, so
    a value here is only legible once the registry says which condition produces
    it; ``lease_action`` is legacy and every value is compatibility-only, which
    is exactly the kind of disposition a reader cannot infer from the name. The
    note is required in the diff that adds a value, not afterwards.
    """
    smoke = runpy.run_path(str(SMOKE))
    vocabulary = smoke['load_registry']()['vocabularies'][name]
    notes = vocabulary.get('value_notes', {})
    undocumented = [
        value for value in vocabulary['values']
        if not str(notes.get(value) or '').strip()
    ]
    assert not undocumented, f'{name}: values with no value_notes entry: {undocumented}'
