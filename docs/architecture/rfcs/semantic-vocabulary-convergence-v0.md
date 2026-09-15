# RFC: Semantic Vocabulary Convergence and Commit-Time Drift Checks (v0)

- **RFC status:** Draft
- **Delivery maturity:** Partial (M0 registry and drift smoke ship with this RFC)
- **Authors / owners:** LoopX contributors; control-plane kernel maintainers own approval
- **Created:** 2026-09-15
- **Last normative revision:** 2026-09-15
- **Implementation baseline:** `1dc6ad8d8`
- **Related contracts:** `loopx/control_plane/semantic_vocabulary_v0.json`,
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

1. **What becomes authoritative.** One machine-readable registry,
   `loopx/control_plane/semantic_vocabulary_v0.json`, names each registered
   cross-module vocabulary, the exact modules allowed to define it, the total
   projections between vocabularies, and the retirement budgets the repository
   has agreed to ratchet down. A public smoke,
   `examples/control_plane/semantic-vocabulary-drift-smoke.py`, checks the code
   against the registry on every premerge and full-public run. A change that
   widens a vocabulary, forks a constant, or regrows a legacy surface must edit
   the registry in the same diff, so the reviewer sees the semantic change as a
   change.
2. **What remains unchanged.** Runtime behavior, wire formats, and the enum
   classes themselves. Each enum keeps living in its owner module; the registry
   is checked against code, it does not generate code in this stage.
3. **Default and opt-in boundary.** The check is always on for the repository.
   It has no runtime flag because it never runs inside the product.
4. **Principal constraint.** Fail closed and deterministic. An unregistered
   literal, a second defining module, a budget overrun, or a registry value no
   module carries each fails the smoke. The smoke reads only tracked sources and
   prints no private data.
5. **Not approved by this RFC.** Merging the three Turn outcome enums into one,
   deleting any legacy should-run field, deleting any Python twin module, or
   renaming any existing value. Those are later milestones with their own gates
   under the schema-reduction rule in `AGENTS.md`.

## 2. Problem and motivation

LoopX has grown by many small agent-driven PRs. Each PR added the vocabulary it
needed where it needed it. The result is not wrong behavior but drift: the same
concept spelled several ways, the same constant defined in several files, and
open string sets that any module may widen without anyone noticing. Reviewers
cannot tell from a diff whether a new literal is a new state or a typo, and
documentation cannot stay in step with a set nobody enumerates.

Concrete failures audited on the baseline:

- `TURN_ENVELOPE_SCHEMA_VERSION` was defined three times:
  `loopx/control_plane/quota/turn_envelope.py:16`,
  `loopx/control_plane/quota/turn_envelope.ts:13`, and a private copy in
  `loopx/control_plane/turn_driver/driver.py:31`. A version bump in one file
  would have silently split the envelope contract. M0 removes the copy.
- The Turn result kinds exist twice by hand: `LoopXTurnResultKind` in
  `transaction.py:28` (12 values) and `TURN_RESULT_KINDS` in
  `settlement.ts:49` (12 values). They match today; no test asserted it.
- `effective_action` is an open string set. 28 distinct literals are produced
  by 11 modules and dispatched by string comparison; there is no enum on either
  side and the documentation mentions about ten of them in prose.
- Three near-isomorphic Turn outcome vocabularies coexist:
  `LoopXTurnResultKind` (12), `LoopXTurnRoute` (8), `LoopDisposition` (8). The
  route-to-disposition projection is a private dictionary in
  `loop_controller.py:127-135`; nothing declared that it is total.
- Six should-run decision fields the documentation already calls legacy
  (`execution_obligation`, `heartbeat_recommendation`, `work_lane_contract`,
  `external_evidence_observation`, `goal_boundary`, `protocol_action_packet`)
  are still mentioned by 7 to 35 Python modules each, with no ratchet stopping
  new consumers.
- 43 same-basename `.py`/`.ts` module pairs exist under `loopx/control_plane`
  while the migration RFC is replacement-first. The count had no guard.
- Word families spread without a glossary: under `loopx/`, identifiers
  containing `gate` number 561, `scope` 536, `packet` 285, `handoff` 200,
  `settlement` 170.

The current owners cannot solve this locally because every fix is
cross-module by definition: the Turn driver, quota, todos, and TypeScript
runtime each own one spelling of the same idea.

### Invariants

- **I1 Single owner.** Every registered vocabulary or constant has exactly the
  defining modules the registry lists. Everyone else imports.
- **I2 Closed sets.** Every value a registered vocabulary may carry is listed.
  The code carries no unregistered value and the registry lists no value the
  code does not carry.
- **I3 Cross-runtime parity.** When a vocabulary has a Python and a TypeScript
  owner, both carry the identical set.
- **I4 Total projections.** A registered projection names every source value
  exactly once, either mapping it or declaring it rejected.
- **I5 Ratchets only fall.** Retirement and twin budgets may be lowered in any
  PR. Raising one requires maintainer approval recorded in Appendix B.
