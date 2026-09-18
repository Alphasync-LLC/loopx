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
- The New-vs-Legacy Heartbeat comparison changes multiple runtime dimensions;
  it is mechanism evidence, not a single-variable causal ablation.
- The effective aggregates include designated replacement trials. Some New
  Heartbeat replacements used longer budgets.
- Historical cost is estimated from retained token telemetry. New Heartbeat
  cost is recorded runtime telemetry, so the page treats cost as descriptive.
- LHTB reward and the `>= 0.95` solved threshold remain benchmark-native.

The runnable current Heartbeat implementation lives in `benchmark/LHTB/`.
