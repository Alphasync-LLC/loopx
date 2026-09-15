#!/usr/bin/env python3
"""Guard registered control-plane vocabularies against silent drift.

The registry ``loopx/control_plane/semantic_vocabulary_v0.json`` is the single
place that names each cross-module vocabulary, its defining owner modules, and
the retirement budgets the repository has agreed to ratchet down. This smoke
checks the code against that registry so a PR that widens a vocabulary, forks
a constant, or regrows a legacy surface must edit the registry in the same diff.
"""

from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REGISTRY_PATH = REPO_ROOT / "loopx" / "control_plane" / "semantic_vocabulary_v0.json"
REGISTRY_SCHEMA_VERSION = "loopx_semantic_vocabulary_v0"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_registry() -> dict:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    require(
        registry.get("schema_version") == REGISTRY_SCHEMA_VERSION,
        f"registry schema_version must be {REGISTRY_SCHEMA_VERSION}",
    )
    rfc = REPO_ROOT / str(registry.get("rfc", ""))
    require(rfc.is_file(), f"registry must point at an existing RFC: {rfc}")
    return registry


def source_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix in suffixes and "__pycache__" not in path.parts
    )


def python_symbol(owner: str) -> object:
    module_path, _, symbol = owner.partition("::")
    require(bool(symbol), f"python owner must be module::Symbol, got {owner!r}")
    dotted = module_path.removesuffix(".py").replace("/", ".")
    return getattr(importlib.import_module(dotted), symbol)


def typescript_const_array(owner: str) -> list[str]:
    module_path, _, symbol = owner.partition("::")
    text = (REPO_ROOT / module_path).read_text(encoding="utf-8")
    match = re.search(
        rf"export const {re.escape(symbol)}\s*=\s*\[(?P<body>.*?)\]\s*as const;",
        text,
        re.DOTALL,
    )
    require(match is not None, f"{module_path} must export const {symbol} = [...] as const")
    return re.findall(r"\"([a-z_]+)\"", match.group("body"))


VALUE_SHAPE = re.compile(r"^[a-z][a-z0-9_]*$")


def assert_closed_set(label: str, actual: list[str], expected: list[str]) -> None:
    malformed = [value for value in expected if not VALUE_SHAPE.match(value)]
    require(not malformed, f"registry {label} values must be lower snake_case: {malformed}")
    require(len(actual) == len(set(actual)), f"{label} repeats a value: {actual}")
    require(len(expected) == len(set(expected)), f"registry {label} repeats a value")
    missing = sorted(set(expected) - set(actual))
    unregistered = sorted(set(actual) - set(expected))
    require(
        not missing and not unregistered,
        f"{label} drifted from the registry; missing={missing} unregistered={unregistered}",
    )


def check_enum_vocabularies(registry: dict) -> None:
    for name, vocabulary in registry["vocabularies"].items():
        owners = vocabulary["owners"]
        values = list(vocabulary["values"])
        python_owner = owners.get("python", "")
        if "::" in python_owner:
            enum_cls = python_symbol(python_owner)
            assert_closed_set(
                f"{name} python enum", [member.value for member in enum_cls], values
            )
        typescript_owner = owners.get("typescript")
        if typescript_owner:
            assert_closed_set(
                f"{name} typescript const", typescript_const_array(typescript_owner), values
            )


def check_literal_vocabularies(registry: dict) -> None:
    for name, vocabulary in registry["vocabularies"].items():
        scan = vocabulary.get("literal_scan")
        if not scan:
            continue
        pattern = re.compile(scan["pattern"])
        suffixes = tuple(scan["suffixes"])
        observed: dict[str, set[str]] = {}
        for root in scan["roots"]:
            for path in source_files(REPO_ROOT / root, suffixes):
                text = path.read_text(encoding="utf-8", errors="replace")
                for value in pattern.findall(text):
                    observed.setdefault(value, set()).add(str(path.relative_to(REPO_ROOT)))
        expected = set(vocabulary["values"])
        malformed = [value for value in expected if not VALUE_SHAPE.match(value)]
        require(not malformed, f"registry {name} values must be lower snake_case: {malformed}")
        unregistered = {value: sorted(files) for value, files in observed.items() if value not in expected}
        require(
            not unregistered,
            f"{name} literals not in the registry (register them or use a registered value): {unregistered}",
        )
        unused = sorted(expected - set(observed))
        require(not unused, f"{name} registry lists values no module carries: {unused}")


