# RFC: Agent Judgment and Optional Independent Assessment — Jev as a Candidate (v0)

- **RFC status:** Draft; document intake and any later study scope await separate maintainer decisions.
- **Delivery maturity:** Proposal; documentation only, no integration or model qualification.
- **Created:** 2026-09-19. **Last normative revision:** 2026-09-20.
- **Implementation baseline:** `9f1916960306b3650d795895b89f331eeae2516e`; source ownership and trigger behavior rechecked at PR revision `27812bd0fb437f831a541b564bcb5be8a96ff77e`. Historical upstream inspection is recorded in Appendix A, not a whole-system certification.
- **Authors / owners:** Proposal author; existing domain maintainers own any direction selected. No new runtime authority or assigned implementation owner.
- **Language mirror:** [中文版](optional-semantic-assistance-jev-v0.zh-CN.md)
- **Related contracts:** [overall roadmap](loopx-overall-roadmap-v0.md), [Decision Context](../../reference/protocols/decision-context-architecture-v0.md), [Goal acceptance](../../reference/goal-acceptance-observations.md), and section 4.

## Document map and maintenance contract

Sections 1–10 propose the research question, comparison method and boundaries; section 11 defines conditional milestones; section 12 lists unresolved decisions. Section 4 records source facts at the named baseline. Appendices preserve history, decisions and evidence. The Chinese document is a semantic mirror; revise both together. D1–D6, I1–I8 and F01–F12 are document identifiers, not new runtime enums or obligations created by publishing this Draft.

