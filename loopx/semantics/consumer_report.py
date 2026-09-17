"""Advisory consumer evidence for a registered vocabulary (RFC B5).

The existing ``consumer_ranking`` counts modules that *mention* a symbol. That
number orders retirement work, but it classifies no role and proves no data
flow: a prompt string, a comment and a dispatch table all count the same. This
module answers the next question with bounded AST evidence -- for one registered
vocabulary, which sites **read** its value, which only **pass it through**, which
**interpret** it by branching, and which stay **unknown** with a recorded reason.

**What this measures is syntactic use, not data flow.** Nothing here traces a
value from a producer to a consumer. A row says "this location performs a
recognized read of this vocabulary's slot, and the recognized syntax around that
read forwards it / branches on it / does neither". It does not say the value
actually observed at runtime came from a registered producer, nor that the
branch is reachable. Data-flow proof would need interprocedural analysis this
module deliberately does not attempt, and the ``limitation`` column on every row
says which gap applies to that row rather than leaving the reader to guess.

Roles follow the RFC hierarchy, where interpreter and pass-through are consumer
subroles rather than a partition of whole modules. A transformer that reads one
vocabulary and emits another is an interpreter *of the vocabulary it reads*;
the same module can be a plain consumer of a second vocabulary in the next
function. Rows are therefore per site and per vocabulary, never per module, and
a site carrying both a branch and a forward is reported as ``interpret``,
the stronger of the two claims.

Anchors come from identities the registry already carries -- the B2 producer and
slot work is the precondition -- so no module has to register itself as a
consumer and no new blanket registration exists:

* **slot read** -- a literal-key read of the vocabulary's slot name, which is
  ``literal_scan.field`` when the registry declares one and otherwise the
  vocabulary id: ``payload["example_slot"]``, ``payload.get("example_slot")``,
  ``record.example_slot``, ``"example_slot" in payload``.
* **owner member** -- a comparison or ``match`` case against a member of the
  registered owner class, resolved through the same one-unrenamed-hop import
  discipline the producer scanner uses. The operand on the other side is being
  interpreted even when the slot name never appears.

Four limits are part of the metric rather than caveats beside it:

* **The slot is keyed by name.** A carrier of the same vocabulary under a
  different field name is not found, and an unrelated field that happens to
  share the name is misattributed. Every slot-read row carries that limitation.
* **A computed mapping key is unknown, not absent.** ``payload.get(name)`` may
  read any slot, so no name-keyed scan can prove a vocabulary has no reader.
  Those sites are reported as ``unknown`` rows against every vocabulary at once.
  Computed *subscripts* are deliberately excluded: ``rows[index]`` and
  ``payload[key]`` are the same syntax, and counting sequence indexing would
  inflate the unknown until it stopped carrying information.
* **Following a local is one hop.** A read bound to a single-assignment,
  unshadowed local is classified by that local's uses. A parameter, a reassigned
  name, a name that escapes into a nested scope, or a second alias hop is
  ``unknown`` with the reason recorded, never a silent drop.
* **TypeScript is not walked.** There is no TypeScript AST here, so a tracked
  ``.ts`` file carrying the slot token is reported as one ``unknown`` row rather
  than omitted from the reach.

Nothing in this module gates anything. It is advisory evidence printed on
demand by ``scripts/generate_semantic_inventory.py --report``, matching F3's
``advisory`` lane in the formal model, and it must not become a merge gate
without the RFC decision that would license one.
"""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping

from .inventory import SourceFile
from .python_production import _qualified_bindings, enum_members

# Module-private names on purpose: a module-level ``NAME = (...)`` of string
# literals is itself an inventory carrier, and this module must not add a
# closed-set carrier to the tree it measures.

# The scan reach is code owned, exactly as PRODUCER_ROOTS is. Registry data
# cannot widen it, so a vocabulary cannot buy coverage with a data-only edit.
# These are the representative paths: the control plane where kernel values are
# decided and the CLI surface that renders them.
CONSUMER_SCAN_ROOTS = ('loopx/control_plane', 'loopx/cli_commands')

_ROLES = ('read', 'interpret', 'pass_through', 'unknown')
# Precedence when one anchor supports more than one claim. Interpreting is the
# stronger statement about the value, so a site that branches and also forwards
# is an interpreter; a site that only forwards is a pass-through.
_ROLE_RANK = {'interpret': 3, 'pass_through': 2, 'read': 1}

