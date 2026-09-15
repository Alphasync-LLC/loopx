# RFC: Semantic Vocabulary Convergence and Commit-Time Drift Checks (v0)

- **RFC status:** Draft
- **Delivery maturity:** Partial (M0 registry, generated inventory, and drift smoke ship with this RFC)
- **Authors / owners:** LoopX contributors; control-plane kernel maintainers own approval
- **Created:** 2026-09-15
- **Last normative revision:** 2026-09-15
- **Implementation baseline:** `1dc6ad8d8`
- **Related contracts:** `loopx/semantics/vocabulary_v0.json`,
  `loopx/semantics/inventory_v0.json`,
  `loopx/control_plane/turn_transaction_contract.json`,
  `loopx/control_plane/coordination/coordination_state_contract_v0.json`,
  [Turn Envelope v0](../../reference/protocols/turn-envelope-v0.md),
  [Turn Loop Controller v0](../../reference/protocols/turn-loop-controller-v0.md),
  [TypeScript Control-Plane Migration v0](typescript-control-plane-migration-v0.md)
- **Language mirror:** [中文版](https://github.com/huangruiteng/loopx/blob/main/docs/architecture/rfcs/semantic-vocabulary-convergence-v0.zh-CN.md)

## Document map and maintenance contract

This RFC ships an English document and a `semantic-vocabulary-convergence-v0.zh-CN.md`
semantic mirror; both carry a language link and must be revised together when a
normative section changes.

- Sections 1-10 are the durable design and acceptance contract.
- Section 11 is the normative delivery plan.
- Section 12 contains unresolved decisions; proposed answers are not approval.
- Appendices hold the non-normative execution ledger, decision log, evidence
  registry, and rejected alternatives.

RFC maturity and delivery maturity are independent. Dated progress entries do
not amend normative sections.

---

## 1. Decision summary

1. **What becomes authoritative.** Two files under `loopx/semantics/`. The
   curated registry `vocabulary_v0.json` names each kernel and cross-runtime
   vocabulary, the exact `module::Symbol` allowed to define it, the relations
   between vocabularies (same concept, shared field name, subset), the total
   projections, and the budgets the repository ratchets down. The generated
   inventory `inventory_v0.json` maps every closed-set carrier under `loopx/`:
   string enums, `Literal` aliases, named closed sets, TypeScript `as const`
   arrays, and every constant name defined in more than one module. A public
   smoke, `examples/semantic-vocabulary-drift-smoke.py`, checks the code against
   both on every premerge and full-public run. A change that widens a
   vocabulary, forks a constant, adds a carrier, or weakens the registry must
   edit the registry or regenerate the inventory in the same diff, so the
   reviewer sees the semantic change as a change.
2. **What remains unchanged.** Runtime behavior, wire formats, and the enum
   classes themselves. Each enum keeps living in its owner module; the registry
   is checked against code by AST and text scan, it does not generate code and
   product code never imports it.
3. **Default and opt-in boundary.** The check is always on for the repository.
   It has no runtime flag because it never runs inside the product.
4. **Principal constraint.** Fail closed, deterministic, and not weakenable by
   a data edit alone. An unregistered literal in either runtime, a second
   defining module, a budget overrun, a registry value no module carries, a
   stale inventory, an owner declared without a symbol, or a coverage count
   below the recorded floor each fails the smoke. The dispatch forms the scan
   recognises live in the smoke, not in the registry. The smoke reads only
   tracked sources and prints no private data.
5. **Not approved by this RFC.** Merging the three Turn outcome enums into one,
   splitting the three `effective_action` slots, deleting any legacy should-run
   field, deleting any Python twin module, or renaming any existing value.
   Those are later milestones with their own gates under the schema-reduction
   rule in `AGENTS.md`.

## 2. Problem and motivation

LoopX has grown by many small agent-driven PRs. Each PR added the vocabulary it
needed where it needed it. The result is not wrong behavior but drift: the same
concept spelled several ways, the same constant defined in several files, the
same field name carrying different vocabularies, and open string sets that any
module may widen without anyone noticing. Reviewers cannot tell from a diff
whether a new literal is a new state or a typo, and documentation cannot stay
in step with a set nobody enumerates.

The semantic surface is repository-wide, not a Turn-kernel problem. Measured on
the baseline by the inventory generator over 1169 source files under `loopx/`:

| Carrier | Count | Notes |
| --- | --- | --- |
| Python string enums | 102 | 29 in the control plane, 17 in capabilities, 6 in extensions |
| Named closed sets (`NAME = frozenset/tuple` of strings) | 490 | 66 are field lists, 31 kinds, 31 states, 29 statuses |
| `Literal[...]` aliases | 8 | |
| TypeScript `as const` arrays | 40 | 21 have an equal Python set; 14 have none |
| Named string constants | 2002 | 754 are `*_SCHEMA_VERSION` |
| Same name, same value, two runtimes | 166 | legitimate py/ts twins |
| Same name, same value, one runtime | 25 names / 58 definitions | forks; 7 are schema versions |
| Same name, different values | 18 names / 59 definitions | see below |

Concrete failures audited on the baseline:

- `TURN_ENVELOPE_SCHEMA_VERSION` was defined three times:
  `loopx/control_plane/quota/turn_envelope.py:16`,
  `loopx/control_plane/quota/turn_envelope.ts:13`, and a private copy in
  `loopx/control_plane/turn_driver/driver.py:31`. M0 removes the copy.
- `HANDOFF_MODES` was defined by the TypeScript owner and again as a literal
  tuple in `control_plane/testing/authority_e2e_fixtures.py:33`. M0 derives the
  fixture tuple from the `HandoffMode` enum.
- The same value set carries two names across runtimes:
  `MATERIAL_DELIVERY_OUTCOMES` in `work_items/delivery_outcome.ts` equals
  `VISION_OUTCOME_CHECKPOINT_MATERIAL_OUTCOMES` in
  `goals/goal_frontier/outcome_continuity.py`. Both equal `DeliveryOutcome`
  minus `surface_only`; nothing said so.
- Conflicting definitions with the same name: `DECISION_CONTEXT_CAPABILITY_ID`
  is `decision_context` in `capabilities/decision_context/packets.py:18` and
  `decision-context` in `extension_provider.py:24`; `MCP_REQUIREMENT` is
  `mcp==1.28.1` in `kunluncode_goal_mode/cli.py:28` and `mcp<2` in
  `claude_goal_mode/scripts/install.py:83`. Sixteen further names are generic
  module-local constants (`SCHEMA_VERSION`, `COMMAND`, `CAPABILITY_ID`) whose
  collision is harmless today and invisible tomorrow.
- The Turn result kinds exist twice by hand: `LoopXTurnResultKind` in
  `transaction.py:28` and `TURN_RESULT_KINDS` in `settlement.ts:49`. They
  match; no test asserted it. The same holds for eleven other py/ts pairs
  (settlement step, binding and failure kinds, receipt-bound phases, scheduler
  transitions, Todo completion continuation and recovery, delivery outcome,
  delivery workspace kinds, Goal amendment classes, Todo decision scopes).
- `effective_action` is an open string set with no enum on either runtime.
  Thirty-one distinct literals are dispatched on by string comparison in
  Python and TypeScript. Two of them (`observe_replay`, `block_replay`) are
  written by `turn_journal.ts:656` into the replay observation slot of the
  Turn Envelope and are not should-run verdicts at all. Two more
  (`quota_action_selection_deferred`, `quota_action_selection_rejected`) are
  quota error codes that `cli_commands/quota.py:279` copies into the slot.
  `AgentScopeFrontierAction` values are written into the
  `agent_scope_frontier.effective_action` slot of the same envelope. One field
  name, three vocabularies. `user_gate.py:162` compares the slot against
  `skip`, which no producer writes.
- Three near-isomorphic Turn outcome vocabularies coexist:
  `LoopXTurnResultKind` (12), `LoopXTurnRoute` (8), `LoopDisposition` (8),
  with `repair`/`repair_required` and `replan`/`replan_required` as different
  spellings of one verdict. The route-to-disposition projection is a private
  dictionary in `loop_controller.py:126`; nothing declared that it is total.
  The load-bearing table in `decide_loop_disposition` (result kind, retryable,
  attempt budget, decision user action, durable no-follow-up) exists only as
  prose in the controller protocol document.
- Six should-run decision fields the documentation already calls legacy are
  still mentioned by 7 to 35 Python modules each, with no ratchet stopping new
  consumers.
- 43 same-basename `.py`/`.ts` module pairs exist under `loopx/control_plane`
  while the migration RFC is replacement-first. The count had no guard.
- The repository already runs an AST-backed control-plane debt ratchet
  (`loopx/canary/maintainability_ratchet.py`) with a reviewed exception
  lifecycle, but it measures module metrics and dependency direction, not
  vocabulary shape. Vocabulary drift had no ratchet.

The current owners cannot solve this locally because every fix is
cross-module by definition: the Turn driver, quota, todos, capabilities, and
the TypeScript runtime each own one spelling of the same idea.

### Invariants

- **I1 Single owner.** Every registered vocabulary or constant has exactly the
  defining modules the registry lists, and the registered symbol name is
  defined nowhere else under `loopx/`. Everyone else imports.
- **I2 Closed sets.** Every value a registered vocabulary may carry is listed.
  The code carries no unregistered value in either runtime and the registry
  lists no value the code does not carry.
- **I3 Cross-runtime parity.** When a vocabulary has a Python and a TypeScript
  owner, both carry the identical set.
- **I4 Total projections.** A registered projection names every source value
  exactly once, either mapping it or declaring it rejected.
- **I5 Ratchets only fall.** Retirement, twin, and inventory budgets may be
  lowered in any PR. Each budget is additionally pinned by a `BUDGET_ANCHOR`
  (or `RETIREMENT_ANCHOR`) literal inside the smoke, and each floor by a
  `COVERAGE_ANCHOR`, following the `RFC_MODULE_BUDGETS` anchor pattern in
  `tests/control_plane/test_m6_quality_gates.py`: the registry may tighten past
  the anchor and never loosen past it. Raising an anchor requires editing a code
  literal, where a reviewer sees it beside the JSON.
- **I6 Same-diff visibility.** A semantic change and its registry edit or
  inventory regeneration land in one reviewable diff.
- **I7 Deterministic and public-safe.** The check reads tracked sources only,
  needs no network or credentials, and its failure text names files and
  values, never private data.
- **I8 Coverage only grows.** The number of registered vocabularies, owner
  symbols, projections, relations, schema versions, and scanned suffixes is
  recorded as a floor. An owner is `module::Symbol` or `null`; a bare module
  path is rejected, and a null owner requires a literal scan. The dispatch
  forms the scan recognises are fixed in the smoke. A registry edit therefore
  cannot silently narrow what the guard sees.
- **I9 Both carrier shapes are measured.** A vocabulary reaches the code either
  as a string constant (`NAME = "value"`) or as a multi-value carrier (an enum,
  a named closed set, a `Literal` alias, a TypeScript `as const` array). Both
  get the same collision rule: one name defined in two modules with identical
  values is a twin, with different values a fork. Collision budgets count the
  shared-vocabulary subset only; module-local convention names such as
  `SCHEMA_VERSION`, `COMMAND`, or `*_LABEL` stay visible in the inventory totals
  but are not drift.

## 3. Scope and non-goals

### In scope

- The registry file, its schema, and the ownership rule for editing it.
- The generated inventory, its generator with `--check`, and its unit test.
- The drift smoke and its placement in the premerge and full-public fleets.
- The vocabularies registered at M0: the four Turn-kernel sets
  (`turn_result_kind`, `turn_route`, `loop_disposition`, `effective_action`),
  `agent_scope_frontier_action` and `lease_action`, and twenty cross-runtime
  sets whose Python and TypeScript owners carry equal values on the baseline;
  the route-to-disposition projection; nine relations; the Turn Envelope schema
  version; the six legacy should-run fields; the control-plane twin count; and
  the inventory fork and conflict budgets.
- The later milestones that turn `effective_action` into a typed enum, split
  its three slots, publish the projection through the contract, and retire
  legacy fields and twins under existing repository rules.

### Non-goals

- Changing any runtime decision, payload shape, or wire format.
- Curating every closed set by hand. The inventory maps all of them; only
  vocabularies that cross a module or runtime boundary and are dispatched on
  are curated with owners, values, and relations.
- Replacing `turn_transaction_contract.json` or
  `coordination_state_contract_v0.json`. Those remain the owners of their
  phases and records; this registry may reference them, not restate them.
- Replacing `maintainability_ratchet.py`. It owns module metrics and dependency
  direction; this registry owns vocabulary shape. Whether their exception
  lifecycles merge is Section 12, Q7.
- A prose glossary as the enforcement mechanism. A glossary is a useful
  companion and is tracked in Section 12, but it cannot fail a build.

## 4. Current-system contract

Facts on baseline `1dc6ad8d8`:

- `turn_transaction_contract.json` is the one contract read by both runtimes:
  `effect_program.py:160-166` loads the phase tuple and
  `turn_journal.ts:1` imports the JSON. This is the template the registry
  follows for a shared source of truth.
- `coordination_state_contract_v0.json` goes further and generates
  `coordination_state_contract_generated.py` and
  `coordination_state_contract.generated.ts` through
  `scripts/generate_coordination_state_contract.py --check`, guarded by
  `tests/control_plane/test_coordination_state_contract.py`. This is the
  template the inventory generator follows now and the generation stage
  proposed in M2 follows later.
- The canary runner discovers every tracked `examples/**/*-smoke.py`
  (`loopx/canary/runner.py:392`), so a smoke at `examples/` needs no
  registration in `planner.py` or `premerge.py`.
- `loopx/canary/maintainability_ratchet.py` is the existing AST-backed
  control-plane debt ratchet. It carries reviewed exceptions with a
  `retirement_plan` and detects stale exception ids. Its subject is module
  size, `Any` density, decision-point counts, and forbidden dependency
  direction; it does not read enum or constant values.
- `AGENTS.md` already requires typed enums for state classification, forbids a
  second source of truth in Python for control-plane authority, requires a
  scope-fit review before adding a module, and requires maintainer approval for
  any schema reduction. This RFC adds the check that makes those rules
  observable in a diff; it does not change them.
- Package data for `loopx.control_plane` already ships `*.json`;
  `pyproject.toml` gains one line so `loopx.semantics` ships its two JSON files
  the same way.

## 5. Proposed architecture

### Ownership and authority

The registry is owned by the control-plane kernel maintainers. Any contributor
may lower a budget or add a value together with the code that carries it. Only
a maintainer may approve raising a budget, removing a value, or moving an owner
module, and the approval is recorded in Appendix B.

Forbidden alternate authorities: a second registry, a per-module list that
restates registered values, or a prose table that claims to be normative for a
registered vocabulary.

### State model and schema

`loopx/semantics/vocabulary_v0.json`, `schema_version`
`loopx_semantic_vocabulary_v0`. The key set is closed; an unknown top-level or
vocabulary key fails the smoke.

| Key | Content | Check |
| --- | --- | --- |
| `coverage_floor` | counts of vocabularies, owner symbols, literal-scan fields, projections, relations, schema versions; the scanned suffix set | Actual counts are at or above the floor, declared suffixes cover the floor set, and no floor sits below its `COVERAGE_ANCHOR` (I8) |
| `vocabularies.<name>.owners` | `python` and `typescript`, each `path::Symbol` or `null` | Enum members, closed-set members, `Literal` alias, or `as const` array equal `values`; the symbol is defined only in owner modules (I1, I2, I3) |
| `vocabularies.<name>.tier`, `status` | `kernel`, `cross_runtime`, `cross_module`; `canonical`, `legacy`, `merge_candidate` | Closed enumerations |
| `vocabularies.<name>.literal_scan` | `field`, roots, suffixes | Every literal the fixed dispatch forms capture is registered; every registered value is captured or variable-sourced (I2) |
| `vocabularies.<name>.variable_sourced_values` | value to producer module | The producer still contains the quoted value |
| `vocabularies.<name>.value_notes`, `deprecated_values` | per-value review notes; values slated for removal | Names must be registered values |
| `relations.same_concept` | groups of `vocabulary.value` members | Every member resolves |
| `relations.shared_field_names` | one field name, its slots and the vocabulary or values each carries | Every slot resolves |
| `relations.subsets` | superset vocabulary, excluded values, owners of the subset symbol | Owner symbols equal superset minus excluded |
| `projections.<name>.mapping` | source value to target value or `null` | Keys equal the source vocabulary; mapped values match the owner function; `null` routes raise (I4) |
| `schema_versions.<name>` | constant name, value, owner modules | The only defining modules are the listed owners and all carry the value (I1) |
| `retirement_ledger.<group>.fields` | per-field Python and TypeScript module budgets | Actual module counts are at or below budget, and the field set and every budget match `RETIREMENT_ANCHOR` (I5) |
| `dual_runtime_twins` | root and module budget | Same-basename `.py`/`.ts` pair count is at or below budget (I5) |
| `inventory_ratchets` | budgets for same-runtime fork names and definitions, conflicting names and definitions, schema-version forks, multi-value twins and forks, and the shared-vocabulary conflict and fork subsets | Inventory summary counts are at or below budget, and no budget sits above its `BUDGET_ANCHOR` entry (I5, I9) |

`loopx/semantics/inventory_v0.json`, `schema_version`
`loopx_semantic_inventory_v0`, is generated by
`scripts/generate_semantic_inventory.py` and must equal a fresh build. It
lists Python enums, closed sets, `Literal` aliases, TypeScript `as const`
arrays, and duplicate definitions split into cross-runtime twins, same-runtime
forks, conflicting values, and multi-value twins and forks, one entry per line.
Every multi-value collision carries each defining module and its value set, so
the divergence itself is reviewable rather than only its count. Consumer counts
and merge-candidate groups are printed by `--report` and not committed, so an
ordinary consumer edit does not touch the file; merge candidates are advisory
because an equal value set is not proof of one concept. Single-module string
constants are counted, not listed.

Values are additive. Removing a value, a field, an owner, or a relation is a
schema reduction and follows the `AGENTS.md` rule: enumerate the affected
surfaces, research producers and readers, lower the floor in the same diff, and
record maintainer approval.

### Command or event lifecycle

The check has one command: run the smoke. It is idempotent and has no side
effects. Failure text names the vocabulary, the offending files, and the values
so the fix is mechanical: register the value, import the constant, or lower the
scope of the change.

### Provider or extension contract

New vocabularies are added by a PR that adds the registry entry, raises the
coverage floor, and, where a TypeScript owner exists, names its `as const`
array. A vocabulary qualifies for curation when it is dispatched on by more
than one module or crosses the Python/TypeScript boundary; everything else is
mapped by the inventory without curation. Adding any carrier regenerates the
inventory in the same PR.

## 6. Alternatives and design choices

| Alternative | Why not now |
| --- | --- |
| Unify the three Turn enums into one in a single PR | Breaks I5 style incrementalism; the three enums have different owners and change reasons (settlement, route, controller). Register and project first, then merge only where a projection proves identity (Section 12, Q2). |
| Rely on `mypy` `Literal` types | Does not cover TypeScript, JSON payloads, or the CLI; the drift here lives at exactly those boundaries. |
| Documentation glossary only | Cannot fail a build; the repository already has eleven documents calling themselves a mental model and no glossary, which is the symptom. |
| Generate bindings from the registry immediately | Premature until owners are settled. Generation is M2 and follows the coordination contract precedent. |
| Grep-based lint in CI without a registry | Encodes the allowed set in the linter, which becomes a second registry with no review trail. |
| Extend `maintainability_ratchet.py` instead of a new registry | Its subject is module metrics and dependency direction with per-module ceilings; vocabulary shape needs values, owners, and relations. The two share the ratchet idea, not the data model. Merging exception lifecycles is Q7. |
| Put the scan regex in the registry | A regex in data can be narrowed in the same edit that widens a vocabulary; the M0 review showed the first pattern missed every TypeScript `===` site. Forms are fixed in the smoke and the suffix set is floored. |
| Commit consumer counts in the inventory | Every consumer edit would churn the file and make the freshness check noise. Counts stay advisory via `--report`. |

## 7. Safety, privacy, and compatibility

- No runtime path imports the registry at M0; product behavior is unchanged
  with the check present or absent.
- The smoke reads tracked repository files only and prints file paths relative
  to the repository root plus registered identifiers.
- Legacy readers and writers are untouched. Budgets freeze their current spread
  without removing a single reference.
- Mixed versions are not a concern for a build-time check. When M2 introduces
  generated bindings, the generator's `--check` mode and the smoke both run so
  a stale generated file cannot merge.

## 8. Migration and rollback

- **Admission.** M0 lands with the registry and inventory matching the
  baseline exactly, plus two behavior-preserving edits so the owner check is
  green: the duplicate `TURN_ENVELOPE_SCHEMA_VERSION` in `driver.py` becomes an
  import, and the `HANDOFF_MODES` tuple in the authority e2e fixtures is
  derived from the `HandoffMode` enum.
- **Rollback.** Deleting the smoke, the `loopx/semantics/` package, the
  generator, its test, and the `pyproject.toml` line restores the previous
  state with no runtime effect. Later milestones each carry their own rollback
  in Section 11.
- **Point of no return.** None in M0. M3 field removals are the first
  irreversible step and are gated individually.

## 9. Validation and acceptance

| Claim | Test or evidence | Required result | Boundary / exclusions |
| --- | --- | --- | --- |
| Registry and inventory match the code at baseline | `python3 examples/semantic-vocabulary-drift-smoke.py` | `ok` with coverage, ratchet, budget, and twin report | Proves parity for registered vocabularies and mapped carriers only |
| Inventory is fresh | `python3 scripts/generate_semantic_inventory.py --check` | exit 0 | Structural map only |
| Scanner classification rules | `pytest tests/architecture/test_semantic_inventory.py` | pass | Fixture repository; rules from this RFC, not from output |
| A widened `effective_action` set fails closed in Python | Add an unregistered literal via `==`, membership, or conditional expression | Failure names the value and file | Mutation exercise; not a committed test |
| A widened `effective_action` set fails closed in TypeScript | Add an unregistered literal via `===` or a ternary | Same | Same |
| A forked constant fails closed | Redefine `TURN_ENVELOPE_SCHEMA_VERSION` or `HANDOFF_MODES` in a non-owner module, regenerate the inventory | Failure lists the extra defining module or the fork budget | Same |
| Python and TypeScript owners cannot diverge | Remove one entry from a registered `as const` array, or widen a registered enum | Failure names the missing or unregistered value | Same |
| The registry cannot be weakened by data alone | Declare a bare-module owner; drop an owner; narrow suffixes to `.py`; rename a vocabulary another relation references; add an unknown key | Each fails naming the rule | Same |
| A new carrier is visible | Add an enum without regenerating | Failure says the inventory is stale | Same |
| Conflicting spellings cannot grow | Add a third value for an already-conflicting name, regenerate | Failure names the definitions budget | Same |
| A multi-value collision cannot grow | Define one closed-set name in two modules with divergent values, or with equal values, and regenerate | `multi_value_forks` or `multi_value_twins` fails naming the new name | Mutation exercise; not a committed test |
| The registry cannot relax its own ratchet | Lower any `coverage_floor` count, raise any `inventory_ratchets` budget, or raise a retirement budget, in the same diff that removes the coverage it counts | `COVERAGE_ANCHOR`, `BUDGET_ANCHOR`, or `RETIREMENT_ANCHOR` fails naming the anchored value | Mutation exercise; moving an anchor is a code edit a reviewer sees |
| Measurement covers both carrier shapes and filters local naming | `pytest tests/architecture/test_semantic_inventory.py` | pass, including the collision and module-local-convention fixtures | Rules come from this RFC, not from scanner output |
| No behavior change from the two owner fixes | `pytest tests/test_loopx_turn_transaction.py tests/test_loop_turn_loop_controller.py tests/test_turn_loop_disposition.py tests/test_loopx_turn_managed_step.py tests/control_plane -k authority` and `loopx canary premerge --from-git-diff` | pass | Environment failures already present on `main` are excluded when reproduced on a clean tree |
| Docs governance accepts the RFC pair | `python3 examples/docs-governance-smoke.py` | pass | Checks mirror, links, index |

Known limits, stated so the check is not over-trusted:

- **Renames launder a collision.** Collisions are keyed by name, so renaming one
  side of a fork lowers the count without removing the drift. The advisory merge
  report is the review aid here; value-set equality cannot be a hard budget
  because `CONFIDENCE_LEVELS` and `EDGE_CASE_COMPLEXITIES` share `high/low/medium`
  while meaning different things.
- **Single-element carriers are invisible.** A closed set with one string member
  is not a vocabulary, so reducing a two-value set to one removes it from the
  inventory entirely.
- **The literal scan can misread unrelated comparisons on the same line.** A form
  such as `log("effective_action", kind === "repair_required")` is captured as an
  `effective_action` value. Registering the reported value to clear the failure
  would widen the vocabulary, so the correct fix is to register the field name
  and the literal together or restructure the line; the failure text names the
  file so this is visible in review.
- **Anchors are code, not history.** A PR can still move an anchor; it cannot do
  so without editing a named literal next to the registry change.

## 10. Operational contract

The check cannot affect a running system: it executes only in premerge and CI.
Its operator surface is the failure text. No observability, capacity, or
on-call contract applies.

## 11. Normative delivery plan

| Milestone | Shipped behavior | Entry gate | Exit evidence | Rollback |
| --- | --- | --- | --- | --- |
| M0 | Registry with 26 vocabularies and 9 relations, generated inventory with `--check`, drift smoke with fixed dispatch forms and coverage floor, two owner forks removed, RFC index entry | This RFC opened | Section 9 rows green; 20 mutation classes fail closed | Delete the smoke, `loopx/semantics/`, the generator, and its test |
| M1 | `EffectiveAction` typed enum in one owner module; the replay observation and frontier slots split off (Q6); producers and consumers import it; registry `literal_scan` tightened to the enum | M0 merged; owner module chosen (Q3); slot split decided (Q6) | Smoke green; zero bare `effective_action` literals outside the owner; parity fixtures for status/should-run unchanged | Revert to literals; registry keeps the set |
| M2 | Route-to-disposition projection, the `decide_loop_disposition` decision table, and the cross-runtime sets published through a shared contract with generated Python and TypeScript bindings, following the coordination contract generator | M1 merged; Q2 and Q7 decided | Generator `--check` and smoke green; `settlement.ts` and `transaction.py` read the generated set | Regenerate from prior contract |
| M3 | Per-field retirement of legacy should-run fields, one field per PR, budgets lowered to zero and the field removed | Field has zero external readers proven by producer/reader research | Schema-reduction record per `AGENTS.md`; Appendix B entry | Restore field from the last writer |
| M4 | Twin budget lowered with each replacement-first cutover from the migration RFC | Each cutover PR | Budget edit in the same diff | None needed; budget follows code |

## 12. Open decisions

1. **Registry location.** Owner: kernel maintainers. M0 implements
   `loopx/semantics/` because the scope is repository-wide and neither
   `loopx/control_plane/` nor `docs/reference/` is; the package holds only the
   two JSON files and the scanner and is imported by no product code. This is
   a proposal until recorded in Appendix B. Needed before M1.
2. **Merge `LoopXTurnRoute` and `LoopDisposition`?** Owner: Turn driver owner.
   The projection is total but not injective (`blocked` and `wait` both map to
   `wait`), and `stop`, `terminal`, `contract_error` exist on one side only.
   The `same_concept` relations record the four shared verdicts.
   Recommendation: keep both, publish the projection in M2, revisit after the
   managed-step consumer matures. Needed before M2.
3. **Owner module for `EffectiveAction`.** The registry declares no owner
   today because no symbol exists; the literal scan is the only check.
   Options: `quota/should_run_packet.py` (largest producer), a new
   `quota/effective_action.py`, or the TypeScript `turn_envelope.ts` with a
   Python import per the migration RFC. Recommendation: TypeScript owner with
   generated Python binding only if M2 lands first; otherwise
   `quota/effective_action.py`. Needed before M1.
4. **Companion glossary.** Whether to add `docs/reference/glossary.md`
   generated from the registry `meaning` fields and the inventory. Owner: docs
   maintainers. Recommendation: yes, in M1, generated so it cannot drift.
5. **Term-family naming rule.** Whether new identifiers in the `gate`,
   `scope`, `packet`, `handoff`, `settlement` families must cite a glossary row
   in review. This is a review rule, not a smoke; recommendation is to adopt it
   in the first-review roster once the glossary exists.
6. **Split the three `effective_action` slots.** The decision slot, the
   `agent_scope_frontier` slot, and the replay observation slot share one field
   name in one Turn Envelope and carry three vocabularies; `skip` is compared
   but never produced. Options: rename the observation and frontier slots,
   or keep one field with a registered union. Owner: Turn Envelope owner.
   Recommendation: rename in M1 so the enum in Q3 has one meaning. Needed
   before M1.
7. **Relation to `maintainability_ratchet.py`.** Whether the inventory
   ratchets adopt its reviewed exception lifecycle (`retirement_plan`, stale
   exception detection) or stay plain budgets. Recommendation: adopt it in M2
   when generation lands, so a fork with a documented reason can be excepted
   instead of budgeted. Owner: canary maintainers.
8. **Promotion rule from inventory to registry.** Whether a mapped carrier
   with three or more external consumer modules or a cross-runtime twin must be
   curated. Recommendation: yes as a review rule now, enforced by the smoke
   only after a quarter of inventory history exists. Owner: kernel maintainers.

## Appendix A: Execution ledger (non-normative)

### 2026-09-15 — M0 opened with the RFC

- **Baseline:** `1dc6ad8d8`
- **Delivered:** registry with four vocabularies, one projection, one schema
  version, six legacy-field budgets, one twin budget; drift smoke; duplicate
  `TURN_ENVELOPE_SCHEMA_VERSION` in `driver.py` replaced by an import.
- **Evidence:** Section 9 rows; see Appendix C.
- **Known gaps:** the projection check imports the private
  `_route_to_disposition` until M2 publishes it.
- **Effect on normative design:** none.

### 2026-09-15 — M0 revised after review; scope made repository-wide

- **Baseline:** `1dc6ad8d8`
- **Trigger:** a review found the first literal scan blind to TypeScript
  (`===` never matched), two unregistered values already on the baseline
  (`observe_replay`, `block_replay`), and an owner check that silently skipped
  any owner written without a symbol.
- **Delivered:** registry moved to `loopx/semantics/vocabulary_v0.json` and
  widened to 26 vocabularies, 46 owner symbols, 9 relations, and a coverage
  floor; generated inventory `inventory_v0.json` with generator `--check` and
  unit test; smoke rewritten with fixed dispatch forms (comparison, assignment,
  ternary, membership, conditional expression), AST-based owner resolution,
  owner exclusivity, inventory freshness and fork/conflict budgets; the
  `HANDOFF_MODES` fixture fork derived from the enum.
- **Evidence:** Appendix C, E6 to E10.
- **Known gaps:** the load-bearing `decide_loop_disposition` table is still
  prose only (M2); the literal scan cannot attribute a literal to one of the
  three `effective_action` slots (Q6); the scan cannot follow values through
  variables, so two quota error codes are registered as variable-sourced with
  a producer check rather than proven.
- **Effect on normative design:** Sections 1 to 5, 8, 9, 11, 12 revised;
  I8 added. Recorded as the same-day revision of an unmerged draft.

### 2026-09-15 — M0 measurement repaired after a second review

- **Baseline:** `1dc6ad8d8`
- **Trigger:** a second review ran 14 attacks against the smoke. Seven escaped:
  lowering `coverage_floor` (individually or all at once), raising
  `inventory_ratchets` or a retirement budget, and — decisively — dropping an
  owner *and* lowering the matching floor in one diff. The floor lived in the
  same file it guarded and was compared with `>=`, so the registry could relax
  its own ratchet. I5 and I8 were prose, not machine-enforced.
- **Also found:** collision detection ran only over string constants, so the 599
  multi-value carriers were listed but never compared. Four same-name forks were
  already on the baseline, including `SOURCE_SURFACES` defined four times with
  four different value sets, plus 19 invisible twins. Separately, 16 of the 18
  `conflicting_values` names were module-local conventions (`SCHEMA_VERSION`
  sixteen times, `COMMAND`, `REQUEST_SCHEMA`, `SURFACE`), so the budget was
  mostly measuring local naming.
- **Delivered:** anchors `COVERAGE_ANCHOR`, `COVERAGE_SUFFIX_ANCHOR`,
  `BUDGET_ANCHOR`, `RETIREMENT_ANCHOR` in the smoke, closing all seven escapes;
  `multi_value_name_collisions` giving enums, closed sets, `Literal` aliases, and
  `as const` arrays the string-constant collision rule, with the four forks and
  19 twins budgeted at today's count; `MODULE_LOCAL_CONVENTION` keeping
  module-local names in the visible totals but out of the semantic budgets
  (`conflicting_values_semantic` 2, `same_runtime_forks_semantic` 18); advisory
  merge-candidate report over the 32 groups of distinct names sharing a value
  set; two scanner tests on a dedicated collision fixture; I9 added and the
  Section 9 limits stated.
- **Evidence:** Appendix C, E11 to E13.
- **Known gaps:** collisions are keyed by name, so a rename still launders one;
  single-element carriers are invisible; the literal scan can misread an
  unrelated comparison sharing a line.
- **Effect on normative design:** I5 and I8 restated as enforced rather than
  intended; I9 added; the Section 5 table and Section 9 rows updated. Moving an
  anchor is now the only way to relax a budget, and it is a code edit.
- **Open question sharpened:** Q7 may now collapse from "adopt the
  `maintainability_ratchet` exception lifecycle" to "share its anchor pattern",
  because this smoke already uses that pattern.

## Appendix B: Decision log

| Date | Decision | Owner / approval | Alternatives | Normative sections changed |
| --- | --- | --- | --- | --- |
| — | none recorded | — | — | — |

## Appendix C: Evidence registry

| Evidence id | Claim | Baseline / environment | Artifact or command | Result | Privacy / validity boundary |
| --- | --- | --- | --- | --- | --- |
| E1 | Three definitions of the envelope schema constant | `1dc6ad8d8` | `rg -n 'TURN_ENVELOPE_SCHEMA_VERSION\s*=' loopx` | 3 files | Source only |
| E2 | 28 distinct `effective_action` literals across `loopx/` | `1dc6ad8d8` | the smoke's `literal_scan` | 28 | Pattern-bound; prose mentions excluded |
| E3 | 43 py/ts twins under the control plane | `1dc6ad8d8` | smoke twin report | 43 | Same-basename rule only |
| E4 | Legacy field spread | `1dc6ad8d8` | smoke budget report | see registry | Module mentions, not call sites |
| E6 | Global census of closed-set carriers | `1dc6ad8d8` | `python3 scripts/generate_semantic_inventory.py` summary | 102 enums, 490 closed sets, 8 aliases, 40 arrays, 2002 named constants, 166 twins, 25/58 forks, 18/59 conflicts | AST and `as const` text scan; module-level only |
| E7 | First scan pattern captured zero TypeScript sites | `1dc6ad8d8` | pattern applied to every `.ts` line containing `effective_action` | 0 of 7 dispatching files matched; `===` always failed | Pattern-bound |
| E8 | Two `effective_action` values unregistered on baseline while the first smoke was green | `1dc6ad8d8` | `turn_journal.ts:656` ternary | `observe_replay`, `block_replay` | Same |
| E9 | Owner check skipped a bare-module owner | `1dc6ad8d8` | first smoke's `if "::" in python_owner` | `effective_action` owner never checked | Code reading plus mutation |
| E10 | Twenty drift mutations fail closed (TS `===`, TS ternary, Python membership, Python `==` through `or ""`, bare owner, dropped owner, narrowed suffixes, renamed vocabulary, forked symbol, TS value removed, enum widened, projection changed, legacy field regrown, stale inventory, third conflicting spelling, dead value, lost variable producer, broken subset, forked schema version, unknown registry key) | `1dc6ad8d8` + local edit, inventory regenerated where the edit adds a carrier, restored after each run | temporary edit then the smoke with `python3 -B` | 20/20 exit 1 naming the rule, value, or file | Local exercise, not a committed test |
| E5 | Nine drift mutations fail closed (unregistered literal with and without digits, forked constant, TS kind removed, Python enum widened, projection changed, legacy field regrown, dead registry value, new py/ts twin) | `1dc6ad8d8` + local edit, restored after each run | temporary edit then the smoke, run with `python3 -B` | 9/9 exit 1 with the offending value or file named | Local exercise, not a committed test; a same-size same-second edit needs `-B` to defeat stale bytecode |
| E11 | The registry could relax its own ratchet in one diff | `1dc6ad8d8` + local edit | fourteen registry mutations: lower one floor, lower all floors, lower a floor while dropping the owner it counts, raise every `inventory_ratchets` entry, raise one entry, raise a retirement budget | 7 escaped before the anchors, 0 escape after; each caught failure names the anchored value | Local exercise, not a committed test |
| E12 | 599 multi-value carriers were listed but never compared | `1dc6ad8d8` | collision rule applied to enums, closed sets, `Literal` aliases, and `as const` arrays | 4 same-name forks (10 definitions) and 19 twins already on the baseline, none budgeted; `SOURCE_SURFACES` alone has four divergent value sets | Name-keyed; a rename removes a name from the comparison |
| E13 | The conflict budget mostly measured local naming | `1dc6ad8d8` | `MODULE_LOCAL_CONVENTION` applied to `conflicting_values` and `same_runtime_forks` names | 16 of 18 conflicts and 7 of 25 forks are module-local conventions; the semantic subsets are 2 and 18 | Classification is a name pattern, documented in the scanner and pinned by a fixture test |

## Appendix D: Rejected or superseded alternatives

See Section 6. A single-PR enum unification was rejected because the three
enums have distinct change reasons; the evidence that could reopen it is a
projection proven to be a bijection after M2.

## Appendix E: Incident and review lessons

- Hand-synchronized parallel constant lists across runtimes pass review until
  the day one side changes; a parity check must exist before the second copy is
  accepted.
- A private extraction of a shared constant looks harmless in a large module
  and is the most common way a schema version forks. Test fixtures are the
  second most common: `HANDOFF_MODES` was copied into an e2e fixture.
- A literal scan that only accepts `[a-z_]` silently skipped a `_v2` spelling
  during the M0 mutation exercise. Capture every quoted string and validate the
  shape separately, so a malformed value is reported instead of ignored.
- A scan pattern written from Python examples matched no TypeScript at all,
  and a guard that is green on a baseline containing violations proves only
  that the guard is blind. Mutation-test every runtime the registry claims to
  cover before declaring an invariant.
- When the registry is both the specification and the validator's input, a
  data edit can weaken the validator. Keep the recognised forms in code, floor
  the coverage counts, and reject owners that are not `module::Symbol`.
- A ratchet on names alone lets an already-conflicting name gain a third
  spelling. Budget definitions as well as names.
- One field name can carry several vocabularies inside one envelope; a scan
  that sees the field cannot see the slot. Record the slots as a relation so
  the ambiguity is a registered fact, not an accident the registry blesses.