For why the proposal changed, read [Appendix E](#appendix-e-discussion-evolution-and-review-lessons); for what has actually been decided, read [Appendix B](#appendix-b-decision-log).

No direction, provider, package, profile version, command or storage design is approved by this document. Accepting a discussion does not authorize an experiment, data egress or production adoption. Recommendations remain pending until the responsible owner records an explicit decision.

## 1. Decision requested

**Which judgments are already handled adequately by the existing Agent workflow, where could a separate bounded assessment help, and would Jev add value over an existing model in that role?** The six scenarios below are unranked candidates for discussing that division of work. Retaining the current workflow, improving evidence alone, using an existing model, postponing evaluation and rejecting Jev are valid outcomes.

The immediate request is whether maintainers want to retain this material as a Draft discussion proposal. The proposed separation is:

| Decision | Requested scope | What it does not approve |
| --- | --- | --- |
| Document intake (M0) | Retain, revise or decline this Draft and its index entry for discussion | No selected study, provider, roadmap priority or spend |
| Study selection (Q1–Q4, before M1) | Select a real problem, finite question, checkpoint, comparator, data and budget, or defer/reject | No production adoption or runtime authority |
| Product adoption (Q5–Q7, before M2) | Decide whether measured value supports a named caller and separately reviewed implementation | No blanket rollout or transfer of existing authority |

This is a proposed scope clarification, not a change to repository governance or a claim that the current request-changes is resolved. Maintainers still decide whether to accept the Draft; if intake is declined or deferred, keep the discussion in PR #4749 without merging these documents and index entry. Explicit acceptance of a discussion Draft would not settle Q1.

The target users are operators reviewing long-running work and developers/reviewers investigating concrete changes. Their potential problem is costly or late recognition that activity does not advance an approved outcome. LoopX already uses executing and reviewing Agents for semantic judgment. Whether a better-defined assessment helps, and whether Jev is the better implementation, are separate questions.

[PR #4749](https://github.com/loopx-project/loopx/pull/4749) is the public proposal and decision-request surface. The [maintainer review](https://github.com/loopx-project/loopx/pull/4749#pullrequestreview-5257146745) requests a verifiable problem and owner decision before provider-specific architecture. This revision separates the document-intake request from later study selection; neither is claimed approved. The [latest maintainer review](https://github.com/loopx-project/loopx/pull/4749#pullrequestreview-5259173141) still requests a scope decision before indexing; the proposed separation above is submitted for that decision, not a unilateral dismissal. [#4447](https://github.com/loopx-project/loopx/issues/4447) and [#4743](https://github.com/loopx-project/loopx/issues/4743) are adjacent vocabulary work, not authorization for Jev, D1 or a new configuration format. Appendix B remains pending.

**No new behavior becomes authoritative.** Necessary workflows retain their existing providers and permissions; they must not require a new Jev account or key. No automatic replan, pause, redirect, Goal mutation, PR approval/merge or settlement is authorized. A later experiment starts only with the selected domain owner, authorized data, a bounded budget and independent evaluation criteria.

## 2. Problem and bounded evidence

An operator may see valid observations, passing tests and repeated claims of progress while the work serves a different outcome. Conversely, characterization tests, negative experiments, research and legitimate waiting may be useful even without a finished feature. A useful assessment must distinguish these situations without rewarding persuasive self-description or punishing necessary prerequisites.

### 2.1 What the repeat trigger establishes

At the named source baseline, [typed_progress_repeat_trigger](../../../loopx/control_plane/work_items/progress_observation.py) requires enough consecutive eligible observations, deduplicates attributable Turns, compares equal fingerprints, and only triggers for `unchanged` or `blocked`. Fingerprints include supplied semantic identity and evidence fields; `hypothesis_id` is one such field.

| Illustrative case | Consequence for this trigger | What remains unknown |
| --- | --- | --- |
| Repeated equivalent `unchanged`/`blocked` observations | Can trigger once the eligible sequence reaches its threshold | Whether repetition is operationally justified |
| Work reports `advanced` while not advancing the approved outcome | Does not satisfy this trigger, even with an unchanged fingerprint | Whether the full workflow notices; whether any model can judge it from available evidence |
| Equivalent work changes a fingerprint-bearing ID | Breaks equality for the affected window | Whether it is genuinely the same work or an authorized change |
| Useful progress or prerequisite work | Absence of a repeat trigger is possible | Absence of a trigger does not certify progress |

These are source-derived boundary cases, not new live-model measurements. The function is an exact-repeat detector, not a semantic completion verifier. Its boundary supports a research question; it does not establish that the entire LoopX/Agent/reviewer workflow is blind. Searching a few source keywords cannot establish that broader absence.

### 2.2 Why Jev remains a candidate

Jev offers bounded typed questions and probability distributions that may fit a small assessment task. These interface properties justify comparison, not adoption: existing models can also perform structured, read-only assessment. No accuracy, cost advantage, strict-superset claim or production token budget is established here. Synthetic examples may test question design; a handwritten description labeled `observed_artifacts` is not host-read evidence.

### Invariants

- **I1 — Existing authority remains.** Optional advice cannot grant work, clear a hold, replace required review or veto a deterministic protection.
- **I2 — Off means no new effects.** No new credential lookup, client, network, file or worker hook; ordinary success and refusal behavior remain unchanged.
- **I3 — Compare the actual baseline.** Include existing Agents, reviewers, tools and rules; do not invent a local fallback or strip the baseline of its normal investigation ability.
- **I4 — Unknown stays visible.** Not evaluated, failed, abstained, uncertain and stale are different; none means normal progress or approval.
- **I5 — Evidence, inference and action differ.** A typed model answer records a judgment, not proof of delivery, source truth or authorization.
- **I6 — Read and send are separate permissions.** Credentials, installation and private-process execution do not authorize uploading private data.
- **I7 — Keep the existing owner.** One bounded question has one responsible domain; no second planner, evaluator policy, registry or installer.
- **I8 — Bound cost and preserve exit.** No silent retries/provider switching. Lack of benefit permits stopping; missing live evidence never becomes a passed qualification.

## 3. Six candidate scenarios without a preset ranking

Choose any future study by an evidenced user need, existing ownership, available context, evidence readiness, error cost, maintenance and removability. D1–D6 are stable discussion identifiers, not priorities, an implementation sequence or a claim that each scenario needs another model. No direction is preferred before a concrete case supports it.

| Scenario | Target user | Existing judgment and baseline | Primary value hypothesis | Readiness and rejection condition |
| --- | --- | --- | --- | --- |
| **D1 — Progress and goal deviation** | long-running-work operator | Executing Agent, operator, enabled reviewer, progress/frontier/writeback and acceptance paths | Earlier detection of work needing goal-alignment review | Needs approved goal, attributable artifacts, bounded history and independent labels; reject if it merely repeats existing review or misclassifies useful prerequisites |
| **D2 — New concepts and owner reuse** | developer | Development Agent, owner search, semantic review and shipped inventory | Less time finding a suitable existing owner | Needs candidates and contract meanings; the #4743 local probe is not assumed shipped; reject false equivalence based on matching literal sets |
| **D3 — Delivery claims against evidence** | PR reviewer | Exact-head reviewer with actual investigation and validation | Detect a named claim/evidence mismatch earlier | Needs a specific under-served subtask; reject a second whole-PR score with no added value |
| **D4 — Material/evidence reranking** | operator or evidence consumer | Actual retrieval candidates, ordering, Agent selection and mandatory reads | Less reading to find useful evidence | Needs relevance judgments and coverage accounting; reject hidden required sources or missing candidates |
| **D5 — Skill/capability suggestions** | task operator | Host discovery, existing catalog and Agent/user selection | Fewer missed or irrelevant capability selections | Needs real task/catalog cases; reject suggestions that duplicate discovery or imply installation authority |
| **D6 — Replan candidate comparison** | planner/manager | Existing planner, legal alternatives, attributable history and constraints | Better identification of redundant exploration | Needs meaningful alternatives and prior outcomes; reject a competing planner or suppression of legitimate exploration |

Each selected experiment chooses one primary hypothesis: added detection, earlier detection, reduced judgment cost or reduced reading. Other metrics are guardrails, not simultaneous promised benefits. D3 does not require D1/D2 and D5 does not require D4 unless a real dependency is demonstrated.

D1 is the worked research example because section 2 identifies a concrete detector boundary. Its proposed question is whether a bounded assessment, at a useful checkpoint, improves recognition of goal deviation relative to the full existing workflow. This example is not a ranking or approval to study or implement D1. The other directions remain candidates, not five future delivery commitments.

## 4. Existing system and ownership

| Concern | Existing source or contract | Reusable boundary / remaining question |
| --- | --- | --- |
| D1 evidence | [Decision Context runtime](../../../loopx/capabilities/decision_context/runtime.py), [sources](../../../loopx/capabilities/decision_context/sources.py), [profile](../../../loopx/capabilities/decision_context/profile.py) | Scoped acquisition, exact reads and evidence assembly exist. The caller owns reasoning; `context_provider` retrieves context rather than performing inference. Existing mechanisms do not by themselves prove a continuous independent progress assessor. |
| Goal basis / progress | [acceptance authority](../../../loopx/control_plane/goals/acceptance_authority.ts), [acceptance contract](../../../loopx/control_plane/goals/acceptance_contract.ts), [progress observation](../../../loopx/control_plane/work_items/progress_observation.py), [Direction Baseline](goal-direction-baseline-v0.md), [Alignment](shared-goal-alignment-and-governed-amendment-v0.md) | Reuse an already effective approved basis; do not promote a provider or infer Goal intent to start an experiment. Existing progress/settlement owners remain authoritative; proposed direction contracts are not shipped dependencies. |
| D2 authoring | [Semantic Vocabulary RFC](semantic-vocabulary-convergence-v0.md), [inventory script](../../../scripts/generate_semantic_inventory.py), [inventory](../../../loopx/semantics/inventory.py) | Full-tree inventory exists; the bounded diff/no-npm probe in #4743 remains separate work at this baseline. Advice cannot replace discovery, register terms or suppress unresolved candidates. |
| D3 review | [review contract](../../../loopx/capabilities/pr_review_queue/review_contract.py), [result check](../../../loopx/capabilities/pr_review_queue/result_check.py), [Intelligent Review RFC](intelligent-review-presentation-surfaces-v0.md) | `pr_review_queue` owns exact-head evidence review. Result checking verifies declared consistency, not truth. Presentation is a consumer, not an alternative reviewer. |
| D4 retrieval | [Decision Context](../../../loopx/capabilities/decision_context/README.md), [Reward Memory](../../../loopx/capabilities/reward_memory/README.md), [memory utility RFC](post-outcome-memory-utility-attribution-v0.md) | Preserve each caller's provenance, freshness and full candidate set. Relevance is not verified truth or outcome utility; no combined registry is proposed. |
| D5 skills | [Project Skill Delivery](../../../loopx/capabilities/project_skill_delivery/README.md), [extensions](../../reference/extensions.md) | Discovery, install, activation and domain permission remain separate. |
| D6 planning / automation | [Explore](../../../loopx/capabilities/explore/README.md), [Manager Handoff](capable-manager-semantic-handoff-v0.md), [post-writeback hooks](provider-neutral-post-writeback-capability-hooks-v0.md), [Effect Interpreter](agent-loop-effect-interpreter-v0.md), [TS migration](typescript-control-plane-migration-v0.md) | Keep planner/effect authority in the existing typed owner. No network in pure reducers or primary writeback transactions; no automatic hook selected. |

Placement is deliberately conditional: D1 would first investigate `decision_context`, D2 semantic developer tooling, D3 `pr_review_queue`, and D4–D6 their actual callers. No capability ID, provider ID, built-in addition or extension package is introduced. Existing owner sufficiency and the [extension placement rules](../../reference/extensions.md) must be reviewed for a real adopted caller, before code placement is chosen. The overall roadmap remains authoritative; this proposal does not reorder it.

## 5. Proposed bounded comparison

### 5.1 One decision brief before an experiment

Reuse the selected issue/PR's decision fields; do not create a new registry. Record the operator and current difficulty, existing judge, one finite question, invocation point, evidence window, primary hypothesis, independent evaluator, permitted data/destination, budget and stop condition. If these cannot be specified, keep the candidate pending. No new product CLI, profile migration or durable attempt store is a prerequisite for a fixed-evidence study.

For a possible D1 study, compare an operator-requested review of one completed-work window at a named checkpoint. Whether that checkpoint occurs early enough to help must be measured; it is not a per-Turn supervisor. Use only evidence available at that time, without hindsight from the final outcome. The owner still chooses or rejects this setup.

### 5.2 Evidence and question design

Bind the approved goal/acceptance revision, attributable work identity, host-read artifacts or diff, validation readback and the earlier evidence needed for comparison. Record missing, conflicting and omitted material. Exact reading proves provenance, not semantic correctness. Missing goal authority stops evaluation; do not infer intent from filenames or self-reports.

For D1, study goal relationship and evidence increment separately. Preserve necessary prerequisites, legitimate blocked waiting and insufficient evidence without forcing them into drift. These need not be a single mutually exclusive enum: waiting describes work state, while alignment describes a relation. Missing prior evidence requires an unknown novelty result. New unrelated work may have increment while remaining off goal.

Use artifact-based input as the primary comparison. Keep author claims separate and evaluate absent/neutral/praising/critical self-description as an ablation on the same artifacts. Measure classification and probability shifts; do not assert that labeling claims untrusted eliminates influence, or that removing all explanations is universally best. Any context needed to explain a prerequisite must have attributable support. Source text remains untrusted even after author summaries are removed.

### 5.3 Provider facts and deferred mechanisms

The [TypeSafe API](https://docs.typesafe.ai/api) accepts state, keyed typed questions and a requested model, returning keyed answers and an actual model. [Confidence](https://docs.typesafe.ai/confidence) is derived from the Choice/Score probability distribution; Noul has no separate confidence field. Raw probabilities do not cure biased evidence, and neither value is measured engineering correctness or authority. Retain provider-specific semantics rather than inventing equivalent confidence for other models.

A trial must pin its requested model, record the actual model and question version, and disclose mismatches. Official interface/model documentation is not live qualification, a retention agreement or measured value on English/Chinese workloads. The documented [model limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13) motivate tests for indirection, irrelevant context and adversarial content.

Package placement, final CLI/API, profile version, persistence, request lifecycle and accounting are deferred until an adopted caller justifies them. Existing strict profile v0 cannot simply accept invented fields; a later configuration decision must preserve restrictions and old-reader behavior. This Draft selects no replacement schema.

## 6. Alternatives and adoption logic

| Arm | Treatment | Question answered |
| --- | --- | --- |
| **A — Existing complete workflow** | Actual Agents, enabled reviewers, tools and deterministic checks | What quality, timing and total effort exist today? |
| **B — Bounded assessment with an existing approved model** | Fixed evidence scope, finite questions and read-only role | Does improved evidence/assessment organization help? |
| **C — The same assessment with Jev** | Same evidence scope, semantic questions and independent rubric as B | Does the provider add value beyond that organization? |

Fixed-snapshot comparisons control B/C evidence and question meaning, not identical API bytes. Full-workflow comparisons preserve A's normal ability to investigate and run checks. Record differences in prompts, tools, evidence preparation, human attention and calls; A/B/C alone is not a causal guarantee.

The executing Agent may benefit from wider history, tool use and task context; a separate assessment may offer a fresh perspective but lose context or repeat the same error. Neither advantage is established by role or model name. "Independent" here means a separate assessment role, not proven statistical independence or greater intelligence.

| Question shape | Candidate division of work | Evidence needed before changing the workflow |
| --- | --- | --- |
| Needs investigation, unstated dependencies or reconstruction of intent | Keep investigation with the existing Agent/reviewer and its tools | Does a bounded evaluator miss decisive context or mislabel useful prerequisites? |
| Can be stated as a finite question over attributable artifacts and an explicit criterion | Compare an existing-model assessment (B) and Jev (C) as optional second opinions | Better error/coverage or total cost at the same rubric, without degrading the complete workflow (A) |
| Evidence is missing or contradictory | Obtain evidence through the existing owner, or preserve unknown | More model votes cannot replace missing facts; record what would resolve the uncertainty |
| Determines permission, acceptance, plan execution or settlement | Preserve the existing authorized decision owner | No model score or agreement grants authority |

Use the same snapshots for B/C and report the context omitted relative to A. Separately measure A with its normal context and investigation, rather than handicapping the Agent to fit a bounded API. Compare judgment quality, false alerts/misses, abstention and coverage, context needs, time and full cost; claim no winner from confidence values alone. If an advantage disappears when missing context is restored or evidence is organized, attribute it to that change rather than to Jev.

Initially measure supplementary observation without changing control decisions. Local replacement of a bounded model subtask and triage/reranking are alternative later treatments. Triage must sample unflagged cases to estimate misses; it cannot skip mandatory review. Simply adding Jev while preserving every existing review adds cost unless additional benefit is demonstrated.

- If B improves on A and C adds no worthwhile benefit over B, retain the process improvement and existing model.
- If C improves on B but the complete treatment is worse than A on the predefined objective/guardrails, do not adopt on that local advantage alone.
- If C offers incremental value within error, privacy, delay, cost and maintenance limits, propose a named product pilot; value alone grants no action authority.
- If evidence is insufficient, data cannot be authorized, or the workflow already meets the need, postpone or stop. Doing nothing is a real alternative.

## 7. Safety, privacy and graceful degradation

These are constraints for any later admitted experiment or integration, not claims of delivered behavior. Preserve existing default-off and zero-egress collection boundaries. A private process using BYOK still sends selected data to a remote service; read access is not upload permission. Minimize inputs, restrict destination/audience/retention, redact secrets, and keep raw traces and private evidence out of public artifacts. Hashing is not anonymization.

| Condition | Required boundary |
| --- | --- |
| Disabled, missing key, denied egress or exhausted budget | No new send; original workflow continues with its original holds; explicit requested assessment says not evaluated |
| Missing/wrong goal, identity or necessary evidence | Do not invent facts; report unavailable basis or insufficient evidence as appropriate |
| Timeout, rate limit, invalid/missing answers or provider failure | Visible bounded failure; no automatic retry, silent alternate provider or clean judgment |
| Low certainty or abstention | Distinguish completed-but-unused advice from transport failure; never interpret it as no drift |
| Goal/evidence revision changes or late response | Not usable as a current judgment; preserve historical provenance if retention permits |
| Optimistic model answer despite existing refusal | Original identity, permission, acceptance, review and settlement obligations remain effective |

The model receives no tools or authority to follow references, install skills or execute commands. Required-source coverage and D4 candidate identity must survive ranking failures. D5 suggestions grant no activation; D6 comparisons grant no plan commit. Reversible intervention can still be costly and requires a separately approved action contract.

## 8. Compatibility, removal and replay

This PR makes no runtime/configuration migration. If a product pilot is selected, its owner must prove ordinary entrypoint behavior with the feature disabled and after uninstall, legacy/mixed-version handling, and explicit opt-in through the existing configuration owner. Disabling stops unsent work and use of in-flight advice; it cannot undo transmitted bytes or fees. Do not alter original Goal, receipt, lease or cursor state to clean up assessment records.

If persistence or cross-process deduplication is introduced, define its retention horizon and replay behavior before adoption. Validate **send → record expiry/deletion → same-ID replay**, including concurrent/restarted callers and ambiguous dispatch. Expired history must not silently turn a replay into a newly authorized billable call. Rejection, a bounded tombstone or an explicit fresh-request policy are alternatives to decide with the actual design. Unknown dispatch/cost cannot be recorded as proven zero. No storage mechanism is selected here.

## 9. Validation and acceptance

### 9.1 Current documentation and decision readiness

| Claim | Evidence / required result | Boundary |
| --- | --- | --- |
| Reviewable comparison proposal | Matching English/Chinese scope, six candidates, actual baseline, A/B/C, alternatives and stop rules; valid references | Document completeness does not approve the research topic or certify model value |
| Document intake request | Section 1 asks maintainers to retain/revise/decline a Draft; Appendix B records the actual response, or pending | Complete request materials do not mean intake is accepted; intake alone would not select or authorize an M1 study |
| Source-bounded motivation | Section 2 is traceable to the named trigger and section 4 distinguishes other owners | No whole-system blindness or strict-superset claim |

Documentation checks:

```bash
uv run --extra test python examples/docs-governance-smoke.py
uv run --extra test python examples/docs-asset-integrity-smoke.py
git diff --check
```

### 9.2 Experiment quality, only after scope approval

Freeze one hypothesis, checkpoint/window, independent rubric, authorized cases, budget, numeric adoption/stop thresholds and held-out task families before collecting answers. Use independent adjudication; keep genuinely disputed cases unresolved rather than treating executor or Jev answers as truth. Measure false alerts, misses, abstention/coverage, detection timing, language strata, latency, evidence preparation, human rework, calls and total cost with denominators. Report uncertainty; a few correct examples do not establish safety or superiority.

For D1 include actual useful progress, necessary tests/research, negative experiments, legitimate waits, changed IDs, authorized goal changes, missing history, same-Turn retries, opposing self-claims and injected instructions. Handwritten or injected responses test examples/contracts only. Record requested/actual model and versioned evidence; do not publish private inputs or use output from a moving alias as a pinned qualification. Missing credentials mean live evidence is unverified, not passed. Model comparison and any eventual intervention benefit need separate evidence.

### 9.3 Conditional product obligations

F01–F12 remain future implementation acceptance categories. They are not present test results or requirements to implement M2 before this Draft can be discussed. The selected caller determines applicability and records justified exclusions.

| ID | Case | Required result before the applicable product pilot is accepted |
| --- | --- | --- |
| F01 | Ordinary entry, feature off | No new credential/client/network/file effects; baseline success/refusal parity |
| F02 | Explicit assessment without key | Useful original path plus not-evaluated result, zero sends, no fabricated probability |
| F03 | Key present but disabled or egress denied | No upload, borrowed key or silent alternate |
| F04 | Existing hold plus missing/optimistic model | Hold and mandatory review preserved |
| F05 | Provider errors and ambiguous send | Bounded observable failures; unknown dispatch/cost remains unknown |
| F06 | Abstention or incomplete ranking | Uncertainty distinct from failure; no lost candidates or invented zero scores |
| F07 | Wrong scope, stale basis or late response | No cross-identity use or relabeling as current |
| F08 | Offline CI vs live comparison | Offline contracts execute; missing live evidence remains skipped/unverified |
| F09 | Direction-specific baseline unavailable | Explicit prerequisite/missing coverage; no fictitious local probe or skill |
| F10 | Concurrency, restart, replay and retention expiry | No unauthorized duplicate billable attempt; prove the selected replay horizon/policy |
| F11 | Install/configuration/uninstall | Optional dependencies, compatible readers and restored original behavior |
| F12 | Injection, self-claims and required coverage | No new authority or suppressed obligations; report model errors separately from hard boundaries |

Future implementation validation must exercise the real selected entrypoint and affected backend, not only a decoder or mock. Use isolated fixtures; never mutate active Goal state to manufacture evidence. Model-quality results cannot substitute for those conformance checks.

## 10. Operator experience and full cost

No user entrypoint changes in this proposal. A later observation study should identify the claim needing review, relevant evidence, missing basis and disagreement without repeatedly demanding keys or creating automatic Todos. Reading results must not call inference. A disagreement should prompt checking missing evidence before adding more model votes.

Choose supplementary observation, bounded replacement or prioritization explicitly; measure what work is added or removed. Count evidence acquisition, model latency, false-alarm review, question maintenance, outages and egress administration alongside API usage. After an outage, a next authorized request may evaluate current evidence; do not replay history automatically. A model's score must not become the worker's delivery target.

## 11. Conditional delivery plan

M0 concerns the discussion document and its intake decision; Q1–Q4 concern admission to M1, and Q5–Q7 concern any later product adoption. These decisions are recorded separately. The proposed M0 exit below is subject to maintainer agreement, not a claim that prior requests have been satisfied. Later milestones are conditional, not a promise to study or build all scenarios; historical entries remain historical.

| Stage | Deliverable | Entry / exit decision | Exit or rollback |
| --- | --- | --- | --- |
| M0 | Bilingual discussion of Agent/assessment roles, six unranked scenarios and comparison criteria | Reviewable material → maintainer explicitly retains, requests revision to, defers or declines the discussion Draft | Record intake outcome; Q1 remains separate. If declined/deferred, keep discussion in the PR without merging the documents/index |
| M1 | One authorized A/B/C comparison, or a documented inability to evaluate | Q1–Q4 explicitly resolved for the selected study: caller, checkpoint, inputs, rubric, permission and budget → evidence supports adoption or stopping | Stop calls; retain/delete study evidence by policy; no production commitment |
| M2 | One conditional product pilot under the existing owner | Supported value and owner adoption decision → real entrypoint, applicable F01–F12, compatibility and operator acceptance | Disable/remove optional path; preserve original authority |
| M3 | A second independently justified caller | Real need and qualification → demonstrated reusable mechanism | Extract only proven duplication; do not manufacture a second caller |
| M4 | Reprioritize remaining directions or stop | Observed value/cost and owner decisions | Existing models, postponement and no adoption remain valid |

No default D1 implementation, automatic worker adoption or hidden mandatory-model phase follows from M0. Adjacent issue closure conditions remain independent.

## 12. Open decisions

| ID | Decision / options | Recommendation and evidence needed | Owner / dependent stage |
| --- | --- | --- | --- |
| Q1 | Is this research topic worth pursuing; which direction or none? | No preset ranking; select only from an evidenced problem, current Agent coverage, context needs and comparison feasibility | Product and domain maintainer; before M1 |
| Q2 | Which finite question, checkpoint and observation window? | One primary hypothesis; D1 relationship/increment with waiting and missing history represented honestly | Selected caller and evaluation owner; before M1 |
| Q3 | Existing-model comparator and independent rubric | A/B/C with fair inputs; freeze thresholds, error costs, language strata and adjudication before results | Evaluation owner; before M1 |
| Q4 | Authorized data, destination, model and spend | Minimum necessary input, pinned/actual model, bounded calls and retention; reject if infeasible | Data/operations owner; before live comparison |
| Q5 | Observation, replacement, triage or no adoption? | Adopt only demonstrated full-workflow value; triage includes unflagged sampling | Product/domain owner; before M2 |
| Q6 | Placement, configuration, replay/storage and user entrypoint | Reuse nearest owner; decide mechanisms for the real caller, including expiry/replay and downgrade | Capability/configuration maintainers; before M2 implementation |
| Q7 | Any influence on execution or required gates? | None authorized; needs a separate named action, authority, error-cost and recovery decision | Existing authority owner; before any such influence |

## Appendix A: Execution ledger (non-normative)

### 2026-09-19 — Initial source-aligned proposal

- **Baseline:** `9f1916960306b3650d795895b89f331eeae2516e`; targeted upstream delta through `cc8e28d8b58a9b15e928d7e2cee16097172567d1`.
- **Delivered:** Bilingual design, six-direction owner map, recommended D1 CLI slice and failure/rollback/validation contracts.
- **Evidence boundary:** Source and official interface documentation reads; this entry does not attest a runtime test or model trial.
- **Known gaps:** M1 implementation, live conformance, value evaluation and UI/worker adoption remain unshipped by this proposal.
- **Normative effect:** Initial sections 1–12 proposed for review; no acceptance inferred.

### 2026-09-20 — Research scope correction

- **Baseline:** Prior proposal `27812bd0fb437f831a541b564bcb5be8a96ff77e` and its linked maintainer review.
- **Delivered:** Revised decision request, bounded detector motivation, full-workflow/existing-model/Jev comparison and conditional milestones; removed preselected package/profile/attempt design.
- **Evidence boundary:** Document revision and source inspection only; no new runtime, API or quality experiment.
- **Known gaps:** Owner acceptance of the research question, representative evidence and comparative value remain pending. The earlier author's approval does not approve this revision.
- **Normative effect:** Sections 1–12 now request comparison before adoption; original milestone meanings are superseded, not retrospectively completed.

### 2026-09-20 — Separate document intake from study selection

- **Baseline:** Reviewed PR head `21e5d18a635aa009a0719369c4ecc2709f3c4d69`.
- **Delivered:** Reframed the question around Agent/assessment roles, removed candidate priority rankings, added context-sensitive comparison criteria, and proposed separate M0 intake, M1 study and M2 adoption decisions.
- **Boundary:** Documentation revision only. Intake, study selection and adoption remain unapproved; no experiment or runtime change.

## Appendix B: Decision log

| Date | Proposal / decision | Owner / approval state | Alternatives | Sections |
| --- | --- | --- | --- | --- |
| 2026-09-19 | D1 CLI, optional Jev package and profile v1 recommended | Not approved; superseded as the default recommendation by this revision | D2 or separate configuration | 3, 5, 11, 12 |
| 2026-09-20 | Request direction selection and one bounded A/B/C study, if warranted | Product/domain maintainers; **pending**. Linked maintainer review requests changes, not approval | Existing-model/evidence improvement, another direction, defer or reject | 1–12 |
| 2026-09-20 | Propose separating Draft intake from study selection; remove scenario rankings | Maintainer intake response **pending**; no Q1–Q7 approval inferred. [Latest review](https://github.com/loopx-project/loopx/pull/4749#pullrequestreview-5259173141) remains request-changes | Retain/revise discussion Draft, or defer/decline intake and keep discussion in this PR | 1, 3, 6, 9, 11, 12 |

Record any future accepting decision with its actual public link and exact scope. Neither silence, author assertions, successful checks nor RFC publication substitutes for it.

## Appendix C: Evidence registry

| ID | Evidence | Supports / does not support |
| --- | --- | --- |
| E1 | Source paths in section 4 at the named baseline | Owner/trigger boundaries; not whole-system blindness or runtime qualification |
| E2 | Historical targeted upstream inspection in Appendix A | Bounded source alignment; not an exhaustive latest-main certification |
| E3 | TypeSafe API/confidence/model-limitations pages linked in section 5.3 | Interface and documented limitations; not independent model quality, data terms or a live trial |
| E4 | PR #4749 and its linked maintainer review | Public request and request-changes rationale; no accepted research/adoption decision |
| E5 | A/B/C and F01–F12 | Proposed experiments/obligations; unexecuted for this feature |

## Appendix D: Deferred mechanisms and rejected shortcuts

The earlier D1 CLI/profile v1/optional-package/private-attempt proposal remains in Git history as an unselected alternative. Reopen only after a real caller and comparative value justify it; do not maintain a second full specification. Reject confidence-to-action shortcuts, probability-shaped rules, model output as a verifier receipt, whole-system claims inferred from one detector, and a generic six-scenario framework without callers.

## Appendix E: Discussion evolution and review lessons

This is a public-safe synthesis of the reasoning, not a transcript, a new experiment report or an approval record. It preserves both the useful initial motivation and the arguments that narrowed the proposal. Source-derived facts are identified in section 2; reported example behavior is a hypothesis generator until independently qualified. Private conversation links, numerical probe outputs and credentials are not required to understand or validate the decisions below.

| Discussion step | Initial proposition / question | Challenge or evidence boundary | Retained conclusion and RFC consequence |
| --- | --- | --- | --- |
| 1. Identify the missing signal | An Agent can keep reporting `advanced` or change an identity while repeating work; can semantics detect what the repeat trigger misses? | The source confirms this trigger boundary, but neither its return value nor a few examples describes the complete Agent/reviewer workflow. | Keep D1's operator problem and the four illustrative cases in section 2. Remove claims of whole-system blindness and Jev being a strict superset. |
| 2. Ask what the evaluator actually sees | Separate an approved goal, observed artifacts and author self-report to obtain an independent judgment. | Handwritten artifact descriptions are still assertions. Novelty cannot be established without prior evidence. A different model can inherit the same incomplete account. | Section 5.2 requires attributable artifact reads, goal revision and comparison history; missing history yields unknown. Synthetic examples cannot stand in for this input path. |
| 3. Examine sensitivity and question coverage | Removing self-report or adding prerequisite/waiting answers might improve the assessment. | Labeling claims untrusted does not establish immunity; deleting explanations may remove relevant context. A missing option can force a wrong category, and waiting and alignment describe different dimensions. | Compare absent/neutral/praising/critical claims on fixed artifacts. Preserve supported prerequisite context, waiting and insufficient evidence without freezing a global enum. Measure errors rather than claim the prompt fixes them. |
| 4. Separate observation from intervention | Typed answers and high confidence might permit redirect or replan. | Interface validity is not factual correctness. Raw probabilities and confidence can both move with input framing; reversible actions still have costs. | Retain observation as the initial study treatment. Sections 7–8 and Q7 preserve current authority, failure boundaries and a separate decision before any action influence. |
| 5. Compare with the models already present | Does Jev add a capability, or duplicate executing/reviewing Agents? | Evidence preparation, role separation and provider replacement can each cause apparent improvement. API success alone cannot distinguish them. | Section 6 adds A/B/C, full-workflow cost and legitimate no-adoption outcomes. D1 remains a worked hypothesis; the earlier provisional rankings are removed, leaving six unranked scenarios. |
| 6. Reconcile the proposal with maintainer review | The original draft made a detailed D1 CLI/package/profile/attempt proposal. | The [maintainer review](https://github.com/loopx-project/loopx/pull/4749#pullrequestreview-5257146745) found no accepted owner decision supporting that investment; the [author self-review](https://github.com/loopx-project/loopx/pull/4749#pullrequestreview-5256367074) had assessed internal completeness, which does not establish demand. | Sections 1, 11 and 12 now request a research-scope decision. Mechanisms are deferred in Appendix D. Appendix B records owner acceptance as pending; this correction does not dismiss the request-changes. |
| 7. Separate intake from investment | Does keeping a Draft imply that its research or provider is selected? | The [latest review](https://github.com/loopx-project/loopx/pull/4749#pullrequestreview-5259173141) requests a scope decision before indexing. Document readiness cannot supply it, but the requested intake scope must also be distinguished from experiment approval. | Sections 1/9/11 propose an explicit discussion-only intake decision; Q1–Q4 still precede M1 and Q5–Q7 precede adoption. Section 3 removes priorities; section 6 compares context needs and judgment quality without assuming either evaluator is smarter. No approval or review dismissal is inferred. |

**Still open:** whether maintainers will retain this discussion Draft (M0), whether the problem deserves a bounded study (Q1), which checkpoint and finite question are useful (Q2), whether Jev adds value over an existing model (Q3/Q5), and whether the necessary data and budget are available (Q4). Recording this discussion does not settle those questions.

When discussion continues, update the affected normative section for a changed recommendation, add a compact rationale here only when a material argument changes, and record an actual owner decision with its public link in Appendix B. Experiment evidence belongs in Appendix C with its validity boundary; implementation progress belongs in Appendix A. Do not duplicate the whole conversation or silently rewrite rejected recommendations as prior approvals.

The engineering reduction criterion remains: identify the work replaced or the missing checkpoint served, and count added maintenance. Better evidence and fewer repeated judgments can be a useful outcome even if Jev is never adopted.