# Mapping accessors whose first argument names a slot. Unlike a subscript,
# these are unambiguously mapping reads, so a computed argument is real
# evidence of an unresolved read rather than an indexing false positive.
_MAPPING_READS = frozenset({'get', 'pop'})

# Wildcard vocabulary id for a site that may read any registered slot.
ANY_VOCABULARY = '*'

_LIMITATIONS = {
    'read': 'slot_name_keyed: a recognized read of this slot name; no proof the value came from a registered producer',
    'interpret': 'branch_operands_only: the compared literals are syntactic; unmatched values take default paths this scan does not enumerate',
    'pass_through': 'forward_target_untraced: the receiving site is not followed, so the value is not proved to stay in the domain',
    'unknown': 'no_classification: recorded so the site stays visible; it is not evidence of absence',
}


@dataclass(frozen=True)
class ConsumerSite:
    """One classified site. ``blocker`` is set only when ``role`` is unknown."""

    vocabulary: str
    site: str
    line: int
    role: str
    anchor: str
    domain: tuple[str, ...]
    observed: tuple[str, ...]
    limitation: str
    blocker: str | None = None


@dataclass(frozen=True)
class ConsumerEvidence:
    """A whole scan, with the tree it ran against and the reach it covered."""

    source_sha: str
    worktree_dirty: bool
    scanned_files: int
    tracked_files: int
    skipped_typescript: int
    rows: tuple[ConsumerSite, ...]

    def counts(self) -> dict[str, int]:
        tally = Counter(row.role for row in self.rows)
        return {role: tally.get(role, 0) for role in _ROLES}

    def unknown_share(self) -> float:
        return (self.counts()['unknown'] / len(self.rows)) if self.rows else 0.0

    def blockers(self) -> dict[str, int]:
        return dict(sorted(Counter(row.blocker for row in self.rows if row.blocker).items()))


def source_revision(repo_root: Path) -> tuple[str, bool]:
    """The commit the scan ran against, and whether the scanned tree differs.

    ``load_sources`` lists paths from the git index but reads their text from
    the working tree, so a row's location is only reproducible at this commit
    when the tree is clean. A dirty tree is reported, never hidden.
    """
    def git(*arguments: str) -> str:
        return subprocess.run(['git', *arguments], cwd=repo_root, check=True,
                              stdout=subprocess.PIPE).stdout.decode('utf-8').strip()

    try:
        sha = git('rev-parse', 'HEAD')
        dirty = bool(git('status', '--porcelain', '--', *CONSUMER_SCAN_ROOTS))
    except (subprocess.CalledProcessError, OSError):
        return 'unknown', True
    return sha, dirty


def slot_name(name: str, vocabulary: Mapping[str, Any]) -> str:
    """The payload key this vocabulary travels under, from registry identity."""
    return vocabulary.get('literal_scan', {}).get('field') or name


def _in_reach(path: str) -> bool:
    return any(path == root or path.startswith(root + '/') for root in CONSUMER_SCAN_ROOTS)


def _owner_members(vocabulary: Mapping[str, Any], by_path: Mapping[str, SourceFile]) -> dict[str, dict[str, str]]:
    owner = (vocabulary.get('owners') or {}).get('python')
    if not owner or '::' not in owner:
        return {}
    module, symbol = owner.split('::')
    if module not in by_path or by_path[module].suffix != '.py':
        return {}
    try:
        return {owner: enum_members(by_path[module], symbol)}
    except ValueError:
        # An owner this scan cannot read is not an excuse to claim coverage.
        return {}


_TREES: dict[tuple[str, int], ast.Module] = {}


def _parsed(source: SourceFile) -> ast.Module:
    """One parse per source text, reused across every registered vocabulary.

    Keyed by path and text hash, so an edited file is a different key and can
    never be classified from a stale tree.
    """
    key = (source.path, hash(source.text))
    tree = _TREES.get(key)
    if tree is None:
        tree = _TREES[key] = ast.parse(source.text, filename=source.path)
    return tree


_SCOPES: dict[tuple[str, int], list[_Scope]] = {}


