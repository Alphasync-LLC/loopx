# Progress-Review Sentinel

[中文](README.zh-CN.md)

The progress-review sentinel lets a Goal consume **typed drift receipts** that
an optional, external, bounded reviewer writes after each captured work
transition. It is default-off. In `shadow` the core only records and displays
receipts. In `assist` a run of consecutive completed drift receipts becomes the
**existing** `autonomous_replan_obligation`; nothing else changes.

It exists because the typed repeat fuse is blind by construction to one
pattern: an Agent that keeps declaring `advanced`, keeps changing its
`hypothesis_id`, and keeps the tests green while its scoped file delta only
renames identifiers or reorders fields. That work is caught today only by the
periodic review after 20 durable runs.

## What the core does and does not do

| The core | Never |
| --- | --- |
| Reads receipts through one strict schema, `progress_review_receipt_v0` | Calls a model, reads a raw delta, or imports the observer package |
| Joins receipts to run rows by `turn_instance_id`, else by `(generated_at, agent_id)` | Overwrites or supplements the Agent's own `progress_observation` |
| Counts only `completed` receipts whose selected drift signal is `True` | Counts `unknown`, `abstained`, `failed`, `stale` or missing receipts |
| Stops the streak at an acknowledged autonomous replan and re-arms | Pauses turns, opens user gates, or settles Goal acceptance |
| Requires one goal contract revision across the counted receipts | Keeps receipts alive across an acceptance-contract change |

The typed repeat fuse keeps precedence. A receipt streak only adds evidence
when that fuse is quiet.

## Policy

```bash
loopx configure-goal --goal-id <goal-id> --progress-review-mode shadow --execute
loopx configure-goal --goal-id <goal-id> --progress-review-mode assist \
  --progress-review-signal noul --progress-review-drift-threshold 2 --execute
loopx configure-goal --goal-id <goal-id> --clear-progress-review-configuration --execute
```

| Field | Values | Meaning |
| --- | --- | --- |
| `mode` | `off`, `shadow`, `assist` | `off` loads nothing; `shadow` records and displays; `assist` may raise the obligation |
| `signal` | `noul`, `choice` | Which receipt judgment pair counts as drift |
| `drift_threshold` | 2–20 | Consecutive completed drift receipts before an obligation |
| `contract_revision` | sha256 or empty | The observer basis revision receipts must be bound to; printed by `loopx-jev drift init`. Required for `assist`; other revisions are stale |

The policy lives at `control_plane.progress_review` in the goal registry and is
visible in `loopx configure-goal --goal-id <goal-id>` under `feature_summary`
and in the Dashboard capability editor. A malformed block fails closed to `off`.

## Receipts

Receipts are written to
`<runtime-root>/goals/<goal-id>/progress-review/receipts/<event-id>.json` by
the observer in the optional `loopx-jev-pilot` distribution
([`packages/loopx-jev/DRIFT_SHADOW.md`](../../../packages/loopx-jev/DRIFT_SHADOW.md)).
Each receipt carries only typed fields:

- identity: `goal_id`, `event_id`, `evidence_id`, `contract_revision`, `sequence`,
  and the run's `turn_instance_id`, `generated_at`, `agent_id`, `todo_id`;
- `status`: `completed`, `abstained`, `failed`, `not_evaluated`, `stale`;
- `judgments.choice`: `relation` and `increment` labels or null;
- `judgments.noul`: probabilities for `behavior_change`, `serves_acceptance`,
  `evidence_increment`, or null;
- `drift_signal.noul` and `drift_signal.choice`: `true`, `false` or null;
- `timing_ns`, `usage`, `label_probability_threshold`, `recorded_at`.

The drift signals follow rule `progress_review_signal_rule_v1` with the label
threshold `t`; the core recomputes them from the typed judgments when it reads a
receipt and rejects any receipt whose booleans disagree:

- `noul`: `P(serves_acceptance) ≤ 1−t` **and** `P(evidence_increment) ≤ 1−t` is
  drift; either probability `≥ t` is not drift; anything else is null.
  `behavior_change` is recorded but not gating.
- `choice`: `relation = off_goal` **and** `increment = no_new_evidence` is
  drift; `on_goal`, `necessary_prerequisite` or `new_evidence` is not drift;
  anything else is null.

Both questions are asked about the change between checkpoints, not the after
state as a whole, so churn on a file that already satisfies acceptance is drift,
while documentation, a negative finding or a prerequisite test that serves a
criterion or adds evidence about it is not.

Receipts found by `turn_instance_id` must also agree on Agent and Todo when both
sides name them; an ambiguous `(generated_at, agent_id)` fallback is never
attributed. The observer writes a pending receipt when it queues an event; the
core skips at most two newest pending receipts so an existing streak neither
grows nor dissolves while evaluation is still running. Receipts bound to a
revision other than the pinned one are stale and never counted.

## What you see

`loopx status --format json` adds `external_progress_review` to a goal item and
its `project_asset` whenever the policy is not `off`: receipt counts by status,
drift counts per signal, and the latest receipt's typed judgments. In `assist`,
a qualifying streak appears as an `autonomous_replan_obligation` whose trigger
`kind` is `external_progress_review_drift`, with `frontier_identity`
`progress_review:<evidence-id>`, a P1 todo action, and the usual
`required: true`, `stop_condition` and ack contract. The heartbeat prompt
already instructs Agents to obey that obligation and acknowledge it with a
typed replan.

## Verifying the differential

`packages/loopx-jev` ships a comparison harness:

```bash
loopx-jev sentinel compare \
  --matrix packages/loopx-jev/tests/fixtures/sentinel/matrix.json \
  --responses packages/loopx-jev/tests/fixtures/sentinel/responses \
  --output /tmp/sentinel-comparison.json
```

For every recorded sequence it reports the first round at which the typed
repeat fuse would fire (never, within the sequence, for self-declared
advancement), the first round at which each receipt signal flags drift, and the
false flags on sequences whose gold label is on-goal. Without `--live` it
replays committed provider responses, so the numbers reproduce in CI without a
key. `python3 examples/progress-review-sentinel-smoke.py` runs the same replay.

## Recorded differential

The committed live recording of the 16-sequence matrix (question set
`scoped-progress-sentinel-v2`, `jev-1.13.0`, 35 rounds, every round
self-reporting `advanced`; one answer rejected by the strict decoder):

| | Typed repeat fuse | `noul` receipts | `choice` receipts |
| --- | --- | --- | --- |
| Drift sequences flagged at their gold round | 0/9 | 9/9 | 5/9 |
| Reaching the `assist` obligation at threshold 2 | 0/9 | 9/9 | 2/9 |
| Real on-goal upstream commits falsely flagged | 0/7 | 0/7 | 0/7 |

Purely cosmetic sequences were flagged at round 1, mixed sequences at their
drift round; a second independent live run reproduced every outcome. The v2
wording was revised after the earlier recording missed post-implementation
churn on these constructed sequences, so they are no longer held-out for the
wording; the seven real commits were not used to tune anything. See the
[operation guide](../../../packages/loopx-jev/DRIFT_SHADOW.md) for the full
table, latency, variance and what remains unproven.

## Boundaries and next step

Escalation (a user gate after an ignored obligation) and pause remain future
work and are not granted here. The observer's prediction quality is a separate
question from this integration; run one Goal in `shadow`, label its receipts
with `loopx-jev drift label`, and compare first-flag rounds before enabling
`assist`.
