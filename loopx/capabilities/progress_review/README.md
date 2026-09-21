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

The drift signals are derived by the observer with its configured label
threshold `t`:

- `noul`: `P(behavior_change) ≤ 1−t` **and** `P(serves_acceptance) ≤ 1−t` is
  drift; either probability `≥ t` is not drift; anything else is null.
- `choice`: `relation = off_goal` **and** `increment = no_new_evidence` is
  drift; `on_goal`, `necessary_prerequisite` or `new_evidence` is not drift;
  anything else is null.

Documentation-only or test-only work that serves an acceptance criterion is
therefore not drift under either signal.

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

The committed live recording of the 16-sequence matrix (`jev-1.13.0`, 35 rounds,
every round self-reporting `advanced`):

| | Typed repeat fuse | `noul` receipts | `choice` receipts |
| --- | --- | --- | --- |
| Drift sequences flagged at or after their gold round | 0/9 | 6/9 | 4/9 |
| Reaching the `assist` obligation at threshold 2 | 0/9 | 6/9 | 1/9 |
| Real on-goal upstream commits falsely flagged | 0/7 | 0/7 | 0/7 |

All six purely cosmetic sequences were flagged at round 1 and would raise the
obligation at round 2, against a periodic review that waits for 20 durable runs.
Cosmetic churn after a real implementation in the same file was not flagged, and
one executed negative probe was flagged in two of three live runs. See the
[operation guide](../../../packages/loopx-jev/DRIFT_SHADOW.md) for the full table,
latency and variance.

## Boundaries and next step

Escalation (a user gate after an ignored obligation) and pause remain future
work and are not granted here. The observer's prediction quality is a separate
question from this integration; run one Goal in `shadow`, label its receipts
with `loopx-jev drift label`, and compare first-flag rounds before enabling
`assist`.