- **I6 Same-diff visibility.** A semantic change and its registry edit land in
  one reviewable diff.
- **I7 Deterministic and public-safe.** The check reads tracked sources only,
  needs no network or credentials, and its failure text names files and
  values, never private data.

## 3. Scope and non-goals

### In scope

- The registry file, its schema, and the ownership rule for editing it.
- The drift smoke and its placement in the premerge and full-public fleets.
- The vocabularies registered at M0: `turn_result_kind`, `turn_route`,
  `loop_disposition`, `effective_action`, the route-to-disposition projection,
  the Turn Envelope schema version, the six legacy should-run fields, and the
  control-plane twin count.
- The later milestones that turn `effective_action` into a typed enum, publish
  the projection through the contract, and retire legacy fields and twins under
  existing repository rules.

### Non-goals

- Changing any runtime decision, payload shape, or wire format.
- Registering every string in the repository. Only vocabularies that cross a
  module or runtime boundary and are dispatched on belong here.
- Replacing `turn_transaction_contract.json` or
  `coordination_state_contract_v0.json`. Those remain the owners of their
  phases and records; this registry may reference them, not restate them.
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
  template for the generation stage proposed in M2.
- The premerge selector (`loopx canary premerge --from-git-diff`) and the
  full-public workflow discover every tracked `examples/**/*-smoke.py`, so a
  smoke under `examples/control_plane/` needs no registration.
- `AGENTS.md` already requires typed enums for state classification, forbids a
  second source of truth in Python for control-plane authority, and requires
  maintainer approval for any schema reduction. This RFC adds the check that
  makes those rules observable in a diff; it does not change them.
- Existing module-size ratchets (`STARTER_MODULE_LIMITS` in the CLI module-size
  smoke) establish the repository precedent for frozen baselines that may only
  shrink.

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

`semantic_vocabulary_v0.json`, `schema_version` `loopx_semantic_vocabulary_v0`:

| Key | Content | Check |
| --- | --- | --- |
| `vocabularies.<name>.owners` | `python: path::Symbol`, optional `typescript: path::CONST` | Enum members and `as const` array equal `values` (I1, I2, I3) |
| `vocabularies.<name>.literal_scan` | roots, suffixes, regex capturing the value | Every captured literal is registered; every registered value is captured somewhere (I2) |
| `projections.<name>.mapping` | source value to target value or `null` | Keys equal the source vocabulary; mapped values match the owner function; `null` routes raise (I4) |
| `schema_versions.<name>` | constant name, value, owner modules | The only defining modules are the listed owners (I1) |
| `retirement_ledger.<group>.fields` | per-field Python and TypeScript module budgets | Actual module counts are at or below budget (I5) |
| `dual_runtime_twins` | root and module budget | Same-basename `.py`/`.ts` pair count is at or below budget (I5) |

Values are additive. Removing a value, a field, or an owner is a schema
reduction and follows the `AGENTS.md` rule: enumerate the affected surfaces,
research producers and readers, and record maintainer approval.

### Command or event lifecycle

The check has one command: run the smoke. It is idempotent and has no side
effects. Failure text names the vocabulary, the offending files, and the values
so the fix is mechanical: register the value, import the constant, or lower the
scope of the change.

### Provider or extension contract

New vocabularies are added by a PR that adds the registry entry and, where a
TypeScript owner exists, its `as const` array. A vocabulary qualifies when it
is dispatched on by more than one module or crosses the Python/TypeScript
boundary.

## 6. Alternatives and design choices

| Alternative | Why not now |
| --- | --- |
| Unify the three Turn enums into one in a single PR | Breaks I5 style incrementalism; the three enums have different owners and change reasons (settlement, route, controller). Register and project first, then merge only where a projection proves identity (Section 12, Q2). |
| Rely on `mypy` `Literal` types | Does not cover TypeScript, JSON payloads, or the CLI; the drift here lives at exactly those boundaries. |
| Documentation glossary only | Cannot fail a build; the repository already has eleven documents calling themselves a mental model and no glossary, which is the symptom. |
| Generate bindings from the registry immediately | Premature until owners are settled. Generation is M2 and follows the coordination contract precedent. |
| Grep-based lint in CI without a registry | Encodes the allowed set in the linter, which becomes a second registry with no review trail. |

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

- **Admission.** M0 lands with the registry matching the baseline exactly, plus
  the one duplicate constant removed so the owner check is green.
- **Rollback.** Deleting the smoke and registry restores the previous state
  with no runtime effect. Later milestones each carry their own rollback in
  Section 11.
- **Point of no return.** None in M0. M3 field removals are the first
  irreversible step and are gated individually.

## 9. Validation and acceptance