def check_projections(registry: dict) -> None:
    projection = registry["projections"]["turn_route_to_loop_disposition"]
    from loopx.control_plane.turn_driver.driver import LoopXTurnRoute
    from loopx.control_plane.turn_driver.loop_controller import (
        LoopDisposition,
        _route_to_disposition,
    )

    mapping = projection["mapping"]
    routes = registry["vocabularies"]["turn_route"]["values"]
    require(sorted(mapping) == sorted(routes), "projection must name every turn_route exactly once")
    for route, expected in mapping.items():
        if expected is None:
            try:
                _route_to_disposition(LoopXTurnRoute(route))
            except KeyError:
                continue
            raise AssertionError(f"route {route} is registered as rejected but projects a disposition")
        actual = _route_to_disposition(LoopXTurnRoute(route))
        require(actual is LoopDisposition(expected), f"route {route} projects {actual.value}, registry says {expected}")


def check_schema_version_owners(registry: dict) -> None:
    for name, entry in registry["schema_versions"].items():
        constant = re.escape(entry["constant"])
        value = re.escape(entry["value"])
        definition = re.compile(
            rf"^\s*(?:export\s+const\s+)?{constant}\s*(?::\s*[\w<>\[\]|\" ]+)?\s*=\s*\"{value}\"",
            re.MULTILINE,
        )
        defining = sorted(
            str(path.relative_to(REPO_ROOT))
            for path in source_files(REPO_ROOT / "loopx", (".py", ".ts"))
            if definition.search(path.read_text(encoding="utf-8", errors="replace"))
        )
        require(
            defining == sorted(entry["owner_modules"]),
            f"schema version {name} is defined in {defining}; registry owners are {entry['owner_modules']}",
        )


def modules_mentioning(token: str, suffix: str) -> list[str]:
    return sorted(
        str(path.relative_to(REPO_ROOT))
        for path in source_files(REPO_ROOT / "loopx", (suffix,))
        if token in path.read_text(encoding="utf-8", errors="replace")
    )


def check_retirement_budgets(registry: dict) -> list[str]:
    report: list[str] = []
    ledger = registry["retirement_ledger"]["should_run_legacy_decision_fields"]["fields"]
    for field, budgets in ledger.items():
        for suffix, key in ((".py", "python_module_budget"), (".ts", "typescript_module_budget")):
            actual = len(modules_mentioning(field, suffix))
            require(
                actual <= budgets[key],
                f"legacy field {field} grew to {actual} {suffix} modules; budget is {budgets[key]}",
            )
            report.append(f"{field}{suffix}={actual}/{budgets[key]}")
    return report


def check_dual_runtime_twins(registry: dict) -> str:
    entry = registry["dual_runtime_twins"]
    root = REPO_ROOT / entry["root"]
    twins = sorted(
        str(path.relative_to(REPO_ROOT))
        for path in root.rglob("*.py")
        if path.name != "__init__.py" and path.with_suffix(".ts").is_file()
    )
    require(
        len(twins) <= entry["module_budget"],
        f"{len(twins)} py/ts twin modules under {entry['root']}; budget is {entry['module_budget']}",
    )
    return f"twins={len(twins)}/{entry['module_budget']}"


def main() -> int:
    registry = load_registry()
    check_enum_vocabularies(registry)
    check_literal_vocabularies(registry)
    check_projections(registry)
    check_schema_version_owners(registry)
    budgets = check_retirement_budgets(registry)
    twins = check_dual_runtime_twins(registry)
    print("semantic-vocabulary-drift-smoke: ok")
    print("  " + " ".join(budgets))
    print("  " + twins)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
