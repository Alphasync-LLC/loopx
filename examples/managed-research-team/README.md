# Synthetic research team

A cloud coordinator asks two registered local dsh workers to analyze a filing
and its correction, reviews independently accepted evidence, and writes a
combined report. There is no `phase` argument or script that selects the next
business step. The model chooses delegation questions and order through three
MCP tools: `read_assignment`, `delegate`, and `write_report`.

This is a bounded composition example for the optional
[Ark Turn adapter](../../packages/loopx-ark-turn/README.md), not a fleet scheduler.
It prepares an isolated synthetic Goal, roster and worktrees, then launches one
coordinator Turn. Each delegation uses the existing Todo and `turn run-once
--host dsh` entrypoints. The coordinator uses `--host generic-cli` with the same
Turn request/candidate and independent acceptance boundary.

## Run

From a matching source checkout, install the optional providers into the same
interpreter. Default LoopX installations do not download either SDK.

```bash
uv sync --extra test --extra deepseek-harness
uv pip install --python .venv/bin/python -e packages/loopx-ark-turn
```

Configure `ARK_API_KEY`, `ARK_MODEL_ID`, `ARK_ENVIRONMENT_ID` and
`DEEPSEEK_API_KEY` in the environment. The Ark Environment must already exist
and belong to the operator; the demo never creates or deletes it. The local
dsh profile defaults to `deepseek-v4-flash@high`; override `--dsh-model` explicitly
for another qualified local profile. Credentials are not command arguments.
The adapter forwards the local worker credential only to the trusted demo MCP
process, never to cloud tool arguments/results.

Choose a **new** private disposable directory outside the source checkout's
tracked files. Runs may invoke up to eight local worker attempts and one cloud
session, with a 20-minute outer bound; provider usage can accrue on rejected
attempts too. Do not point this demo at an active Goal or research workspace.

```bash
uv run --no-sync --extra test python examples/managed-research-team/demo.py \
  run "$DEMO_ROOT" --model "$ARK_MODEL_ID" --environment-id "$ARK_ENVIRONMENT_ID"

uv run --no-sync --extra test python examples/managed-research-team/demo.py \
  validate-report "$DEMO_ROOT"
```

The launcher exits unsuccessfully unless the lead Turn commits validated
progress. Inspect `lead/report.json`, `accepted/`, `turns/`, `lead-turn.json`
and `provider-receipts/` inside that private directory. These local artifacts
are not public demo fixtures or publishable run logs. Inspect canonical state
with the existing CLI, using absolute values for the two local paths:

```bash
uv run --no-sync --extra test python -m loopx.cli \
  --registry "$DEMO_ROOT/registry.json" --runtime-root "$DEMO_ROOT/runtime" \
  --format json todo list --goal-id synthetic-managed-research
```

The host receipt's tool ACK only means a result reached the provider. Each
worker must pass the independent validator and canonical Turn writeback; the
lead must then adopt all four exact artifact hashes and pass a separate
aggregate validator. The `accepted/` files are evidence copies produced by
this trusted example service, not an alternative Todo/lease/acceptance store.

## What the scenario checks

| Evidence | Initial | Corrected | Required interpretation |
| --- | --- | --- | --- |
| Cash from operations | 120 | 105 | Correction changes the consumed input |
| Capital expenditure | 30 | 30 | Raw FCF becomes 90 → 75 |
| Receivables sold, included in cash | 50 | 50 | Normalized FCF becomes 40 → 25 |
| Current vs prior fiscal period | H1 vs FY | H1 vs FY | Neither positive nor negative growth is established |
| Repost of the issuer | Same source | Old figures retained | One independent family; stale only after correction |

Worker outputs bind the input bytes by SHA-256. The final report binds each
worker/revision output by hash, incorporates the correction and checks the
semantic conclusions. A valid-looking report with a missing/unaccepted worker,
stale dependency hash, altered input, wrong calculation or unsupported growth
claim is rejected. Tests mutate these conditions independently of model output.

## Qualification recorded for this slice