def _parents(nodes: Iterable[ast.AST]) -> dict[int, ast.AST]:
    table: dict[int, ast.AST] = {}
    for node in nodes:
        for child in ast.iter_child_nodes(node):
            table[id(child)] = node
    return table


@dataclass
class _Scope:
    name: str
    nodes: list[ast.AST]
    nested: list[ast.AST]
    parents: dict[int, ast.AST]
    assigned: Counter
    parameters: set[str]


def _scopes(tree: ast.Module) -> list[_Scope]:
    """Split a module into scopes, each holding only its own statements.

    Nested functions, classes and lambdas are separate scopes; their bodies are
    kept so a name that escapes into one can be detected rather than mistaken
    for an unused local.
    """
    scopes: list[_Scope] = []

    def walk(body: list[ast.stmt], name: str, parameters: set[str]) -> None:
        nodes: list[ast.AST] = []
        nested: list[ast.AST] = []

        def collect(node: ast.AST) -> None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                nested.append(node)
                return
            nodes.append(node)
            for child in ast.iter_child_nodes(node):
                collect(child)

        for statement in body:
            collect(statement)
        assigned = Counter(n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
        scopes.append(_Scope(name, nodes, nested, _parents(nodes), assigned, parameters))
        for child in nested:
            if isinstance(child, ast.Lambda):
                continue
            inner = name + '.' + child.name if name != '<module>' else child.name
            params: set[str] = set()
            if not isinstance(child, ast.ClassDef):
                arguments = child.args
                params = {a.arg for a in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)}
                params.update(a.arg for a in (arguments.vararg, arguments.kwarg) if a)
            walk(child.body, inner, params)

    walk(tree.body, '<module>', set())
    return scopes


def _module_scopes(source: SourceFile) -> list[_Scope]:
    key = (source.path, hash(source.text))
    scopes = _SCOPES.get(key)
    if scopes is None:
        scopes = _SCOPES[key] = _scopes(_parsed(source))
    return scopes


def _literal_strings(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Constant):
        return {node.value} if isinstance(node.value, str) else set()
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return set().union(*(_literal_strings(item) for item in node.elts), set())
    if isinstance(node, ast.MatchValue):
        return _literal_strings(node.value)
    if isinstance(node, ast.MatchOr):
        return set().union(*(_literal_strings(p) for p in node.patterns), set())
    return set()


def _classify_use(node: ast.AST, scope: _Scope) -> tuple[str | None, set[str], str | None]:
    """Walk syntactic parents of one use; return role, named literals, local.

    A ``None`` role means the surrounding syntax is outside the recognized
    grammar. The third element is the plain local name the climb ended at, if
    any, so the caller can spend its single hop on that name's own uses.
    """
    observed: set[str] = set()
    role: str | None = None
    current = node
    for _ in range(12):  # A finite climb; a deeper nesting stays unclassified.
        parent = scope.parents.get(id(current))
        if parent is None:
            break
        if isinstance(parent, ast.Attribute) and parent.attr == 'value' and parent.value is current:
            # Unwrapping an enum member to its string does not change meaning;
            # keep climbing so the row is classified by what consumes the
            # string. Any other attribute of the read is a different field and
            # ends the climb rather than being attributed to this slot.
            current = parent
            continue
        if isinstance(parent, ast.Compare):
            for operand in (parent.left, *parent.comparators):
                if operand is not current:
                    observed |= _literal_strings(operand)
            role = 'interpret'
            break
        if isinstance(parent, ast.Match) and parent.subject is current:
            for case in parent.cases:
                observed |= _literal_strings(case.pattern)
            role = 'interpret'
            break
        if isinstance(parent, (ast.If, ast.While, ast.Assert)) and getattr(parent, 'test', None) is current:
            role = 'interpret'
            break
        if isinstance(parent, ast.IfExp) and parent.test is current:
            role = 'interpret'
            break
        if isinstance(parent, ast.Subscript) and parent.slice is current:
            # The value selects an entry of another mapping: one vocabulary
            # read as the key into another, which is interpretation.
            role = 'interpret'
            break
        if isinstance(parent, ast.Return):
            role = _stronger(role, 'pass_through')
            break
        if isinstance(parent, ast.Dict) and current in parent.values:
            role = _stronger(role, 'pass_through')
            break
        if isinstance(parent, (ast.Assign, ast.AnnAssign)) and parent.value is current:
            targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
            if any(isinstance(t, (ast.Subscript, ast.Attribute)) for t in targets):
                # A store into a payload or an object forwards the value out.
                return _stronger(role, 'pass_through'), observed, None
            if len(targets) == 1 and isinstance(targets[0], ast.Name):
                return role, observed, targets[0].id
            break
        if isinstance(parent, ast.Call) and current is not parent.func:
            role = _stronger(role, 'pass_through')
        elif isinstance(parent, (ast.FormattedValue, ast.JoinedStr)):
            role = _stronger(role, 'pass_through')
        elif isinstance(parent, ast.Expr):
            role = _stronger(role, 'read')
            break
        elif not isinstance(parent, (ast.BoolOp, ast.UnaryOp, ast.Tuple, ast.List, ast.Set,
                                     ast.keyword, ast.Starred, ast.IfExp, ast.Await)):
            break
        current = parent
    return role, observed, None


