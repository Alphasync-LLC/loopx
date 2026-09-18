"""Counterexamples for the bounded binding forms the producer scan recognizes.

Each form here narrows an ``unresolved`` blocker, so every one needs a negative
twin: a site the scan must keep unresolved rather than call dead. Shrinking the
residue by loosening the rule is the failure this file is meant to catch.
"""
from __future__ import annotations

import ast
import time

import pytest

from loopx.semantics.inventory import SourceFile
from loopx.semantics.python_production import scan_python_production

OWNER = 'loopx/quota/owner.py::Action'
ENUMS = {OWNER: {'RUN': 'run', 'WAIT': 'wait'}}
CONSUMER = 'loopx/quota/client.py'


def scan(text, *, returns=(), paths=None, calls=None, field='action', enums=ENUMS):
    return scan_python_production(SourceFile(CONSUMER, '.py', text), field=field, enums=enums,
                                  return_functions=frozenset(returns), return_paths=paths,
                                  call_arguments=calls)


def known(rows):
    return set().union(*(row.values for row in rows if row.form != 'keyword_unproved'))


def blockers(rows):
    return {row.blocker for row in rows if row.unresolved}


def at(rows, scope):
    """Only the consumer's own rows; a helper's own returns are its evidence."""
    return [row for row in rows if row.site == f'{CONSUMER}::{scope}']


# --- same-module call results -------------------------------------------------


def test_same_module_call_resolves_to_the_callee_own_returns():
    rows = scan('def pick(flag):\n return "run" if flag else "wait"\n'
                'def emit():\n return {"action": pick(True)}\n')
    assert known(rows) == {'run', 'wait'}
    assert not any(row.unresolved for row in rows)


def test_same_module_call_keeps_the_callee_unknown_portion():
    """A bound call reports the callee's own reason, not a blanket call_result."""
    rows = scan('def pick(flag):\n return "run" if flag else dynamic()\n'
                'def emit():\n return {"action": pick(True)}\n')
    assert known(rows) == {'run'}
    assert blockers(rows) == {'call_result'}


def test_call_arguments_are_never_bound_to_callee_parameters():
    """A returned parameter stays unknown however literal the argument is."""
    rows = scan('def pick(choice):\n return choice\n'
                'def emit():\n return {"action": pick("run")}\n')
    assert known(rows) == set()
    assert blockers(rows) == {'unstable_local'}


def test_enum_object_returned_by_a_same_module_call_supplies_value():
    rows = scan('from .owner import Action\ndef pick():\n return Action.RUN\n'
                'def emit():\n choice = pick()\n return {"action": choice.value}\n')
    assert known(rows) == {'run'}
    assert not any(row.unresolved for row in rows)


def test_serialized_result_is_not_an_enum_object_with_a_value_attribute():
    rows = at(scan('from .owner import Action\ndef pick():\n return Action.RUN.value\n'
                   'def emit():\n choice = pick()\n return {"action": choice.value}\n'), 'emit')
    assert known(rows) == set()
    assert blockers(rows) == {'serialized_value'}


@pytest.mark.parametrize('definition, reason', [
    # A decorator can replace the returned object entirely.
    ('@wrap\ndef pick():\n return "run"\n', 'call_result'),
    # await of a coroutine is a different expression; a bare call is not the value.
    ('async def pick():\n return "run"\n', 'call_result'),
    # A generator yields; the call returns the iterator, not a member.
    ('def pick():\n yield "run"\n', 'call_result'),
    # A second top-level binding takes the name away from the definition.
    ('def pick():\n return "run"\npick = other\n', 'call_result'),
    ('def pick():\n return "run"\nfrom .elsewhere import pick\n', 'call_result'),
])
def test_unbindable_definitions_keep_the_site_unresolved(definition, reason):
    rows = scan(definition + 'def emit():\n return {"action": pick()}\n')
    assert known(rows) == set()
    assert blockers(rows) == {reason}


def test_imported_and_attribute_calls_are_not_same_module_definitions():
    rows = scan('from .elsewhere import pick\nimport helper\n'
                'def emit():\n return {"action": pick(), "other": helper.pick()}\n')
    assert known(rows) == set()
    assert blockers(rows) == {'call_result'}


def test_locally_rebound_name_does_not_borrow_the_module_definition():
    rows = scan('def pick():\n return "run"\n'
                'def emit(pick):\n return {"action": pick()}\n')
    assert known(rows) == set()
    assert blockers(rows) == {'call_result'}


def test_recursive_call_chain_terminates_and_stays_unresolved():
    rows = scan('def left():\n return right()\ndef right():\n return left()\n'
                'def emit():\n return {"action": left()}\n')
    assert known(rows) == set()
    assert blockers(rows) == {'call_result'}


