# D1 scoped drift shadow pilot

[中文](DRIFT_SHADOW.zh-CN.md)

This experimental command captures real, explicitly scoped file changes around a
successful LoopX `refresh-state`, then evaluates them in a **separate consumer**.
It reports historical observations only. It does not correct, pause, redirect,
acknowledge, settle, or inject messages into an Agent. No success-rate or time-saving
claim follows from passing the integration tests.

## Placement and supported journey

The commands live in the optional `loopx-jev-pilot` distribution. Its only
product surface is the D1 shadow command; no ranking code, built-in capability
or scheduler is registered. The source is explicitly `scoped_checkpoint_capture`,
not a claim to be a Decision Context provider. The [decision record](DESIGN_DECISIONS.md)
links the research history and evidence limitations.

The existing L1 `reliability-diagnostics` observer is a separate contract: its
no-egress/no-worker-influence receipt is not reused for model inference. Neither
that observer nor `state_refresh.py` is modified. Jev never runs inside a core
transaction or core write lock.

This is an explicit CLI installation: use the wrapper at the real refresh call
site and run the consumer separately. Ordinary `loopx refresh-state` and native
Codex/Claude sessions remain unchanged. There is no automatic host-hook installer,
registry capability setting, Dashboard or Lark switch in this branch. Settings
are local and bound to one Goal state directory; give each Goal its own config
file. The operator supplies the contract export, which is not itself proof of
canonical Goal acceptance or exclusive workspace ownership.

## Run it

Use Python 3.11+ and the Node runtime required by the LoopX checkout. This
scoped collector targets POSIX file handling on Linux/macOS; Windows capture is
not qualified and unsupported file primitives produce an unavailable observation.
The optional distribution is not part of the default LoopX wheel. Install from
the source root into a fresh environment, then run the no-key checks:

```bash
uv venv .venv-jev
uv pip install --python .venv-jev/bin/python -e '.[test]' -e packages/loopx-jev
.venv-jev/bin/python -m pytest packages/loopx-jev/tests/test_drift.py packages/loopx-jev/tests/test_drift_cli.py -q
.venv-jev/bin/loopx-jev drift --help
```

This slice contains D1 only. Earlier fork D2–D8 commands and ranking code are
excluded. Use `loopx_jev_drift_config_v0` and `minimum_label_probability`; old
multi-direction pilot profiles are rejected rather than silently promoted.
A configured key alone does not activate shadow or allow egress. On failure
the existing Agent workflow continues; no independent Agent judge is launched.

For an existing Goal, create an ignored local directory, copy
[`config.shadow.json`](examples/drift/config.shadow.json) and
[`basis.json`](examples/drift/basis.json), and replace the example Goal id,
objective and acceptance with the intended contract. Optional `evidence` refs
are regular files relative to the delivery workspace, for example an independently
produced test report. Do not put credentials in either file. The config starts
with `allow_egress: false`; set it to true only for approved source material.
Provision `TYPESAFE_API_KEY` in the **consumer process environment**.

The following placeholders refer to that Goal's existing local paths. Initialize
**before the work being observed**, in a dedicated delivery workspace. Each
`--path` is an exact relative file path (a not-yet-created file is allowed), not
a glob or directory. Include relevant tests and research artifacts, not just code.
Do not include the observer directory, mutable LoopX state, or credentials.

```bash
loopx-jev drift init --state-dir "$OBSERVER" --config "$CONFIG" \
  --workspace "$WORKSPACE" --basis "$BASIS" \
  --path src/retry.py --path tests/test_retry.py

# At the original refresh call site, preserve its existing arguments and bindings.
loopx-jev drift refresh --state-dir "$OBSERVER" --config "$CONFIG" -- \
  --registry "$REGISTRY" --runtime-root "$RUNTIME" refresh-state \
  --goal-id "$GOAL_ID" --format json

# Separate shell/process: one pass, or bounded polling while work continues.
loopx-jev drift drain --state-dir "$OBSERVER" --config "$CONFIG"
loopx-jev drift drain --state-dir "$OBSERVER" --config "$CONFIG" --watch-seconds 300
loopx-jev drift status --state-dir "$OBSERVER"

loopx-jev drift configure --state-dir "$OBSERVER" --mode off
loopx-jev drift configure --state-dir "$OBSERVER" --mode shadow
```