def _stronger(current: str | None, candidate: str) -> str:
    return candidate if current is None or _ROLE_RANK[candidate] > _ROLE_RANK[current] else current


def _escapes(name: str, scope: _Scope) -> bool:
    return any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)
               for child in scope.nested for n in ast.walk(child))


def _classify_anchor(node: ast.AST, scope: _Scope) -> tuple[str, set[str], str | None]:
    """Classify one anchor expression, spending at most one local hop.

    A blocker is returned only when the climb produced no role of its own. A
    read that is serialized into an unstable local has already shown a
    pass-through; losing that to the local's instability would understate what
    was actually observed.
    """
    role, observed, name = _classify_use(node, scope)

    def settle(blocker: str) -> tuple[str, set[str], str | None]:
        return (role, observed, None) if role is not None else ('unknown', observed, blocker)

    if name is None:
        return settle('unclassified_context')
    if name in scope.parameters or scope.assigned[name] != 1:
        return settle('unstable_local')
    if _escapes(name, scope):
        return settle('nested_scope_escape')
    uses = [n for n in scope.nodes
            if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)]
    if not uses:
        # Bound and never read again: a real read, and nothing more than that.
        return _stronger(role, 'read'), observed, None
    resolved = role
    for use in uses:
        used_role, named, next_name = _classify_use(use, scope)
        observed |= named
        if used_role is None:
            # A second alias hop would be needed; one hop is the stated bound.
            return settle('alias_chain' if next_name else 'unclassified_context')
        resolved = _stronger(resolved, used_role)
    return resolved or 'read', observed, None


def _slot_anchors(scope: _Scope, slot: str) -> list[ast.AST]:
    anchors: list[ast.AST] = []
    for node in scope.nodes:
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
            if isinstance(node.slice, ast.Constant) and node.slice.value == slot:
                anchors.append(node)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and node.attr == slot:
            anchors.append(node)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr in _MAPPING_READS and node.args
              and isinstance(node.args[0], ast.Constant) and node.args[0].value == slot):
            anchors.append(node)
    return anchors


def _membership_anchors(scope: _Scope, slot: str) -> list[ast.AST]:
    """``"slot" in payload`` proves the module checks for the slot's presence."""
    return [node for node in scope.nodes
            if isinstance(node, ast.Compare)
            and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops)
            and isinstance(node.left, ast.Constant) and node.left.value == slot]


def _owner_anchors(scope: _Scope, members: Mapping[str, str], bound: set[str]) -> list[tuple[ast.AST, set[str]]]:
    """Comparisons and match cases naming a member of the bound owner class."""
    def member_values(node: ast.AST) -> set[str]:
        if isinstance(node, ast.Attribute) and node.attr == 'value':
            return member_values(node.value)
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id in bound and node.attr in members):
            return {members[node.attr]}
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return set().union(*(member_values(item) for item in node.elts), set())
        if isinstance(node, ast.MatchValue):
            return member_values(node.value)
        if isinstance(node, ast.MatchOr):
            return set().union(*(member_values(p) for p in node.patterns), set())
        return set()

    anchors: list[tuple[ast.AST, set[str]]] = []
    for node in scope.nodes:
        if isinstance(node, ast.Compare):
            named: set[str] = set()
            subject: ast.AST | None = None
            for operand in (node.left, *node.comparators):
                values = member_values(operand)
                named |= values
                if not values and subject is None:
                    subject = operand
            if named and subject is not None:
                anchors.append((node, named))
        elif isinstance(node, ast.Match):
            named = set().union(*(member_values(case.pattern) for case in node.cases), set())
            if named:
                anchors.append((node, named))
    return anchors


