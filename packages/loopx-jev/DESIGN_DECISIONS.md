# D1 shadow: design decisions and evidence

[中文](DESIGN_DECISIONS.zh-CN.md) · [Operation guide](DRIFT_SHADOW.md) · [Research RFC](../../docs/architecture/rfcs/optional-semantic-assistance-jev-v0.md)

**Current proposal:** retain D1 as an explicitly installed, default-off historical
observation tool. Do not enable a drift fuse, automatic replan or pause. The
decision requested by this change is whether to accept this bounded optional
tool, not whether Jev has proved useful enough to control an Agent.

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
| Should every explored direction ship? | Candidate ranking experiments also depended on reducers, contexts and different Agent entrypoints. Their results do not qualify drift detection. | Only D1 ships in this proposal. Other direction code, ranking reducers, selector changes and fork-only workflows are excluded. |
| Is the change just three model questions inside refresh? | Refresh has its own state-write transactions. Network failures must not interrupt those writes; repeated polling must not create repeated drift evidence. | Bounded capture around the command, inference in another process, durable event/request deduplication and historical-only results. |
| Is a delta sufficient evidence? | A new test or probe may be uninterpretable without unchanged surrounding code. | Supply both scoped checkpoints plus the delta. Do not silently truncate required context to fit a request. |
| Does a fast response justify automatic correction? | Later checks still abstained on decorative changes and disagreed on evidence increment. Capture itself also adds latency. | Keep off/shadow. High probability is not a correctness guarantee; no-new-evidence is not itself drift. |

## What the exploratory measurements established

These are **author-run fork observations at `9153f5841`**, summarized to explain
the design. They are not independent validation of this upstream port, and raw
private workspaces, model traffic and credential material are not published here.
The port uses a D1-only schema and must pass its own exact-head checks.

The scenarios were five small constructed tasks: implement a retry, rename an
unrelated constant, add a necessary failing test, produce a negative probe result,
and change a call whose external helper implementation is absent. Git, refresh
CLI, provider requests, the failing test and probe were actually executed. These
were not native long-running Agent sessions. Labels were fixed before each batch;
the model and selected-label threshold of 0.6 were held fixed.

| Batch | Requests / parseable responses | Timeouts | Exact two-label match | Assessment median |
| --- | ---: | ---: | ---: | ---: |
| Delta only; 5s; two repeats per case | 10 / 6 | 4 | 0/10 | 4258 ms including timeouts |
| Delta only; 15s; one per case | 5 / 5 | 0 | 0/5 | 803 ms |
| Scoped context + delta; 15s; one per case | 5 / 5 | 0 | 1/5 | 763 ms |
| Scoped context + delta; default 5s; two per case | 10 / 10 | 0 | 2/10 | 856 ms |

The last batch returned 8 partially or fully decided assessments and 2 full
abstentions. Both repeats agreed for each case. The necessary failing test was
identified as on-goal/new evidence; decorative renaming remained unknown/unknown.
The negative probe added evidence but its Goal relation remained unknown. The
retry implementation was on-goal/no-new-evidence, and the missing helper was
on-goal/unknown. **The key intended drift case was not detected.**

Exact-label match is not production accuracy. The relation question asks about
Goal relevance, not verified acceptance. New code is not necessarily new
verification evidence, and the implementation case's independent passing check
was outside the model's observed packet. These distinctions need independently
agreed labels before another quality study. Repeated agreement is repeatability,
not correctness. The 15s batch completed within 5s anyway, so its lack of timeouts
cannot be attributed to the longer deadline; network/server variation remains a
possible explanation. No automatic retries or local cache replays were counted
as additional model calls.

In the final repeated batch, synchronous capture overhead had a 406 ms median,
request-to-headers 729 ms, and the whole consumer process 1049 ms. Those phases
overlap; do not sum them. They are client measurements, not server-only inference
time or Agent time saved. Input tokens had a median of 1247. Timeout usage and
total billing were not established. Original run records remained unchanged.

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