Do not omit required Agent/Todo/Turn/validation arguments from a managed refresh;
the wrapper grants no exception to those rules. It preserves original stdout and
exit code and writes a compact capture diagnostic to stderr. No config means
off: no observation files, key lookup or transport import. Dry runs bypass
capture. Capture failure after a successful write does not turn that write into
a failed command; it increments capture failures and invalidates the baseline.
Unknown or invalid output cannot be treated as a successful observation.

Use `configure` to disable/re-enable: its monotonic epoch revokes in-flight work
even if the config returns to identical bytes. Re-enable requires a new baseline
checkpoint before comparison. Directly editing config changes its content hash,
but an off/on edit restored between checks cannot be observed; use the command
for revocation. Changing the contract also resets the comparison baseline.

To uninstall, restore the original `loopx refresh-state` call, stop the consumer,
and uninstall `loopx-jev-pilot` from the selected environment. Retained local
evidence may be deleted according to operator policy; deleting request tombstones
and creating a new state directory is an explicit new experiment/budget, not
transparent continuation.

## Evidence, deduplication and results

- Snapshot comparison covers net committed, staged and unstaged **working-file**
  changes between checkpoints, plus explicitly named untracked files and optional
  evidence files. Git is read only. Index-only changes that leave working files
  identical are `index_only_change_unknown`; no model guess is made.
- Model input includes both checkpoints' scoped file contents, including unchanged
  files, alongside the delta. A probe or new test often cannot be interpreted from
  changed lines alone. The overall request-byte limit still applies: reject an
  oversized packet, never silently remove required context. Equal patches against
  different surrounding source are distinct evidence identities.
- Two reads check stability and the post-refresh read checks it again. This is
  not an atomic filesystem snapshot or an authorship proof. Use a single-writer
  worktree. Unobserved edits restored between reads and out-of-scope work remain
  limitations; diff-only evidence cannot establish whole-task progress.
- Baseline reset, no delta, duplicate event and duplicate evidence do not call
  the model. Goal/Agent/Todo/Turn identity deduplicates checkpoint supplements;
  unbound refreshes use the durable record digest. Identical delta under the same
  contract is not another independent observation. Explicit sequence numbers
  preserve order independently of JSON key sorting.
- Queued evidence is immutable historical input. Subsequent workspace work does
  not invalidate it; contract/config epoch changes or changed/deleted source
  records do. Results never acquire authority over the current task.
- `on_goal`, `necessary_prerequisite`, `off_goal`, `unknown` and the separate
  evidence-increment labels remain distinct. Necessary tests, research, negative
  findings and documentation may advance a Goal without changing runtime behavior.
  `no_new_evidence` alone is not a drift verdict. No consecutive-suspicion fuse
  or automatic escalation is implemented.
- Missing key, egress denial, stale inputs, transport failure and abstention remain
  separate outcomes. Requests are never automatically retried. A durable request
  reservation survives deleted result detail; an unresolved send is not reissued.
  Consumer crashes can reuse a saved provider response without another request.

The fixed bounds are 32 named files, 32 KiB combined file text, 32 KiB optional
evidence text, 32 KiB delta, 16 pending observations and 256 event identities.
Oversize/binary/symlink input is rejected, not silently truncated into a verdict.
The initialized request budget (default 20, at most 100) cannot be increased by
editing the config. Full queues reset the baseline and visibly count a failed
capture; they do not silently stretch one observation over missed rounds.

State directories use private permissions; JSON files are mode 0600. The current
baseline and pending jobs contain raw scoped material and must remain local and
ignored. Completed jobs discard raw deltas; compact results and request
tombstones remain. The reused credential-pattern filter is defense in depth,
not a guarantee that arbitrary source is safe to export. Review the scope.

`status` lists statuses, judgments, capture failures and nanosecond client timings:
pre-capture, original command, capture before final state write, assessment,
transport and worker phases when available. Parent timings include child timings;
do not sum them. Cache timings are marked separately. These measurements do not
identify server-only inference time or time saved by the Agent.

## Qualification still required

Tests cover actual Git and refresh CLI, off isolation, immutable authority
records, replay/restart, concurrent producers, revocation, missing/bad evidence,
queue limits and injected unknown/error/model responses. Injected answers prove
plumbing, not Jev accuracy. Before intervention, independently label held-out
multi-round tasks and compare the existing workflow, Jev shadow and an independent
Agent judge. Report false alarms, misses, abstention, lead time and full overhead.
Only a separate authorized intervention experiment can establish wasted-work
reduction. Monitoring `material_change`, native hook installation, canonical
configuration UI and automatic correction are outside this slice.