def _dynamic_anchors(scope: _Scope) -> list[ast.AST]:
    """Mapping reads with a computed key: possible readers of any slot."""
    return [node for node in scope.nodes
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in _MAPPING_READS and node.args
            and not isinstance(node.args[0], ast.Constant)]


def scan_python_consumers(
    source: SourceFile, *, vocabulary: str, slot: str, values: Iterable[str],
    owners: Mapping[str, Mapping[str, str]] | None = None,
    modules: Mapping[str, SourceFile] | None = None,
) -> list[ConsumerSite]:
    """Classify every recognized consuming site of one vocabulary in one file."""
    tree = _parsed(source)
    domain = tuple(sorted(values))
    owners = owners or {}
    members: dict[str, str] = {}
    bound: set[str] = set()
    if owners:
        bindings = _qualified_bindings(source, tree, owners, modules)
        bound = set(bindings)
        for member_map in bindings.values():
            members.update(member_map)
    rows: set[ConsumerSite] = set()
    for scope in _module_scopes(source):
        site = f'{source.path}::{scope.name}'

        def add(node: ast.AST, role: str, anchor: str, observed: Iterable[str], blocker: str | None) -> None:
            named = tuple(sorted(set(observed) & set(domain))) if domain else tuple(sorted(set(observed)))
            rows.add(ConsumerSite(vocabulary, site, node.lineno, role, anchor, domain, named,
                                  _LIMITATIONS[role] if blocker is None else f'{blocker}: unresolved, not absent',
                                  blocker))

        for node in _slot_anchors(scope, slot):
            role, observed, blocker = _classify_anchor(node, scope)
            add(node, role, 'slot_read', observed, blocker)
        for node in _membership_anchors(scope, slot):
            add(node, 'read', 'slot_presence', set(), None)
        for node, named in _owner_anchors(scope, members, bound):
            add(node, 'interpret', 'owner_member', named, None)
    return sorted(rows, key=lambda row: (row.site, row.line, row.role, row.anchor))


def scan_dynamic_reads(source: SourceFile) -> list[ConsumerSite]:
    """Sites that read a mapping under a computed key, unattributed by design.

    Such a site may read any registered slot, so it is recorded once against
    ``ANY_VOCABULARY`` rather than duplicated into every vocabulary's table.
    It is the reason a vocabulary measured at zero readers is measured against
    a stated unknown instead of declared dead.
    """
    rows: list[ConsumerSite] = []
    for scope in _module_scopes(source):
        for node in _dynamic_anchors(scope):
            rows.append(ConsumerSite(
                ANY_VOCABULARY, f'{source.path}::{scope.name}', node.lineno, 'unknown',
                'dynamic_mapping_read', (), (),
                'dynamic_key: unresolved, not absent', 'dynamic_key'))
    return rows


def _first_line(text: str, token: str) -> int:
    """The first line carrying a token, so an unclassified mention has a location."""
    for number, line in enumerate(text.splitlines(), start=1):
        if token in line:
            return number
    return 1