def test_a_callee_that_only_raises_produces_no_value_and_no_blocker():
    rows = scan('def pick():\n raise ValueError("no route")\n'
                'def emit():\n return {"action": pick()}\n')
    assert known(rows) == set()
    assert not any(row.unresolved for row in rows)


# --- ordered rebinding of a local --------------------------------------------


def test_rebound_local_unions_the_writes_that_precede_the_read():
    rows = scan('from .owner import Action\ndef emit(flag):\n choice = Action.RUN.value\n'
                ' if flag:\n  choice = Action.WAIT.value\n return {"action": choice}\n')
    assert known(rows) == {'run', 'wait'}
    assert not any(row.unresolved for row in rows)


def test_a_write_after_the_read_is_not_a_definition_for_that_read():
    rows = scan('from .owner import Action\ndef emit(flag):\n choice = Action.RUN.value\n'
                ' packet = {"action": choice}\n choice = Action.WAIT.value\n return packet\n')
    assert known(rows) == {'run'}
    assert not any(row.unresolved for row in rows)


def test_a_rebound_local_keeps_its_unknown_arm_visible():
    rows = scan('from .owner import Action\ndef emit(flag):\n choice = Action.RUN.value\n'
                ' if flag:\n  choice = dynamic()\n return {"action": choice}\n')
    assert known(rows) == {'run'}
    assert blockers(rows) == {'call_result'}


@pytest.mark.parametrize('rebind', [
    'for choice in options: pass',
    'with opened() as choice: pass',
    'choice += suffix',
    'choice, extra = pair()',
    'del choice',
    'print(choice := dynamic())',
])
def test_stores_this_scan_cannot_order_leave_the_local_unknown(rebind):
    """Only a plain ``name = expression`` is an ordered write; nothing else is."""
    rows = scan('from .owner import Action\ndef emit():\n choice = Action.RUN.value\n '
                + rebind + '\n return {"action": choice}\n')
    assert known(rows) == set()
    assert blockers(rows) == {'unstable_local'}


def test_a_global_declaration_takes_the_name_out_of_this_scope():
    rows = scan('from .owner import Action\ndef emit():\n global choice\n'
                ' choice = Action.RUN.value\n return {"action": choice}\n')
    assert known(rows) == set()
    assert blockers(rows) == {'unstable_local'}


# --- key-precise container writes --------------------------------------------


def test_untouched_keys_survive_a_literal_key_write():
    rows = scan('from .owner import Action\ndef emit(flag):\n'
                ' packet = {"action": Action.RUN.value, "note": ""}\n'
                ' if flag:\n  packet["note"] = "changed"\n return packet\n',
                returns=['emit'], paths={'emit': ('action',)})
    assert known(rows) == {'run'}
    assert not any(row.unresolved for row in rows)


def test_a_written_key_carries_every_contributing_write():
    rows = scan('from .owner import Action\ndef emit(flag):\n'
                ' packet = {"action": Action.RUN.value}\n'
                ' if flag:\n  packet["action"] = Action.WAIT.value\n return packet\n',
                returns=['emit'], paths={'emit': ('action',)})
    assert known(rows) == {'run', 'wait'}
    assert not any(row.unresolved for row in rows)


def test_a_key_supplied_only_by_a_write_is_not_an_unknown_boundary():
    rows = scan('from .owner import Action\ndef emit():\n packet = {}\n'
                ' packet["action"] = Action.RUN.value\n return packet\n',
                returns=['emit'], paths={'emit': ('action',)})
    assert known(rows) == {'run'}
    assert not any(row.unresolved for row in rows)


def test_an_unresolved_write_to_the_read_key_stays_unresolved():
    rows = scan('from .owner import Action\ndef emit(flag):\n'
                ' packet = {"action": Action.RUN.value}\n'
                ' if flag:\n  packet["action"] = dynamic()\n return packet\n',
                returns=['emit'], paths={'emit': ('action',)})
    assert known(rows) == {'run'}
    assert blockers(rows) == {'call_result'}


@pytest.mark.parametrize('mutation', [
    # A second name could carry a write this key map never sees.
    'alias = packet\n alias["action"] = dynamic()',
    # A computed key could land on any key at all.
    'packet[key()] = dynamic()',
    # A deeper store is not a write to a key of this container.
    'packet["action"]["kind"] = dynamic()',
    # A method or an escape can rewrite the whole container.
    'packet.update(other)',
    'consume(packet)',
    'del packet["action"]',
])
def test_writes_outside_the_recognized_form_discard_the_container(mutation):
    rows = [row for row in scan('from .owner import Action\ndef emit():\n'
                                ' packet = {"action": Action.RUN.value}\n ' + mutation + '\n return packet\n',
                                returns=['emit'], paths={'emit': ('action',)}) if row.form == 'return']
    assert known(rows) == set()
    assert rows and all(row.unresolved for row in rows)


