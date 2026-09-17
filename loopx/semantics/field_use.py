"""Classify how each module uses a named payload field (RFC B3).

The retirement ledger used to count modules whose text contains the field
token. That metric answers "does this name appear here", which is not the
question retirement asks. Removing a legacy field requires knowing which
modules *read* it, which modules *write* it, and which merely mention it in
prose -- three populations the token count folds into one number.

What is measured here is syntactic use, not data flow. A module is a reader
when it performs a recognized literal-key read (``payload["legacy_field"]``,
``payload.get("legacy_field")``, ``"legacy_field" in payload``, or the
TypeScript property read). It is a writer when it performs a recognized literal
write (subscript store, dict-literal key, keyword argument, attribute store,
``setdefault``). Reader and writer are not exclusive: a projection module that
reads the legacy field and re-emits it is both.

Three limits are part of the metric, not caveats around it:

* A computed key is **unresolved**. ``payload.get(name)`` may read any field, so
  no name-keyed scan -- lexical or syntactic -- can prove a module is not a
  reader. ``dynamic_mapping_key_sites`` counts those sites repository-wide, so a
  field measured at zero readers is measured against a stated unknown rather
  than declared dead, and a module that carries the field name as a bare string
  is reported as unresolved rather than as a mention. Subscripts with a computed
  key are deliberately *not* counted: ``rows[index]`` and ``payload[key]`` are
  the same syntax, and counting sequence indexing as an unresolved mapping read
  would inflate the unknown until it stopped carrying information.
* Same-prefix identifiers are different fields. ``legacy_field_repair`` is not
  a use of ``legacy_field``; the AST compares whole keys, and the TypeScript
  scan anchors on non-identifier boundaries.
* A field this module measures must not be spelled out here. The scan reads
  tracked sources under ``loopx/``, this file is one of them, and a field name
  in a docstring would add a mention to that field's own budget. The examples
  above use ``legacy_field`` for that reason; the real names live in the
  registry and in the smoke's anchors, both outside the scanned root.
* A mention is evidence of nothing. Prompt prose, a module path component, a
  local variable named after the payload it holds and a parameter name all
  carry the token without touching the field. They are reported as mentions so
  that migration can ignore them and so the residual token count stays visible.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Any, Iterable

from .inventory import SourceFile, parse_python

# ``dict``/``Mapping`` accessors whose first literal argument names a field.
MAPPING_READ_CALLS = frozenset({"get", "pop"})
MAPPING_WRITE_CALLS = frozenset({"setdefault"})

READ_FORMS = frozenset({
    "subscript_read", "mapping_call_read", "membership_read", "attribute_read",
    "property_read",
})
WRITE_FORMS = frozenset({
    "subscript_write", "mapping_call_write", "dict_literal_key", "keyword_argument",
    "attribute_write", "property_write",
})
# The module names the field as a parameter, a local or its own definition. It
# handles the value without a recognized key access -- a pass-through consumer
# in the RFC's role hierarchy, and a signature the migration has to change.
BINDING_FORMS = frozenset({"local_binding", "local_reference", "parameter", "definition"})
# The field name travels as data here: a string constant that no recognized key
# position consumed -- a name in a field list a loop will index with, or a label
# in an emitted record. Which one it is needs a reader, so the module is
# reported as unresolved rather than silently counted as a mention.
UNRESOLVED_FORMS = frozenset({"name_constant"})
MENTION_FORMS = frozenset({"module_import", "object_key", "prose"})
USE_FORMS = READ_FORMS | WRITE_FORMS | BINDING_FORMS | UNRESOLVED_FORMS | MENTION_FORMS

# TypeScript has no parser here, so it is scanned with a bounded grammar over
# code text whose string literals and comments have been blanked out first --
# otherwise a path label such as ``"decision.legacy_field"`` would be counted
# as a property read. Each pattern is anchored on non-identifier boundaries, so
# ``legacy_field_repair`` cannot match ``legacy_field``.
#
# ``object_key`` (a bare ``field:`` at the head of a line) is reported as a
# mention, not a write. An interface member and an object-literal entry are the
# same shape, and this grammar cannot separate them; crediting a declaration as
# a write would overstate production in exactly the direction the RFC's
# production obligation warns about. The token count still shows the module.
_TS_READ_PATTERNS: tuple[tuple[str, str], ...] = (
    ("property_read", r"\.\s*{field}(?![A-Za-z0-9_$])"),
    ("subscript_read", r"""\[\s*["']{field}["']\s*\]"""),
)
# Each write pattern is its read pattern followed by an assignment, so a write
# match always starts where the corresponding read match starts. That is how a
# pure write is kept from also counting as a read.
_TS_WRITE_SUFFIX = r"\s*(?:=[^=]|\+=)"
_TS_OBJECT_KEY = r"^\s*{field}\??\s*:"
_TS_STRING = re.compile(r"""(?s)(?P<q>["'`])(?:\\.|(?!(?P=q)).)*(?P=q)""")
_TS_COMMENT = re.compile(r"(?s)//[^\n]*|/\*.*?\*/")


@dataclass(frozen=True)
class FieldUse:
    """One module's recognized uses of one field."""

    field: str
    module: str
    forms: frozenset[str]

    @property
    def reads(self) -> bool:
        return bool(self.forms & READ_FORMS)

    @property
    def writes(self) -> bool:
        return bool(self.forms & WRITE_FORMS)

    @property
    def unresolved(self) -> bool:
        return bool(self.forms & UNRESOLVED_FORMS)

    @property
    def binds(self) -> bool:
        return bool(self.forms & BINDING_FORMS)

    @property
    def role(self) -> str:
        """The single label that orders migration work for this module."""
        if self.reads:
            return "reader"
        if self.writes:
            return "writer"
        if self.binds:
            return "binding"
        if self.unresolved:
            return "unresolved"
        return "mention"

    @property
    def in_migration_surface(self) -> bool:
        """True when removing the field requires changing this module."""
        return self.reads or self.writes or self.binds


def _literal_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def python_module_scan(tree: ast.AST, fields: frozenset[str]) -> tuple[dict[str, set[str]], int]:
    """Recognized forms per field, and the module's computed-key site count.

    Both come from one walk. The scan runs over every tracked Python module on
    every pull request that touches ``loopx/``, so a second traversal is a cost
    paid by everyone; the shared ``parse_python`` cache exists for the same
    reason.
    """
    found: dict[str, set[str]] = {}
    # Constants consumed as a literal key. Whatever is left over is the field
    # name travelling as data, which is how a computed access is written.
    keyed: set[int] = set()
    seen_constants: list[tuple[int, str]] = []
    dynamic_sites = 0

    def record(field: str, form: str) -> None:
        found.setdefault(field, set()).add(form)

    for node in ast.walk(tree):
        key = _literal_key(node)
        if key is not None:
            if key in fields:
                seen_constants.append((id(node), key))
            continue
        if isinstance(node, ast.Subscript):
            key = _literal_key(node.slice)
            if key in fields:
                keyed.add(id(node.slice))
                record(key, "subscript_write" if isinstance(node.ctx, (ast.Store, ast.Del)) else "subscript_read")
        elif isinstance(node, ast.Call):
            function = node.func
            if isinstance(function, ast.Attribute) and node.args:
                accessor = function.attr in MAPPING_READ_CALLS or function.attr in MAPPING_WRITE_CALLS
                key = _literal_key(node.args[0])
                if accessor and key is None:
                    dynamic_sites += 1
                elif key in fields and function.attr in MAPPING_READ_CALLS:
                    keyed.add(id(node.args[0]))
                    record(key, "mapping_call_read")
                elif key in fields and function.attr in MAPPING_WRITE_CALLS:
                    keyed.add(id(node.args[0]))
                    record(key, "mapping_call_write")
            for keyword in node.keywords:
                if keyword.arg in fields:
                    record(keyword.arg, "keyword_argument")
        elif isinstance(node, ast.Dict):
            for key_node in node.keys:
                key = _literal_key(key_node) if key_node is not None else None
                if key in fields:
                    keyed.add(id(key_node))
                    record(key, "dict_literal_key")
        elif isinstance(node, ast.Compare):
            key = _literal_key(node.left)
            if key in fields and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                keyed.add(id(node.left))
                record(key, "membership_read")
        elif isinstance(node, ast.Attribute):
            if node.attr in fields:
                record(node.attr, "attribute_write" if isinstance(node.ctx, (ast.Store, ast.Del)) else "attribute_read")
        elif isinstance(node, ast.arg):
            if node.arg in fields:
                record(node.arg, "parameter")
        elif isinstance(node, ast.Name):
            if node.id in fields:
                record(node.id, "local_binding" if isinstance(node.ctx, (ast.Store, ast.Del)) else "local_reference")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in fields:
                record(node.name, "definition")
        elif isinstance(node, ast.ImportFrom):
            parts = set((node.module or "").split("."))
            for field in fields:
                if field in parts or any(alias.name == field for alias in node.names):
                    record(field, "module_import")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = set(alias.name.split("."))
                for field in fields & parts:
                    record(field, "module_import")
    for identity, key in seen_constants:
        if identity not in keyed:
            record(key, "name_constant")
    return found, dynamic_sites


def _blank_strings_and_comments(text: str) -> tuple[str, list[str]]:
    """Split a TypeScript module into code text and its string literals.

    String and comment bodies are replaced by a placeholder of the same length
    so line structure survives for the line-anchored patterns, while the field
    names inside them stop matching code forms.
    """
    literals: list[str] = []

    def mask(body: str) -> str:
        return "".join("\x00" if character != "\n" else "\n" for character in body)

    def blank_literal(match: re.Match[str]) -> str:
        literals.append(match.group(0))
        return mask(match.group(0))

    without_comments = _TS_COMMENT.sub(lambda match: mask(match.group(0)), text)
    code = _TS_STRING.sub(blank_literal, without_comments)
    return code, literals


def typescript_field_forms(text: str, fields: frozenset[str]) -> dict[str, set[str]]:
    """Recognized forms per field in one TypeScript module, by bounded grammar."""
    found: dict[str, set[str]] = {}
    code, literals = _blank_strings_and_comments(text)
    # Subscript keys are string literals, which blanking removed, so they are
    # matched against the original text. A quoted key inside prose would be an
    # indexing expression there too, so this does not reintroduce the path-label
    # false positive that blanking exists to remove.
    for field in fields:
        quoted = re.escape(field)
        for form, template in _TS_READ_PATTERNS:
            pattern = template.format(field=quoted)
            subject = text if form.startswith("subscript") else code
            reads = [match.start() for match in re.finditer(pattern, subject, re.MULTILINE)]
            if not reads:
                continue
            writes = {match.start() for match in re.finditer(pattern + _TS_WRITE_SUFFIX, subject, re.MULTILINE)}
            if writes:
                found.setdefault(field, set()).add(form.replace("_read", "_write"))
            if set(reads) - writes:
                found.setdefault(field, set()).add(form)
        if re.search(_TS_OBJECT_KEY.format(field=quoted), code, re.MULTILINE):
            found.setdefault(field, set()).add("object_key")
        token = re.compile(rf"(?<![A-Za-z0-9_]){quoted}(?![A-Za-z0-9_])")
        if any(token.search(literal) for literal in literals):
            found.setdefault(field, set()).add("prose")
    return found


@lru_cache(maxsize=256)
def _token_pattern(field: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(field)}(?![A-Za-z0-9_])")


def lexical_module_count(field: str, suffix: str, sources: Iterable[SourceFile]) -> int:
    """The pre-B3 metric: modules whose text contains the standalone token."""
    token = _token_pattern(field)
    return sum(1 for source in sources if source.suffix == suffix and token.search(source.text))


def scan_field_uses(fields: Iterable[str], sources: Iterable[SourceFile]) -> tuple[list[FieldUse], int]:
    """Classify every module's use of each field; also return the unresolved count."""
    wanted = frozenset(fields)
    uses: list[FieldUse] = []
    dynamic_sites = 0
    for source in sources:
        # Every Python module contributes to the computed-key total whether or
        # not it names a field, so the cheap substring filter only narrows the
        # per-field work, never the standing unknown.
        present = frozenset(field for field in wanted if field in source.text)
        if source.suffix == ".py":
            try:
                tree = parse_python(source)
            except (SyntaxError, ValueError):
                # An unparseable tracked module is a measurement gap, not a
                # module without readers; fall back to the token so the field
                # is not silently credited with one fewer mention. The inventory
                # scan rejects such a module first, so this path is for direct
                # callers rather than the drift smoke.
                for field in wanted:
                    if lexical_module_count(field, ".py", [source]):
                        uses.append(FieldUse(field=field, module=source.path, forms=frozenset({"prose"})))
                continue
            forms, module_dynamic_sites = python_module_scan(tree, present)
            dynamic_sites += module_dynamic_sites
        elif source.suffix == ".ts":
            forms = typescript_field_forms(source.text, present)
        else:
            continue
        for field in present:
            recognized = forms.get(field, set())
            if not recognized and _token_pattern(field).search(source.text):
                # The token is present but no recognized form carries it: a
                # comment, a docstring, or prompt prose.
                recognized = {"prose"}
            if not recognized:
                continue
            unclassified = recognized - USE_FORMS
            if unclassified:
                # A form with no role would disappear from the role counts while
                # still carrying the token, breaking the partition the ledger
                # check relies on. Fail where the form was added, not there.
                raise ValueError(f"unclassified field-use form(s): {sorted(unclassified)}")
            uses.append(FieldUse(field=field, module=source.path, forms=frozenset(recognized)))
    return sorted(uses, key=lambda use: (use.field, use.module)), dynamic_sites


ROLES = ("reader", "writer", "binding", "unresolved", "mention")


def field_use_summary(fields: Iterable[str], sources: Iterable[SourceFile]) -> dict[str, Any]:
    """Per-field role counts and migration surface, beside the old token count.

    ``migration_surface`` is the number of modules that must change before the
    field can be removed: every reader, writer and binding. Mentions are prose
    and imports, and ``unresolved`` modules carry the field name as data, so
    they are reported separately rather than folded into a budget that would
    then move when a comment is reworded.
    """
    materialized = list(sources)
    ordered = sorted(fields)
    uses, dynamic_sites = scan_field_uses(ordered, materialized)
    summary: dict[str, Any] = {"fields": {}, "dynamic_mapping_key_sites": dynamic_sites}
    for field in ordered:
        entry: dict[str, Any] = {}
        for suffix, runtime in ((".py", "python"), (".ts", "typescript")):
            selected = [use for use in uses if use.field == field and use.module.endswith(suffix)]
            roles = [use.role for use in selected]
            for role in ROLES:
                entry[f"{runtime}_{role}_modules"] = roles.count(role)
            entry[f"{runtime}_migration_surface"] = sum(1 for use in selected if use.in_migration_surface)
            entry[f"{runtime}_token_modules"] = lexical_module_count(field, suffix, materialized)
        summary["fields"][field] = entry
    return summary


def render_field_uses(uses: Iterable[FieldUse]) -> list[str]:
    """One reviewable line per module, for ``--report``."""
    return [
        f"{use.field} {use.role} {use.module} [{','.join(sorted(use.forms))}]"
        for use in uses
    ]