| Claim | Test or evidence | Required result | Boundary / exclusions |
| --- | --- | --- | --- |
| Registry matches the code at baseline | `python3 examples/control_plane/semantic-vocabulary-drift-smoke.py` | `ok` with budget report | Proves parity for registered vocabularies only |
| A widened `effective_action` set fails closed | Add an unregistered literal in a producer, run the smoke | Failure names the value and file | Mutation exercise; not a committed test |
| A forked schema constant fails closed | Redefine `TURN_ENVELOPE_SCHEMA_VERSION` in a non-owner module | Failure lists the extra defining module | Same |
| Python and TypeScript result kinds cannot diverge | Remove one entry from `TURN_RESULT_KINDS`, run the smoke | Failure names the missing value | Same |
| No behavior change from removing the duplicate constant | `pytest tests/test_loopx_turn_transaction.py tests/test_loop_turn_loop_controller.py tests/test_turn_loop_disposition.py tests/test_loopx_turn_managed_step.py` and `loopx canary premerge --from-git-diff` | pass | Environment failures already present on `main` are excluded when reproduced on a clean tree |
| Docs governance accepts the RFC pair | `python3 examples/docs-governance-smoke.py` | pass | Checks mirror, links, index |

## 10. Operational contract

The check cannot affect a running system: it executes only in premerge and CI.
Its operator surface is the failure text. No observability, capacity, or
on-call contract applies.

## 11. Normative delivery plan

| Milestone | Shipped behavior | Entry gate | Exit evidence | Rollback |
| --- | --- | --- | --- | --- |
| M0 | Registry, drift smoke, duplicate `TURN_ENVELOPE_SCHEMA_VERSION` removed, RFC index entry | This RFC opened | Section 9 rows 1-6 green | Delete smoke and registry |
| M1 | `EffectiveAction` typed enum in one owner module; producers and consumers import it; registry `literal_scan` tightened to the enum | M0 merged; owner module chosen (Q3) | Smoke green; zero bare `effective_action` literals outside the owner; parity fixtures for status/should-run unchanged | Revert to literals; registry keeps the set |
| M2 | Route-to-disposition projection and result kinds published through a shared contract with generated Python and TypeScript bindings, following the coordination contract generator | M1 merged; Q2 decided | Generator `--check` and smoke green; `settlement.ts` and `transaction.py` read the generated set | Regenerate from prior contract |
| M3 | Per-field retirement of legacy should-run fields, one field per PR, budgets lowered to zero and the field removed | Field has zero external readers proven by producer/reader research | Schema-reduction record per `AGENTS.md`; Appendix B entry | Restore field from the last writer |
| M4 | Twin budget lowered with each replacement-first cutover from the migration RFC | Each cutover PR | Budget edit in the same diff | None needed; budget follows code |

## 12. Open decisions

1. **Registry location.** Owner: kernel maintainers. Options: `loopx/control_plane/`
   next to the transaction contract (recommended, matches the shared-contract
   precedent) or `docs/reference/`. Needed before M1.
2. **Merge `LoopXTurnRoute` and `LoopDisposition`?** Owner: Turn driver owner.
   The projection is total but not injective (`blocked` and `wait` both map to
   `wait`), and `stop`, `terminal`, `contract_error` exist on one side only.
   Recommendation: keep both, publish the projection in M2, revisit after the
   managed-step consumer matures. Needed before M2.
3. **Owner module for `EffectiveAction`.** Options: `quota/should_run_packet.py`
   (largest producer), a new `quota/effective_action.py`, or the TypeScript
   `turn_envelope.ts` with a Python import per the migration RFC.
   Recommendation: TypeScript owner with generated Python binding only if M2
   lands first; otherwise `quota/effective_action.py`. Needed before M1.
4. **Companion glossary.** Whether to add `docs/reference/glossary.md` that
   lists each registered vocabulary with its meaning and links the protocol doc
   that owns it, generated from the registry `meaning` fields. Recommendation:
   yes, in M1, generated so it cannot drift. Owner: docs maintainers.
5. **Term-family naming rule.** Whether new identifiers in the `gate`,
   `scope`, `packet`, `handoff`, `settlement` families must cite a glossary row
   in review. This is a review rule, not a smoke; recommendation is to adopt it
   in the first-review roster once the glossary exists.

---

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
| E5 | Nine drift mutations fail closed (unregistered literal with and without digits, forked constant, TS kind removed, Python enum widened, projection changed, legacy field regrown, dead registry value, new py/ts twin) | `1dc6ad8d8` + local edit, restored after each run | temporary edit then the smoke, run with `python3 -B` | 9/9 exit 1 with the offending value or file named | Local exercise, not a committed test; a same-size same-second edit needs `-B` to defeat stale bytecode |

## Appendix D: Rejected or superseded alternatives

See Section 6. A single-PR enum unification was rejected because the three
enums have distinct change reasons; the evidence that could reopen it is a
projection proven to be a bijection after M2.

## Appendix E: Incident and review lessons

- Hand-synchronized parallel constant lists across runtimes pass review until
  the day one side changes; a parity check must exist before the second copy is
  accepted.
- A private extraction of a shared constant looks harmless in a large module
  and is the most common way a schema version forks.
- A literal scan that only accepts `[a-z_]` silently skipped a `_v2` spelling
  during the M0 mutation exercise. Capture every quoted string and validate the
  shape separately, so a malformed value is reported instead of ignored.