# --- dict literal spreads -----------------------------------------------------


def test_a_spread_of_known_literals_does_not_hide_a_sibling_key():
    rows = scan('from .owner import Action\ndef emit(flag):\n'
                ' packet = {"action": Action.RUN.value, **({"note": "x"} if flag else {})}\n'
                ' return packet\n', returns=['emit'], paths={'emit': ('action',)})
    assert known(rows) == {'run'}
    assert not any(row.unresolved for row in rows)


def test_a_spread_that_may_carry_the_key_keeps_both_possibilities():
    rows = scan('from .owner import Action\ndef emit(flag):\n'
                ' packet = {"action": Action.RUN.value, **({"action": Action.WAIT.value} if flag else {})}\n'
                ' return packet\n', returns=['emit'], paths={'emit': ('action',)})
    assert known(rows) == {'run', 'wait'}
    assert not any(row.unresolved for row in rows)


@pytest.mark.parametrize('spread', ['**overrides', '**dict(overrides)', '**{key(): "x"}'])
def test_an_unknown_spread_could_overwrite_any_key(spread):
    rows = scan('from .owner import Action\ndef emit(overrides):\n'
                ' packet = {"action": Action.RUN.value, ' + spread + '}\n return packet\n',
                returns=['emit'], paths={'emit': ('action',)})
    assert blockers(rows) == {'dynamic_key'}


# --- the residue stays honest -------------------------------------------------


def test_an_unbound_site_is_unresolved_and_never_silently_dropped():
    """No recognized producer means unresolved; it never means dead."""
    rows = scan('def emit(payload):\n return {"action": payload.get("action")}\n')
    assert len(rows) == 1
    assert rows[0].unresolved and rows[0].blocker == 'call_result'
    assert rows[0].values == frozenset()


def test_every_recognized_form_still_labels_what_it_could_not_bind():
    rows = scan('from .owner import Action\ndef pick(flag):\n return Action.RUN.value if flag else late()\n'
                'def emit(flag):\n packet = {"action": pick(flag)}\n'
                ' packet["note"] = dynamic()\n return packet\n',
                returns=['emit'], paths={'emit': ('action',)})
    assert known(at(rows, 'emit')) == {'run'}
    assert all(row.blocker for row in rows if row.unresolved)


def test_deep_call_chains_stay_bounded():
    """The memo and the recursion guard keep a long chain linear, not explosive."""
    depth = 60
    text = 'def step0():\n return "run"\n'
    text += ''.join(f'def step{i}():\n return step{i - 1}() or step{i - 1}()\n'
                    for i in range(1, depth))
    text += f'def emit():\n return {{"action": step{depth - 1}()}}\n'
    started = time.perf_counter()
    rows = scan(text)
    assert known(rows) == {'run'}
    assert time.perf_counter() - started < 5.0


def test_synthetic_selection_nodes_never_enter_the_shared_tree():
    """Rebinding folds a union for the read only; the parsed tree is untouched."""
    text = ('from .owner import Action\ndef emit(flag):\n choice = Action.RUN.value\n'
            ' if flag:\n  choice = Action.WAIT.value\n return {"action": choice}\n')
    source = SourceFile(CONSUMER, '.py', text)
    first = scan_python_production(source, field='action', enums=ENUMS)
    before = ast.dump(ast.parse(text))
    second = scan_python_production(source, field='action', enums=ENUMS)
    assert first == second
    assert ast.dump(ast.parse(text)) == before


# A write that textually follows a read still reaches it when a loop carries
# control back. The preceding-writes filter reads file position as execution
# order, so without these the scan reports the value that happens to appear
# first and marks the site fully resolved -- the one failure mode that turns an
# unknown into wrong evidence. F1 would then pass over a producer that emits an
# unregistered value on every iteration after the first.
@pytest.mark.parametrize('text', [
    # for-loop back edge: iteration 2 emits 'leaked'
    'def build(rows):\n'
    '    chosen = "run"\n'
    '    for row in rows:\n'
    '        emit({"action": chosen})\n'
    '        chosen = "leaked"\n',
    # while-loop back edge
    'def build(rows):\n'
    '    chosen = "run"\n'
    '    while rows:\n'
    '        emit({"action": chosen})\n'
    '        chosen = "leaked"\n'
    '        rows = rows[1:]\n',
    # the carrying write sits in the outer loop, the read in the inner one
    'def build(rows):\n'
    '    chosen = "run"\n'
    '    for row in rows:\n'
    '        for inner in row:\n'
    '            emit({"action": chosen})\n'
    '        chosen = "leaked"\n',
    # finally runs after the read and feeds the next iteration
    'def build(rows):\n'
    '    chosen = "run"\n'
    '    for row in rows:\n'
    '        try:\n'
    '            emit({"action": chosen})\n'
    '        finally:\n'
    '            chosen = "leaked"\n',
])
def test_a_loop_back_edge_leaves_the_local_unordered(text):
    rows = [row for row in scan(text) if row.form == 'dict']
    assert rows, 'the dict write must still be observed'
    assert all(row.unresolved for row in rows), (
        'a write the back edge carries past the read makes the writes unorderable; '
        'reporting only the textually earlier value states a closed value set that is not closed'
    )
    assert blockers(rows) == {'unstable_local'}
    assert 'leaked' not in known(rows)