def collect_consumer_evidence(
    repo_root: Path, registry: Mapping[str, Any], sources: list[SourceFile],
    *, names: Iterable[str] | None = None,
) -> ConsumerEvidence:
    """Scan the code-owned reach for every selected registered vocabulary."""
    by_path = {s.path: s for s in sources}
    selected = [s for s in sources if _in_reach(s.path)]
    python = [s for s in selected if s.suffix == '.py']
    sha, dirty = source_revision(repo_root)
    wanted = list(names) if names is not None else list(registry['vocabularies'])
    rows: list[ConsumerSite] = []
    skipped = 0
    for name in wanted:
        vocabulary = registry['vocabularies'][name]
        slot = slot_name(name, vocabulary)
        owners = _owner_members(vocabulary, by_path)
        domain = tuple(sorted(vocabulary['values']))
        symbols = [owner.split('::')[1] for owner in owners]
        for source in python:
            # Cheap text prefilter: a file that never spells the slot and never
            # imports the owner cannot yield a slot or owner anchor.
            mentions_slot = slot in source.text
            if not mentions_slot and not any(symbol in source.text for symbol in symbols):
                continue
            found = scan_python_consumers(source, vocabulary=name, slot=slot,
                                          values=vocabulary['values'], owners=owners, modules=by_path)
            rows.extend(found)
            if not found and mentions_slot:
                # The token is here and the grammar recognized nothing: prose, a
                # field list, a local named after the slot, a carrier this scan
                # does not model. Reported as unknown because the alternative is
                # to drop the module and let the tables read as complete.
                rows.append(ConsumerSite(
                    name, f'{source.path}::<module>', _first_line(source.text, slot), 'unknown',
                    'slot_mention', domain, (),
                    'mention_without_recognized_anchor: unresolved, not absent', 'mention_without_recognized_anchor'))
        for source in selected:
            if source.suffix == '.ts' and slot in source.text:
                skipped += 1
                rows.append(ConsumerSite(
                    name, f'{source.path}::<module>', 1, 'unknown', 'typescript_source', domain, (),
                    'typescript_not_walked: unresolved, not absent', 'typescript_not_walked'))
    for source in python:
        rows.extend(scan_dynamic_reads(source))
    rows.sort(key=lambda row: (row.vocabulary, row.site, row.line, row.role, row.anchor))
    return ConsumerEvidence(sha, dirty, len(python), len(sources), skipped, tuple(rows))


def render_consumer_evidence(evidence: ConsumerEvidence, *, top: int = 25) -> list[str]:
    """Advisory lines for the report surface; never a pass/fail verdict.

    Two unknown shares are printed because they answer different questions. The
    overall share includes the computed-key sites, which belong to no single
    vocabulary and dominate the count; the attributed share is what is unknown
    once a row has a vocabulary. Printing only one of them would flatter or
    inflate the result depending on which.
    """
    counts = evidence.counts()
    total = len(evidence.rows)
    attributed = [row for row in evidence.rows if row.vocabulary != ANY_VOCABULARY]
    attributed_unknown = sum(1 for row in attributed if row.role == 'unknown')
    lines = [
        'consumer evidence (advisory; syntactic use, not proved data flow, never a gate):',
        f'  source_sha={evidence.source_sha[:12]}'
        f'{" +dirty-worktree" if evidence.worktree_dirty else ""}'
        f'  reach={evidence.scanned_files} scanned Python sources of {evidence.tracked_files} tracked'
        f'  roots={", ".join(CONSUMER_SCAN_ROOTS)}',
        f'  rows={total}  ' + '  '.join(f'{role}={counts[role]}' for role in _ROLES)
        + f'  unknown_share={evidence.unknown_share():.1%}',
        f'  attributed_rows={len(attributed)}  unknown={attributed_unknown}'
        f'  attributed_unknown_share={attributed_unknown / len(attributed):.1%}'
        if attributed else '  attributed_rows=0',
        '  unknown_reasons: ' + (', '.join(f'{k}={v}' for k, v in evidence.blockers().items()) or 'none'),
        f'  {ANY_VOCABULARY} rows read a mapping under a computed key, so they are unresolved '
        'for every vocabulary at once and are never counted as a reader of one',
    ]
    per_vocabulary = Counter((row.vocabulary, row.role) for row in evidence.rows)
    for name in sorted({row.vocabulary for row in evidence.rows}):
        tally = '  '.join(f'{role}={per_vocabulary.get((name, role), 0)}' for role in _ROLES)
        lines.append(f'  {name}: {tally}')
    lines.append('  rows (location | role | anchor | observed values | limitation):')
    shown = [row for row in evidence.rows if row.vocabulary != ANY_VOCABULARY][:top]
    for row in shown:
        observed = ','.join(row.observed) or '-'
        lines.append(f'    {row.site}:{row.line} | {row.role} | {row.anchor} | {observed} | {row.limitation}')
    if len(attributed) > len(shown):
        lines.append(f'    ... {len(attributed) - len(shown)} further attributed rows and '
                     f'{total - len(attributed)} computed-key rows; raise --top to print more')
    return lines
