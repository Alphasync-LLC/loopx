# RFC: Goal-scoped Capability Portfolio and Connector Lifecycle (v0)

- **RFC status:** Draft
- **Delivery maturity:** Proposal; existing catalog, hooks and external-evidence slices are partial prerequisites
- **Authors / owners:** LoopX capability and control-plane maintainers
- **Created:** 2026-09-21
- **Last normative revision:** 2026-09-21
- **Implementation baseline:** `0ef7ebd749ec97a698a8fc7f2a29844dd368689b`
- **Related contracts:** [overall roadmap](loopx-overall-roadmap-v0.md),
  [research exploration](research-exploration-control-plane-v0.md),
  [agent loop effects](agent-loop-effect-interpreter-v0.md),
  [post-outcome memory utility](post-outcome-memory-utility-attribution-v0.md),
  [extension reference](../../reference/extensions.md), and
  [external-evidence lifecycle PR #4813](https://github.com/loopx-project/loopx/pull/4813)
- **Language mirror:** [中文版](goal-scoped-capability-portfolio-v0.zh-CN.md)

## Document map and maintenance contract

Sections 1–10 are the durable design and acceptance contract. Section 11 is
the normative delivery plan. Section 12 contains unresolved decisions.
Appendices are non-normative evidence and history. RFC maturity and delivery
maturity are independent. The English and Chinese documents are a semantic mirror
and must change together.

---

## 1. Decision summary

LoopX will add a **Goal-scoped Capability Portfolio** that lets an Agent reason
about, select, compose, evaluate, degrade and retire capabilities against the
Goal's outcome and acceptance gaps. It owns adoption decisions and effect
receipts. It does not copy capability configuration, provider state, evidence,
Todo state, authority grants or memory into another source of truth.

The portfolio composes existing owners:

1. the capability catalog describes what can be considered;
2. original configuration and provider owners prove the effective revision;
3. `agent_context` projects a bounded plan at `before_plan`, freezes a selected
   route at `before_delegate`, and returns typed outcomes at
   `after_delegate_result`;
4. the external-evidence lifecycle qualifies repeatable source methods and
   connectors;
5. Decision Context, Explore and reward memory remain downstream consumers
   with their own admission rules.

The default is advisory and fail-open. An unavailable portfolio must not stop
ordinary work unless the selected Todo explicitly requires the missing
capability. Self-discovery can recommend or run a bounded trial within existing
authority; it cannot install software, enable a provider, enlarge network or
write scope, change model authorization, or approve a protected effect.

This RFC does not approve automatic capability installation, a connector
marketplace, domain-specific ranking in Core, or finance execution authority.

## 2. Problem and motivation

LoopX already has a catalog, extensions, readiness checks, Goal/Todo capability
requirements, three Agent-context hooks, external-evidence planning, Explore,
Decision Context and reward memory. A fresh Agent still has to infer how these
pieces fit together. A domain prompt or local strategy document often supplies
the missing organization, so adoption reasoning disappears across sessions and
another Agent may repeat the same discovery, select redundant sources or treat
provider readiness as evidence quality.

Connectors expose the same gap. The current connector registry is useful
inventory and usage telemetry. Registration, readiness and call counts do not
prove source coverage, freshness, rights, execution, parent admission or
decision value. A stable source should be promoted only after discovery and a
bounded trial, and should later degrade or retire when it becomes stale,
unreliable, costly or unused.

Concrete example: a research Goal needs current primary evidence, independent
counterevidence and a read-heavy worker. The Agent should discover an existing
external-research method, one qualified source connector and an eligible worker
route; explain why each was selected; freeze revisions and budget; record
partial coverage and failures; and tell whether the result changed the
decision. Today those facts live in separate projections and prose.

### Invariants

- Portfolio adoption never creates or enlarges authority.
- Configuration stays with its original owner; the portfolio stores only
  exact references, digests and bounded readback.
- `ready`, `executed`, `read`, `admitted`, `decision-changing` and
  `domain-eligible` remain distinct states.
- One source observed through multiple connectors or workers is not independent
  evidence.
- Unknown, stale, partial and unavailable are explicit; an empty result is not
  complete coverage.
- A model response, tool call, commit or connector invocation is not effect
  evidence by itself.
- Replays are idempotent and revision drift cannot silently reuse an old plan.
- CLI, managed Turn, frontend and Lark read the same public projection.
- Feature-off and portfolio-failure paths preserve the existing Agent route.

## 3. Scope and non-goals

### In scope

- a provider-neutral capability descriptor reference and Goal adoption record;
- a bounded capability composition DAG with explicit selection and skip reasons;
- trial, use, effect, degradation and retirement receipts;
- a connector qualification profile built on the external-evidence lifecycle;
- injection through `before_plan`, `before_delegate` and
  `after_delegate_result`;
- exact effective-configuration and provider-revision readback;
- shared CLI/frontend/Lark inspection and feedback;
- finance and one non-finance journey as qualification consumers.

### Non-goals

- replacing Goal, Todo, quota, claim, lease or shared-authority state;
- copying provider credentials, raw source bodies or private configuration;
- moving Decision Context, Explore or reward-memory state into the portfolio;
- inventing a universal score across unrelated capabilities;
- automatic installation, permission grant, payment, publishing, signing or
  trading;
- treating a portfolio recommendation as a runtime or domain authorization;
- requiring every Turn to scan every installed capability.

## 4. Current-system contract

At the implementation baseline:

- the capability catalog and extension manifests describe installed and enabled
  implementations, declared providers, hooks, permissions and readiness;
- capability admission and capability memory expose bounded Goal/provider and
  host observations but do not grant authority;
- Todo capability gates answer whether a known task can execute; they do not
  discover a Goal's missing capability;
- `agent_context` supports `before_plan`, `before_delegate` and
  `after_delegate_result` with bounded guidance-only projections;
- the connector registry stores inventory and simple usage telemetry, not
  source qualification;
- the external-evidence slice in PR #4813 proposes typed discovery, plan,
  receipt observation, parent admission and retirement while keeping provider
  execution outside Core;
- Decision Context owns decision evidence, Explore owns research topology, and
  reward memory owns qualified reusable outcome lessons.

This RFC composes those owners. It does not make PR #4813 merge-ready or claim
that its end-to-end provider qualification has shipped.

## 5. Proposed architecture

### Ownership and authority

The TypeScript control plane owns normalization, identity, transition legality
and the public portfolio projection. Python remains an adapter while the
TypeScript migration is active.

The portfolio owns only:

- why a Goal considered, trialed, adopted, degraded or retired a capability;
- the selected composition and its exact revision;
- use/effect receipts and review triggers.

It references, without copying:

- catalog and extension declarations;
- effective configuration and provider readiness;
- Todo requirements and authorization decisions;
- external-evidence call/admission receipts;
- Decision Context, Explore and memory artifact identifiers.

No chat, UI, connector, worker or domain capability may become an alternate
portfolio writer. Mutations pass through one typed reducer and the configured
Goal authority provider.

### State model and schema

#### `capability_catalog_entry_v1`

This is a normalized reference to an existing capability declaration:

```text
capability_id, capability_revision, owner_ref
outcome_tags[], lifecycle_phases[]
input_schema_ref, output_schema_ref, receipt_schema_ref
provider_requirements[], connector_requirements[]
required_host_capabilities[], required_authority_scopes[]
privacy_class, cost_class, readiness_ref, fallback_ref
```

The portfolio does not edit this record.

#### `goal_capability_adoption_v1`

```text
goal_id, adoption_id, portfolio_revision
gap_ref, capability_id, capability_revision
status = candidate | trial | adopted | degraded | retired
reason, alternatives[], expected_effects[]
effective_config_ref, effective_config_revision, config_digest
trial_budget, trial_window, authority_refs[]
use_receipt_refs[], effect_receipt_refs[]
review_after, degradation_conditions[], retirement_conditions[]
created_at, updated_at
```

`gap_ref` points to an outcome or acceptance gap; it does not create a second
Todo. A transition needs an expected current revision. Omitting a field preserves
it; explicit clear semantics are defined per optional field.

#### `capability_composition_plan_v1`

```text
goal_id, todo_id?, turn_id?, composition_id, portfolio_revision
gap_refs[], nodes[], edges[], selected_at, expires_at
node: capability/provider/connector/worker/reducer reference,
      phase, input/output schema, exact revision, budget,
      required authority, required read/write scope,
      disposition, reason
```

`composition_id` is a canonical digest of all normalized decision-relevant
fields. The graph must be acyclic. Each candidate receives `selected`,
`skipped`, `unavailable` or `incompatible` with a reason. A plan is guidance,
not execution authority.

#### `capability_use_receipt_v1`

```text
receipt_id, composition_id, node_id, phase
goal/todo/turn identity, exact provider/model/connector revision
started_at, completed_at, cost, latency
coverage, freshness, source_families[], typed_failures[]
output_digest, result_ref
parent_disposition = adopted | ignored | refuted | unknown
decision_effects[], next_lifecycle_proposal
```

For non-evidence capabilities, coverage and source families may be explicit
`not_applicable`; they must not be fabricated. Persistence success, retrieval,
quality qualification and useful application are separate facts.

### Command and event lifecycle

```text
Goal gap observed
  → catalog candidates projected
  → composition previewed
  → bounded trial or existing adoption selected
  → exact config/provider revisions read back
  → route frozen at before_delegate
  → typed results observed at after_delegate_result
  → parent adopts / ignores / refutes / leaves unknown
  → keep / reconfigure / degrade / retire proposal
```

The mutation identity is `(goal_id, adoption_id, expected_revision,
operation_id)`. Replay with the same intent returns the original receipt;
identity drift fails closed. Provider/config revision drift invalidates the
plan. Lost responses reconcile through receipt readback before retry.

If a portfolio cannot be read, planning continues without portfolio guidance
and reports `coverage=unknown`. If a Todo explicitly requires the missing
capability, normal capability admission blocks that Todo; the portfolio does
not weaken it.

### Connector qualification profile

Connectors use the external-evidence lifecycle rather than a parallel state
machine:

```text
external-research discovery
  → connector candidate
  → bounded trial
  → parent qualification
  → active
  → degraded | retired
```

A connector descriptor adds source family, supported operations, coverage
domain, publication/observation-time semantics, rights, cost, failure and
fallback declarations. A call receipt binds the exact plan/provider revision,
source references, coverage interval, freshness, rights snapshot, cost,
latency, failure and output digest. Registration and readiness remain
inventory facts. Parent qualification remains distinct from finance evidence
eligibility or another domain's admission.

### Runtime injection

- **`before_plan`:** project the current gap, active adoptions, stale or
  unavailable nodes and a minimal useful composition. Allow an empty selection.
- **`before_delegate`:** freeze worker/connector/provider revisions, budget,
  schemas, authority references and composition digest. Domain capabilities
  describe the question and acceptance criteria; the generic delegation owner
  controls capacity, route and result receipts.
- **`after_delegate_result`:** consume typed result receipts and record parent
  disposition, cost, coverage and decision effect. Raw worker prose is not an
  adoption receipt.

An optional Turn-start summary contains only portfolio revision, current gap,
selected composition, stale/unavailable nodes and the next review trigger. The
full catalog and history stay out of the prompt envelope.

## 6. Alternatives and design choices

### Domain skills organize capabilities

This is useful for early experiments but loses adoption history across Agents,
duplicates runtime discovery and makes each domain implement failure and
authority rules. Domain capabilities will keep domain semantics and acceptance
criteria, while the portfolio owns generic organization.

### Connector registry becomes the quality authority

Rejected. A registry is inventory and telemetry. Source quality and parent
admission require exact call evidence, time, coverage, rights and domain rules.

### Decision Context owns capability planning

Rejected. Decision Context assembles decision evidence; it must not become a
configuration, provider or authorization owner.

### Fully automatic self-installation

Rejected for v0. It collapses recommendation, configuration and authority. The
portfolio may propose installation or enablement through existing governed
owners, but cannot perform it implicitly.

## 7. Safety, privacy, and compatibility

- The portfolio is advisory by default and stores no secrets or raw private
  payloads.
- Public projections redact private source, account and paid-data details while
  preserving typed coverage and failure facts.
- A readiness observation cannot become a durable grant. Existing authority
  scope and protected-effect confirmation remain authoritative.
- Mixed-version readers preserve unknown fields and reject unsupported semantic
  narrowing. Revision mismatch is visible and blocks reuse.
- A connector with expired rights, stale revision or ambiguous execution moves
  to unknown/degraded; it is never silently active.
- Source-family deduplication prevents multiple wrappers or workers from being
  counted as independent evidence.
- A feature-off installation retains the existing planning, delegation and
  evidence paths.

## 8. Migration and rollback

M0 introduces read-only inspection over existing owners. M1 stores candidate
and trial records behind a default-off capability. Existing registry records
remain readable and are not bulk-promoted. A connector becomes active only
through a new exact-revision qualification receipt.

Rollout proceeds Goal by Goal. Before enabling mutations, preflight verifies
the portfolio owner, authority provider, configuration references and public
projection. Rollback disables portfolio injection and retains receipts for
audit; original catalog, configuration, evidence and task owners continue.
No destructive registry migration is part of v0.

## 9. Validation and acceptance

| Claim | Test or evidence | Required result | Boundary / exclusions |
| --- | --- | --- | --- |
| Portfolio does not grant authority | mutation and adversarial fixtures | requested scope expansion rejected; no grant written | does not qualify each external provider |
| Plan binds exact semantics | mutate gap, config, provider, route, budget and graph fields | digest mismatch fails closed | does not prove live execution |
| Replay is idempotent | lost-response and concurrent retry fixtures | one transition and one receipt | provider side effects remain provider-owned |
| Failure preserves useful work | portfolio/provider unavailable fixture | ordinary Todo continues with unknown coverage; hard requirement blocks only that Todo | no availability SLO |
| Connector lifecycle is auditable | discovery→trial→qualification→degrade→retire fixture | every transition has exact revision and typed reason | domain eligibility tested separately |
| Self-discovery is useful | fresh finance and non-finance Agents receive the same Goal only | both select a minimal defensible composition or explain empty selection | two cases do not prove universal uplift |
| Composition improves outcomes | frozen baseline versus portfolio-assisted trials | better first useful action, coverage or decision quality within declared cost; failures retained | no automatic production promotion |
| Three hooks agree | before-plan/delegate/result contract tests | same composition identity and exact route/result lineage | raw model quality excluded |
| Product surfaces agree | CLI, packaged frontend and Lark acceptance | same revision, status, reasons, cost/coverage and failure readback | each transport qualified separately |
| Domain boundaries hold | finance and another domain fixtures | Core remains domain-neutral; domain admission remains independent | no trading authorization |

Measure time to first useful action, evidence coverage, stale/duplicate-source
errors, manual intervention, token/monetary cost, decision changes and accepted
outcomes. Number of installed capabilities, calls or generated words is not a
success metric.

## 10. Operational contract

Operators can inspect the current portfolio revision, active/trial/degraded
adoptions, exact config/provider revisions, recent typed failures, cost,
coverage and next review triggers. Alerts are event-driven for revision drift,
rights expiry, repeated failure, budget exhaustion or a required capability
becoming unavailable; routine successful calls do not create noise.

Capacity is bounded per Goal and Turn. Candidate enumeration is paginated and
prompt projection is size-limited. Failure classes distinguish unavailable,
incompatible, unauthorized, stale, rights-expired, budget-exhausted,
provider-failed and result-unqualified. Backup and recovery follow the selected
Goal authority provider; raw provider artifacts follow their original owners.

## 11. Normative delivery plan

| Milestone | Shipped behavior | Entry gate | Exit evidence | Rollback |
| --- | --- | --- | --- | --- |
| M0 · Contract and inspect | Four schemas and read-only `portfolio inspect/plan` over existing owners | RFC review; catalog/config owners identified | normalization, mutation and feature-off fixtures | remove projection; no stored state |
| M1 · External evidence and connector trial | #4813 lifecycle aligned with connector descriptor/call receipt; no auto-promotion | exact-plan binding and provider boundary accepted | one real host method and one connector trial with partial/failure receipts | keep registry inventory; disable qualification writes |
| M2 · Goal adoption owner | candidate/trial/adopted/degraded/retired reducer and receipts | Goal authority provider available | replay, concurrency, drift, rollback and recovery tests | disable writer; retain receipts read-only |
| M3 · Three-phase composition | portfolio projection at all three Agent-context hooks and generic delegation receipts | M0–M2 identities stable | no-hint fresh-Agent finance/non-finance trials | disable hooks independently |
| M4 · Effect qualification | external-only, connector-only and hybrid trials; use/effect review and retirement proposals | frozen metrics, budget and stop rules | retained denominators show benefit or explicit no-uplift | revert adoption to candidate/degraded |
| M5 · Product journey | CLI, packaged frontend and Lark share inspect, reasons, readback and recovery | shared public projection stable | cross-session, stale, reconnect and repeated-action acceptance | hide mutation controls; CLI readback remains |

Milestones may ship while the RFC remains Draft. #4813 is an M1 prerequisite,
not proof of the whole portfolio. The overall-roadmap owner tracks S8 ordering;
canonical Todos track implementation.

## 12. Open decisions

1. **Portfolio storage profile.** Owner: shared-authority and capability
   maintainers. Recommendation: use the configured Goal authority provider for
   adoption records while keeping large receipts/artifacts with their owners.
   Decide before M2.
2. **Cross-capability comparison.** Owner: capability maintainers.
   Recommendation: compare only within a named Goal gap and report multiple
   dimensions; do not create one global score. Validate in M3/M4.
3. **Automatic degradation threshold.** Owner: capability plus domain owner.
   Recommendation: automatic proposal, explicit typed policy to apply; never
   infer retirement from low call count alone. Decide before M4.
4. **Installation proposal UX.** Owner: product and extension maintainers.
   Recommendation: show governed repair/install proposals only after M3 proves
   selection value. It is outside v0 execution authority.

---

## Appendix A: Execution ledger (non-normative)

### 2026-09-21 — research and contract synthesis

- **Baseline:** `0ef7ebd749ec97a698a8fc7f2a29844dd368689b`; PR #4813 inspected at
  `491c0bf3ccd4804091d7611bd85d73f5f466fdd9`.
- **Delivered:** RFC contract only.
- **Evidence:** repository audit of catalog, connector registry, capability
  admission/memory, Agent-context hooks, Decision Context, Explore, reward
  memory and external-evidence proposal; one finance connector inventory/use
  dogfood informed the lifecycle but is not public qualification evidence.
- **Known gaps:** no canonical portfolio reducer, frontend/Lark projection or
  two-domain effect trial.
- **Effect on normative design:** initial proposal.

## Appendix B: Decision log

| Date | Decision | Owner / approval | Alternatives | Normative sections changed |
| --- | --- | --- | --- | --- |
| 2026-09-21 | Initial proposal; no approval inferred | pending maintainer review | domain-only organization, registry-as-quality-owner, Decision Context owner | all |

## Appendix C: Evidence registry

| Evidence id | Claim | Baseline / environment | Artifact or command | Result | Privacy / validity boundary |
| --- | --- | --- | --- | --- | --- |
| E1 | Three generic hook phases exist | implementation baseline | `agent_context` and subagent-context tests/source | inspected | static inspection, not live uplift |
| E2 | Registry is inventory/telemetry rather than qualification | implementation baseline | connector-registry schema and CLI | inspected | no exhaustive provider audit |
| E3 | External-evidence typed lifecycle is an active prerequisite | PR #4813 exact head above | PR diff, tests and review | open; not on `main` | no merge or live-provider claim |

## Appendix D: Rejected or superseded alternatives

The alternatives in Section 6 remain rejected until evidence shows they can
preserve the invariants with less state and equal product clarity.

## Appendix E: Incident and review lessons

- A capability being installed or a worker route being projected did not prove
  that a real call could execute. Exact authority/readiness readback belongs in
  each composition plan.
- Successful persistence or exact memory readback did not prove that an
  experience changed future behavior. Use and effect qualification remain
  separate.