def test_a_straight_line_rebinding_still_resolves():
    """The back-edge rule must not retract the ordering it was built for.

    Without a loop the preceding-writes filter is execution order, so a local
    written twice before the read is still a finite selection.
    """
    rows = [row for row in scan(
        'def build(flag):\n'
        '    chosen = "run"\n'
        '    if flag:\n'
        '        chosen = "wait"\n'
        '    return {"action": chosen}\n',
    ) if row.form == 'dict']
    assert known(rows) == {'run', 'wait'} and not any(row.unresolved for row in rows)


def test_a_single_write_inside_a_loop_is_still_its_only_value():
    """One plain store is the only value a read can see, back edge or not."""
    rows = [row for row in scan(
        'def build(rows):\n'
        '    for row in rows:\n'
        '        chosen = "run"\n'
        '        emit({"action": chosen})\n',
    ) if row.form == 'dict']
    assert known(rows) == {'run'} and not any(row.unresolved for row in rows)


def test_a_negative_index_store_discards_the_container():
    """``table[-1]`` names a slot whose number depends on the length.

    Recording it against the key ``-1`` leaves a read of ``table[0]`` looking at
    the untouched initializer, so a one-element list reports the value the write
    replaced and calls the site resolved.
    """
    rows = [row for row in scan(
        'def build():\n'
        '    table = ["run"]\n'
        '    table[-1] = "leaked"\n'
        '    return {"action": table[0]}\n',
    ) if row.form == 'dict']
    assert rows and all(row.unresolved for row in rows)
    assert 'run' not in known(rows), 'the initializer was overwritten by the negative store'


def test_a_non_negative_index_store_still_carries_its_key():
    """The negative-index rule must not discard the key map it was built on.

    A written key carries the union of its initializer and the write, which is
    this scan's documented answer: it reports syntactic possibilities, not the
    one value a flow-sensitive reading would pick. What matters here is that the
    site stays resolved and the write is visible, both of which the discard path
    would have taken away.
    """
    rows = [row for row in scan(
        'def build():\n'
        '    table = ["run"]\n'
        '    table[0] = "wait"\n'
        '    return {"action": table[0]}\n',
    ) if row.form == 'dict']
    assert known(rows) == {'run', 'wait'} and not any(row.unresolved for row in rows)


def test_a_module_scope_back_edge_is_unordered_too():
    """The carve-out must hold outside a function body.

    The scope table is built per scope, so a module-level loop is a separate
    path through the same rule and needs its own negative fixture.
    """
    rows = [row for row in scan(
        'chosen = "run"\n'
        'for row in rows:\n'
        '    emit({"action": chosen})\n'
        '    chosen = "leaked"\n',
    ) if row.form == 'dict']
    assert rows and all(row.unresolved for row in rows)
    assert blockers(rows) == {'unstable_local'}


def test_a_nested_generator_does_not_make_its_enclosing_function_one():
    """``ast.walk`` descends into nested defs; a containing function is not a generator.

    The direction was safe -- the call kept ``call_result`` -- but it withheld
    evidence this slice exists to make actionable.
    """
    rows = at(scan(
        'from loopx.quota.owner import Action\n'
        'def choose():\n'
        '    def stream():\n'
        '        yield 1\n'
        '    return Action.RUN.value\n'
        'def emit():\n'
        '    return {"action": choose()}\n',
    ), 'emit')
    assert known(rows) == {'run'} and not any(row.unresolved for row in rows)


def test_a_function_that_yields_itself_is_still_not_bound():
    rows = at(scan(
        'from loopx.quota.owner import Action\n'
        'def choose():\n'
        '    yield Action.RUN.value\n'
        'def emit():\n'
        '    return {"action": choose()}\n',
    ), 'emit')
    assert blockers(rows) == {'call_result'}
