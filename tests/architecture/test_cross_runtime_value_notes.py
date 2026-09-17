"""Per-value meaning ratchet for the ``cross_runtime`` vocabulary tier.

``tests/architecture/test_semantic_vocabulary_drift.py`` already requires a
``value_notes`` entry for every value of the six kernel vocabularies (#4625 for
the four canonical Turn vocabularies, #4626 for ``effective_action`` and
``lease_action``). That ratchet stops at the tier boundary, so the 20
``cross_runtime`` vocabularies could grow a value that no diff ever explains.

This file is the same obligation for the other tier, kept separate on purpose:
the kernel ratchet sits at the end of a file that several open branches already
edit, and a shared tail is where same-diff rules get lost in a merge.

The bar a note has to meet is the one #4625/#4626 set, and it is not "a
sentence exists". A note says **which condition produces the value** — what has
to be true at runtime for the code to choose it. A note that rephrases the
identifier, or that only records what happens next, leaves the reader exactly
where they started: reconstructing control flow from the generated rule table.
That failure mode is worse than an empty note, because the coverage count says
it is covered, so ``test_a_note_must_not_merely_restate_its_own_value`` treats
it as a failure rather than trusting the count.

Where the producing condition genuinely cannot be established from the code,
the honest note is the one the RFC's evidence rules require: say it is
unresolved and say what evidence is missing. Those are spelled
``Unresolved: ... Missing evidence: ...`` so they are countable, and
``UNRESOLVED_BUDGET`` keeps them from quietly becoming the easy default.
"""

from __future__ import annotations

import copy
import re
import runpy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE = REPO_ROOT / "examples" / "semantic-vocabulary-drift-smoke.py"

TIER = "cross_runtime"

# The registry is read through the smoke's own loader, so this ratchet sees the
# same validated shape the drift check does instead of a second JSON reader
# that could disagree with it.
_SMOKE = runpy.run_path(str(SMOKE))
_REGISTRY = _SMOKE["load_registry"]()
_VOCABULARIES = _REGISTRY["vocabularies"]

CROSS_RUNTIME_VOCABULARIES = sorted(
    name for name, entry in _VOCABULARIES.items() if entry["tier"] == TIER
)

# An unresolved note is a legitimate outcome, not a loophole: it must name the
# evidence that would settle the value. The budget is the measurement taken
# when this tier was first documented; it may fall, and it may not rise without
# a diff that says why.
#
# The two are ``settlement_failure_kind.cancelled`` (declared in both owners and
# admitted by the decoders, selected by no branch, exercised only by tests that
# fabricate it) and ``todo_decision_scope_kind.other`` (an accepted member with
# no producer, no fallback, and no documented rule for when an author picks it).
UNRESOLVED_BUDGET = 2

UNRESOLVED_PREFIX = "unresolved:"
MISSING_EVIDENCE_MARKER = "missing evidence:"

# A note is prose, so the restatement check has to ignore the words that carry
# no information about the producing condition.
STOPWORDS = frozenset("""
a an and are as at be been but by can cannot for from has have if in into is it
its no not of on one only or so than that the their then there these this to
under until up was when where which while who why with without
""".split())

_WORD = re.compile(r"[a-z0-9]+")

# A note that says which condition produces a value needs a real sentence. These
# floors are deliberately low: they catch the bare-restatement failure mode, not
# terse-but-substantive prose.
MIN_NOTE_CHARACTERS = 40
MIN_INFORMATIVE_WORDS = 6


def _note(name: str, value: str) -> str:
    return str((_VOCABULARIES[name].get("value_notes") or {}).get(value) or "").strip()


def _informative_words(note: str, *own: str) -> set[str]:
    """Words in ``note`` that are not stopwords and not echoes of the names.

    ``own`` is the value and its vocabulary; a note built only out of those
    tokens has restated the identifier rather than explained it.
    """
    own_tokens = {token for name in own for token in _WORD.findall(name.lower())}
    return {
        word
        for word in _WORD.findall(note.lower())
        if len(word) > 2 and word not in STOPWORDS and word not in own_tokens
    }


def _undocumented(vocabulary: dict) -> list[str]:
    notes = vocabulary.get("value_notes", {})
    return [
        value
        for value in vocabulary["values"]
        if not str(notes.get(value) or "").strip()
    ]


@pytest.mark.parametrize("name", CROSS_RUNTIME_VOCABULARIES)
def test_every_cross_runtime_value_carries_a_note(name: str) -> None:
    """A ``cross_runtime`` value with no note sends every reader back to the code.

    The registry already settles who owns a vocabulary and which values are
    legal. It did not say what any of them mean, so a reader had to recover the
    producing condition from the generated rule table. Requiring the note in the
    diff that adds the value keeps that case reviewable at review time.
    """
    vocabulary = _VOCABULARIES[name]
    undocumented = _undocumented(vocabulary)
    assert not undocumented, f"{name}: values with no value_notes entry: {undocumented}"