One final local run passed through the real public Ark API (`arkruntime 0.8.0`,
`doubao-seed-2-1-pro-260628`) and real dsh (`deepseek-harness-sdk 0.1.5rc1`,
`deepseek-v4-flash@high`). Four worker Turns and the lead Turn committed
`validated_progress`; a separate report readback passed. The cloud model used
six local tool calls: assignment read, four delegations, and report submission.
The host confirmed its session and Agent absent; the experiment owner separately
deleted its disposable Environment. No model calls run in CI.

Earlier qualification attempts failed on event identity decoding, pagination,
missing local runtime and ambiguous source-count scope. They were not accepted
as successful work. The fixes use the custom-tool event id as result correlation,
opaque `next_page` tokens, a local dependency preflight, explicit current-period
source counting and actionable field-level rejection. An interrupted canary
also cleaned its owned resources; a cleanup retry retired a known pending
session without repeating work. Uncertain *creation* still requires manual
reconciliation. This is one bounded success after repairs, not a reliability,
throughput or arbitrary-scale claim.

Deterministic checks use the real SDK over synthetic HTTP fixtures plus a real
stdio MCP process. They cover input/capability mismatch, duplicate and changed
event identities, pagination beyond 200 events, timeout/cancellation, competing
starts, cleanup-only replay and semantic/dependency mutations. Both existing
DSH CLI smokes are byte-identical against the pre-change baseline; dropping the
Turn identity in a disposable baseline makes the same oracle reject writeback.

## Boundaries and cleanup

The model does not choose an executable, credential, workspace, roster or
validator. The trusted MCP service binds the caller and permits only the two
workers and two input revisions. It serializes delegated Turns and permits two
attempts per worker/revision. It deliberately does not implement a new queue,
Inbox, lease owner or continuation mechanism. The three Agent identities and
all canonical work remain in LoopX; ephemeral provider sessions are execution
resources. MCP tool execution uses local OS permissions and requires a trusted
server; the cloud sandbox does not isolate local subprocesses.

This example qualifies a managed coordinator calling local workers within one
bounded Turn. It does not establish arbitrary team size, parallel fairness,
multi-level recursive launch, restart recovery of the coordinator, live
steering, distributed authority, or persistent Chat/Lark/desktop integration.
Those remain with the existing team/session RFCs. The roster and acceptance
are fixed by the operator; there is no claim of autonomous permission creation.

On normal completion the adapter deletes its owned Ark session and Agent and
confirms absence. The configured Environment remains. On failure inspect the
private provider receipt and use the adapter's cleanup operation for known
resources; unresolved creation requires operator reconciliation. Stop before
removing the disposable directory, and retain incomplete receipts. Removing
this example or its explicit host command disables it; it installs no monitor
or recurring automation and modifies no existing Goal.

## 中文操作与能力说明

这是一次有界的真实协作：云端协调员自行决定问题和委派顺序，本地分析员、核验员
分别处理初始数据和修订数据，然后云端综合四份独立验收的产物。启动脚本只准备
隔离环境、注册名单并启动一次 Turn，没有人为输入 `phase` 来推进业务流程。

按上面的命令安装两种可选 SDK，配置模型、已有云端 Environment 和凭据，再使用
新的私有目录运行。`validate-report` 会重新检查计算、期间可比性、来源独立性、
修订采用和四份依赖的哈希。工具返回、worker 通过验收、总报告通过验收是不同事实。
所有演示数据都是虚构数据，不涉及真实证券建议、交易或私有研究资料。

这提供了可复用的本地/云端受控工作单元，以及“managed Agent 可以继续委派”的
实际调用样例。它还不是完整数字团队产品：持久 Inbox/queue/steer、自动扩缩容、
多层级恢复及前端/Lark 团队入口仍需沿现有 RFC 完成。本次不会改变管家默认执行器
或看板。正常结束会清理本次云端 Agent 和会话，不删除你配置的 Environment；失败
时保留私有回执，按适配器说明检查和清理，不能用删除回执来掩盖未清理资源。
