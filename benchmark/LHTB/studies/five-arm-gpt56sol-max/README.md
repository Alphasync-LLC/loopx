# LHTB five-arm GPT-5.6 Sol max study

This directory contains the public-safe aggregate used by the LoopX LHTB
research brief at `/benchmarks/lhtb/`.

The study compares 46 matched LHTB tasks across:

1. Plain Codex app-server.
2. Native Codex Goal.
3. LoopX SSH-Goal.
4. Legacy LoopX 0.5.3 Heartbeat over app-server.
5. LoopX 1.0.3 Heartbeat using `generic_cli` and a fresh `codex exec` per wake.

All arms use `openai/gpt-5.6-sol`, `reasoning_effort=max`, and disabled Codex
Web Search. `data.json` contains only aggregate rewards and disclosed runtime
metadata. It intentionally excludes raw trajectories, local filesystem paths,
gateway addresses, credentials, and verifier artifacts.

## Evidence boundary

- Each task-arm cell contributes one effective trial. This is not a
  repeated-seed estimate.
- The primary reading compares the 1.0.3 Heartbeat arm with Plain and Native
  Goal. Runtime and budget differences prevent a single-variable causal or
  equal-budget efficiency interpretation. SSH-Goal and Legacy Heartbeat are
  retained as historical context.
- The effective aggregates include designated replacement trials. Some New
  Heartbeat replacements used longer budgets.
- Historical cost is estimated from retained token telemetry. New Heartbeat
  cost is recorded runtime telemetry, so the page treats cost as descriptive.
- LHTB reward and the `>= 0.95` solved threshold remain benchmark-native.

The runnable current Heartbeat implementation lives in `benchmark/LHTB/`.

## Reading the baseline comparisons

The brief derives these comparisons from the 46 `tasks` rows in `data.json`,
without modifying the experiment data:

| LoopX 1.0.3 Heartbeat versus | Mean reward delta | Relative mean gain | Wins / ties / losses | Strict solves (LoopX / baseline) |
| --- | ---: | ---: | --- | --- |
| Plain | +0.0731 | +17.3% | 17 / 13 / 16 | 7 / 7 |
| Native Goal | +0.0473 | +10.6% | 23 / 13 / 10 | 7 / 4 |

Mean delta is the mean of per-task differences; relative gain divides that
unrounded delta by the baseline mean. Wins, ties and losses compare published
unrounded rewards strictly; equality is not statistical equivalence. Display
rounding is applied only afterwards. The historical `heartbeat_comparison`
summary is retained in the source archive but is not used for these comparisons.

The task matrix defaults to Plain, Native Goal and LoopX Heartbeat; readers can
expand both historical arms. Case scores come from the same task rows rather
than a separate editorial copy. The recorded scores support outcome comparisons;
reported recovery or regression cases are mechanism clues, not causal estimates.
