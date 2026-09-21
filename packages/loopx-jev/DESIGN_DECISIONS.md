# D1 shadow: design decisions and evidence

[中文](DESIGN_DECISIONS.zh-CN.md) · [Operation guide](DRIFT_SHADOW.md) · [Research RFC](../../docs/architecture/rfcs/optional-semantic-assistance-jev-v0.md)

Current implementation review: [PR #4854](https://github.com/loopx-project/loopx/pull/4854).

**Current proposal:** retain D1 as an explicitly installed, default-off historical
observation tool. Do not enable a drift fuse, automatic replan or pause. The
decision requested by this change is whether to accept this bounded optional
tool, not whether Jev has proved useful enough to control an Agent.

## Implemented functionality and observed effect

The current delivery is a usable **capture → assess → inspect** path, enabled
at an explicitly wrapped refresh call. It does not automatically observe every
native Agent session.

| Implemented functionality | Concrete effect and verification boundary |
| --- | --- |
| `drift init` binds a Goal contract, exact files and an initial checkpoint | Subsequent wrapped refreshes collect actual before/after material without hand-written artifact summaries; scope and contract still need operator selection. |
| `drift refresh` captures around the real core command | Net file/evidence changes are associated with a durable run. Original stdout and exit code are retained; all 10 live-check run records remained unchanged. Collection adds measured overhead. |
| Separate `drift drain` consumer | Jev evaluates Goal relation and evidence increment outside core transactions. All 10 requests in this run returned, but the decorative-work case was not detected. |
| Durable deduplication, request budget and revocation checks | Repeated events are not additional evidence; saved answers can survive a consumer restart without a new request. Offline tests cover duplicates, unresolved sends, changed contracts/configuration and failures; this is not full long-horizon recovery qualification. |
| Local off/shadow settings and environment-only key | Operators can enable, disable and read back the observer. Missing credentials, denied egress and request failure leave the existing Agent workflow in place. No automatic fallback judge or control action is added. |
| `drift status` and phase timings | Operators can inspect judgments, unknowns, failures and capture/assessment time. No raw private source is printed by this status surface; the record supports review, not acceptance certification. |

Validation covers 61 package tests plus 35 related core regressions (96 passing,
no skips), strict source typing and lint, documentation checks, and a built-wheel
CLI journey in an independent environment. **The observation workflow is
implemented; reliable drift detection and reduced wasted work are not proven.**

This is a public-safe decision record, not a transcript or an approval receipt.
[RFC PR #4749](https://github.com/loopx-project/loopx/pull/4749) and
[Discussion #4838](https://github.com/loopx-project/loopx/discussions/4838)
preserve the public discussion. Earlier claims in that discussion are historical;
the limitations below are essential to interpreting the current proposal.

## How the proposal changed

| Question / earlier claim | Challenge or observation | Retained decision |
| --- | --- | --- |
| Can semantics detect busy work that the repeat fuse misses? | An `advanced` self-report or changed fingerprint can evade that specific repeat condition. This does not prove that the entire Agent/review/acceptance system is blind. | Investigate earlier evidence-based observation; retain existing acceptance and control authority. |
| Is Jev a strict superset of the rule? | A few constructed cases, including hand-written artifact descriptions, cannot establish that claim or a production error rate. | Drop the strict-superset claim; collect attributable before/after artifacts and preserve unknowns. |
| Should Jev replace the working Agent's judgment? | An independent read-only Agent can assess the same material too. Role separation, evidence preparation and provider choice are different treatments. | Keep the existing Agent workflow; no fallback judge is implicitly launched by this package. |
| Should every explored direction ship? | Candidate ranking experiments also depended on reducers, contexts and different Agent entrypoints. Their results do not qualify drift detection. | Only D1 ships in this proposal. Other direction code, ranking reducers, selector changes and unrelated workflows are excluded. |
| Is the change just three model questions inside refresh? | Refresh has its own state-write transactions. Network failures must not interrupt those writes; repeated polling must not create repeated drift evidence. | Bounded capture around the command, inference in another process, durable event/request deduplication and historical-only results. |
| Is a delta sufficient evidence? | A new test or probe may be uninterpretable without unchanged surrounding code. | Supply both scoped checkpoints plus the delta. Do not silently truncate required context to fit a request. |
| Does a fast response justify automatic correction? | Later checks still abstained on decorative changes and disagreed on evidence increment. Capture itself also adds latency. | Keep off/shadow. High probability is not a correctness guarantee; no-new-evidence is not itself drift. |

## Current implementation: execution results

The following checks exercised this D1 implementation at source revision
`2f4783bdd`. They used the installed `drift init/refresh/drain/status` entrypoints,
real Git/files, an isolated Goal fixture and real Jev API calls. They are
implementation checks on small constructed tasks, not independent production
qualification or native long-running Agent sessions. Private workspaces, raw
model traffic and credentials are not part of the public record.

Five scenarios were each run twice: implement a retry, rename an unrelated
constant, add a necessary failing test, produce a negative probe result, and
change a call whose external helper implementation is absent. The failing test
and probe actually ran. Expected labels were fixed before requests. The model
was pinned to `jev-1.13.0`, selected-label probability threshold to 0.6 and request
deadline to the default 5 seconds; input included both scoped checkpoints and
the delta. Credentials came from the consumer environment.

| Measurement | Result |
| --- | ---: |
| New requests / parseable responses | 10 / 10 |
| Timeouts / full abstentions | 0 / 0 |
| Cases with matching classifications across both repeats | 5/5 |
| Exact two-label match to fixed expectations | 4/10 |
| Client assessment median | 746 ms |
| Request-to-headers median | 646 ms |
| Synchronous capture overhead median | 334 ms |
| Whole consumer process median | 824 ms |
| Input tokens median | 1217 |

| Scenario (two equal results each) | Goal relation | Evidence increment |
| --- | --- | --- |
| Retry implementation | on_goal | new_evidence |
| Decorative renaming | unknown | new_evidence |
| Necessary failing test | on_goal | new_evidence |
| Negative probe | unknown | new_evidence |
| Missing external helper implementation | on_goal | new_evidence |

**The intended decorative-work drift case was not detected.** Four responses
left Goal relation unknown; all ten selected new evidence. The latter does not
establish verified progress: the increment dimension did not distinguish the
intended counterexamples in this batch. Results do not support automatic
correction. Stable responses and repeated agreement are not correctness proof.

Exact-label match is not production accuracy. Goal relevance is different from
verified acceptance; new code is not necessarily new verification evidence.
The retry implementation's independent passing check was outside the model's
observed packet. Labels need independent agreement before a quality study;
this run does not justify retagging outcomes after seeing the answers.

No automatic retries or local cache replays were counted as new model calls;
all ten original run records remained byte-identical. Timing phases overlap
and must not be summed. Request-to-headers includes network/server waiting,
not server-only inference time. Capture still adds synchronous overhead even
though inference runs separately. Billing, production error rates and Agent
time saved were not established. Earlier design alternatives are recorded
qualitatively above; this table reports only the current implementation run.

## Engineering choices and alternatives

- **Optional package, not a new core capability:** the concrete caller is the
  explicit refresh wrapper and consumer CLI. Core scheduling, Goal, Todo,
  acceptance and L1 reliability-diagnostics contracts are unchanged. L1's
  no-outbound-endpoint receipt cannot certify a Jev request.
- **Environment credentials, separate opt-in:** only `TYPESAFE_API_KEY` supplies
  the live key. Having a key does not select a mode or permit egress. Missing key,
  invalid authentication, timeout, stale input and unknown answers never become
  evidence of healthy progress. The normal Agent workflow continues.
- **Local per-Goal configuration:** this optional CLI has no built-in configuration
  editor. Native host hooks and a registry/frontend/Lark journey would require a
  separate integration proposal. A hand-maintained contract is explicitly an
  operator export, not an assertion of canonical approval.
- **Narrow snapshots:** exact files, bounded material, explicit missing context,
  and single-writer use. No repository-wide completeness, atomic filesystem
  snapshot or author-attribution claim. Equal patches with different context are
  different evidence; unchanged observation material is not another warning.
- **Historical record, not a trigger:** preserve separate relation/increment
  labels, invalid/unknown states and currentness checks. Do not turn `on_goal`
  into acceptance or `no_new_evidence` into a fuse. Invalidated or failed
  observations do not accumulate a consecutive-anomaly count.

## Conditions before intervention

First define Goal relevance, artifact change and new verification evidence
separately. Freeze a held-out multi-round set with independent labels, including
legitimate research, waiting, prerequisites, changed intent and missing evidence.
Compare the existing complete workflow, an independent existing-model judge,
and Jev with matched material. Measure misses, false alarms, abstention, lead
time, review effort and full overhead. Only a separately reviewed intervention
study can establish reduced wasted work or safe replan/pause behavior.

Stopping or retaining the existing workflow is a valid result. The original M0
RFC intake remains discussion intake; no research, provider, spend or control
approval is inferred from that earlier decision. This PR's explicit optional-tool
scope is for maintainers to accept or reject on its own evidence.