def test_a_new_value_without_a_note_fails_the_ratchet() -> None:
    """The ratchet has to bite, not merely pass on a tree that is already clean.

    A green assertion over documented values proves nothing about the diff that
    adds an undocumented one, so the failure path is exercised directly.
    """
    vocabulary = copy.deepcopy(_VOCABULARIES[CROSS_RUNTIME_VOCABULARIES[0]])
    vocabulary["values"].append("probe_value_added_without_a_note")
    assert _undocumented(vocabulary) == ["probe_value_added_without_a_note"]


def test_an_empty_or_whitespace_note_does_not_count_as_coverage() -> None:
    """A present-but-blank note must not satisfy the ratchet."""
    name = CROSS_RUNTIME_VOCABULARIES[0]
    vocabulary = copy.deepcopy(_VOCABULARIES[name])
    value = vocabulary["values"][0]
    for blank in ("", "   ", "\n\t"):
        vocabulary["value_notes"][value] = blank
        assert _undocumented(vocabulary) == [value], blank


@pytest.mark.parametrize("name", CROSS_RUNTIME_VOCABULARIES)
def test_a_note_must_not_merely_restate_its_own_value(name: str) -> None:
    """Coverage that only rephrases the identifier is worse than no coverage.

    ``surface_only: "The outcome is surface only."`` passes a presence check and
    tells a reader nothing, while making the tier look documented. A note has to
    carry words that are not just its own name spelled out.
    """
    vocabulary = _VOCABULARIES[name]
    thin = []
    for value in vocabulary["values"]:
        note = _note(name, value)
        informative = _informative_words(note, value, name)
        if len(note) < MIN_NOTE_CHARACTERS or len(informative) < MIN_INFORMATIVE_WORDS:
            thin.append((value, len(note), sorted(informative)))
    assert not thin, (
        f"{name}: notes that restate the value instead of saying what produces it "
        f"(need >={MIN_NOTE_CHARACTERS} chars and >={MIN_INFORMATIVE_WORDS} words that are "
        f"not the value's own name): {thin}"
    )


@pytest.mark.parametrize("name", CROSS_RUNTIME_VOCABULARIES)
def test_an_unresolved_note_must_name_the_missing_evidence(name: str) -> None:
    """"Unresolved" is an allowed answer only when it says what would settle it.

    The RFC's evidence rules forbid inventing a meaning to fill the table. They
    equally forbid an unresolved marker that is just a shrug: the note has to
    name the evidence whose absence blocks the reading, so a later diff knows
    what to go and find.
    """
    vocabulary = _VOCABULARIES[name]
    unnamed = []
    for value in vocabulary["values"]:
        note = _note(name, value).lower()
        if note.startswith(UNRESOLVED_PREFIX) and MISSING_EVIDENCE_MARKER not in note:
            unnamed.append(value)
    assert not unnamed, (
        f"{name}: unresolved notes must say what evidence is missing, spelled "
        f"'Missing evidence: ...': {unnamed}"
    )


def test_unresolved_values_stay_within_their_budget() -> None:
    """Unresolved must not drift into being the cheap default.

    The budget is a measurement, so it discloses slack the way the inventory
    ratchets do: if the real count has fallen below the pin, the pin is stale
    and the message says by how much.
    """
    unresolved = sorted(
        f"{name}.{value}"
        for name in CROSS_RUNTIME_VOCABULARIES
        for value in _VOCABULARIES[name]["values"]
        if _note(name, value).lower().startswith(UNRESOLVED_PREFIX)
    )
    assert len(unresolved) <= UNRESOLVED_BUDGET, (
        f"unresolved cross_runtime values grew past the budget "
        f"{UNRESOLVED_BUDGET}: {unresolved}"
    )
    slack = UNRESOLVED_BUDGET - len(unresolved)
    assert slack == 0, (
        f"UNRESOLVED_BUDGET is stale by {slack}; lower it to {len(unresolved)} "
        f"in the diff that resolved the values"
    )


def test_the_two_tier_ratchets_together_cover_every_registered_vocabulary() -> None:
    """No value may fall between the kernel ratchet and this one.

    The kernel tier is covered by ``test_semantic_vocabulary_drift.py`` and this
    tier by the parametrization above. ``TIERS`` in the smoke also admits
    ``cross_module``, so a vocabulary registered under a third tier would carry
    no per-value obligation at all. It fails here until someone extends one of
    the two ratchets to reach it.
    """
    covered = {
        name
        for name, entry in _VOCABULARIES.items()
        if entry["tier"] in {"kernel", TIER}
    }
    uncovered = sorted(set(_VOCABULARIES) - covered)
    assert not uncovered, (
        "vocabularies in a tier no per-value ratchet walks: "
        f"{[(name, _VOCABULARIES[name]['tier']) for name in uncovered]}"
    )


def test_the_parametrized_population_is_derived_from_the_registry() -> None:
    """The ratchet's population must be counted, never typed in.

    A hand-listed set of vocabulary names is the failure this whole file exists
    to prevent: a new ``cross_runtime`` vocabulary would be outside the list and
    the tier would look covered.
    """
    assert CROSS_RUNTIME_VOCABULARIES == sorted(
        name for name, entry in _VOCABULARIES.items() if entry["tier"] == TIER
    )
    assert CROSS_RUNTIME_VOCABULARIES, "the cross_runtime tier is not empty"
