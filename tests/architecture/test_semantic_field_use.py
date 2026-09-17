"""Pin the B3 retirement metric against finite counterexamples.

The metric replaces a token count with a syntactic role, so the tests that
matter are the ones that separate populations the token count merged: a reader
from a writer, a same-prefix identifier from the field, prose from an access,
and a computed key from an absent one.
"""

from __future__ import annotations

import ast

import pytest

from loopx.semantics.field_use import (
    ROLES,
    field_use_summary,
    python_dynamic_mapping_keys,
    python_field_forms,
    scan_field_uses,
    typescript_field_forms,
)
from loopx.semantics.inventory import SourceFile

FIELD = "goal_boundary"
FIELDS = frozenset({FIELD})


def python(text: str) -> dict[str, set[str]]:
    return python_field_forms(ast.parse(text), FIELDS)


def source(text: str, suffix: str = ".py", path: str = "loopx/probe") -> SourceFile:
    return SourceFile(path + suffix, suffix, text)


def role(text: str, suffix: str = ".py") -> str:
    uses, _ = scan_field_uses([FIELD], [source(text, suffix)])
    assert len(uses) == 1, uses
    return uses[0].role


@pytest.mark.parametrize("text", [
    'value = payload["goal_boundary"]',
    'value = payload.get("goal_boundary")',
    'value = payload.pop("goal_boundary", None)',
    'present = "goal_boundary" in payload',
    'value = route.goal_boundary',
])
def test_literal_key_reads_are_readers(text: str) -> None:
    assert role(text) == "reader"


@pytest.mark.parametrize("text", [
    'payload["goal_boundary"] = built',
    'payload = {"goal_boundary": built}',
    'emit(goal_boundary=built)',
    'payload.setdefault("goal_boundary", {})',
    'route.goal_boundary = None',
])
def test_literal_key_writes_are_writers(text: str) -> None:
    assert role(text) == "writer"


def test_a_module_that_reads_and_writes_counts_as_a_reader_and_stays_in_the_surface() -> None:
    text = 'def project(payload):\n    payload["goal_boundary"] = payload.get("goal_boundary")\n'
    uses, _ = scan_field_uses([FIELD], [source(text)])
    assert uses[0].reads and uses[0].writes
    assert uses[0].role == "reader" and uses[0].in_migration_surface


@pytest.mark.parametrize("text", [
    'def build(goal_boundary):\n    return goal_boundary\n',
    'goal_boundary = collect()\nreturn goal_boundary\n',
])
def test_named_parameters_and_locals_are_bindings_in_the_migration_surface(text: str) -> None:
    uses, _ = scan_field_uses([FIELD], [source(text)])
    assert uses[0].role == "binding"
    assert uses[0].in_migration_surface, "a signature carrying the field still has to change"


@pytest.mark.parametrize("text", [
    '"""The quota guard publishes goal_boundary for the agent."""',
    '# goal_boundary is described in the should-run docs',
    'note = "read quota.goal_boundary.capabilities before spending"',
])
def test_prose_is_a_mention_and_never_enters_the_migration_surface(text: str) -> None:
    uses, _ = scan_field_uses([FIELD], [source(text)])
    assert uses[0].role == "mention"
    assert not uses[0].in_migration_surface


def test_a_field_name_carried_as_data_is_unresolved_rather_than_absent() -> None:
    text = 'LEGACY = ["goal_boundary", "work_lane_contract"]\nfor field in LEGACY:\n    payload.get(field)\n'
    uses, _ = scan_field_uses([FIELD], [source(text)])
    assert uses[0].role == "unresolved"
    assert "name_constant" in uses[0].forms
    assert not uses[0].in_migration_surface, (
        "an unresolved module is not known to need migration; it is known to be unproven"
    )


def test_the_same_prefix_identifier_is_not_a_use_of_the_field() -> None:
    text = (
        'value = payload["goal_boundary_repair"]\n'
        'other = payload.get("repair_goal_boundary")\n'
        'route.goal_boundary_repair = None\n'
    )
    assert python(text) == {}
    uses, _ = scan_field_uses([FIELD], [source(text)])
    assert uses == [], "goal_boundary_repair must not be counted as a reader of goal_boundary"


def test_computed_keys_are_counted_as_the_standing_unknown() -> None:
    tree = ast.parse('payload.get(name)\npayload.get("goal_boundary")\nrows[index]\npayload.pop(key, None)\n')
    assert python_dynamic_mapping_keys(tree) == 2, (
        "literal keys are attributable and sequence indexing is not a mapping access"
    )


def test_an_unparseable_module_is_recorded_rather_than_dropped() -> None:
    uses, _ = scan_field_uses([FIELD], [source('def broken(:\n    "goal_boundary"\n')])
    assert [use.role for use in uses] == ["mention"]


@pytest.mark.parametrize("text, expected", [
    ("const source = object(payload.goal_boundary);", "reader"),
    ('const source = payload["goal_boundary"];', "reader"),
    ("capsule.goal_boundary = projection;", "writer"),
    ('capsule["goal_boundary"] = projection;', "writer"),
    ("  goal_boundary: JsonObject;", "mention"),
    ('report("decision.goal_boundary", value);', "mention"),
    ("// goal_boundary is projected downstream", "mention"),
    ("const repaired = payload.goal_boundary_repair;", None),
])
def test_typescript_forms_are_classified_by_the_bounded_grammar(text: str, expected: str | None) -> None:
    uses, _ = scan_field_uses([FIELD], [source(text, ".ts")])
    assert [use.role for use in uses] == ([expected] if expected else [])


def test_typescript_string_paths_do_not_become_property_reads() -> None:
    forms = typescript_field_forms('log("decision.goal_boundary");', FIELDS)
    assert forms[FIELD] == {"prose"}


def test_roles_partition_the_token_count_so_the_metric_reclassifies_one_population() -> None:
    sources = [
        source('value = payload["goal_boundary"]', path="loopx/reader"),
        source('payload["goal_boundary"] = built', path="loopx/writer"),
        source('def build(goal_boundary):\n    return goal_boundary\n', path="loopx/binding"),
        source('LEGACY = ["goal_boundary"]', path="loopx/unresolved"),
        source('# goal_boundary', path="loopx/mention"),
        source('value = payload["goal_boundary_repair"]', path="loopx/unrelated"),
    ]
    summary = field_use_summary([FIELD], sources)["fields"][FIELD]
    classified = sum(summary[f"python_{role}_modules"] for role in ROLES)
    assert classified == summary["python_token_modules"] == 5
    assert summary["python_migration_surface"] == 3
