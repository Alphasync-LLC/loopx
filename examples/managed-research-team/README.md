# Synthetic research team

A local coordinator organizes two local DSH Agents and two cloud Ark Agents
to analyze a filing and its correction. An Ark reviewer adopts a local
analyst's result, independently checks it, and returns evidence for the local
coordinator's combined report. There is no `phase` argument or script that
selects the next business step. The model chooses questions and delegation order
through three MCP tools: `read_assignment`, `delegate`, and `write_report`.

This is a bounded composition example for the optional
[Ark Turn adapter](../../packages/loopx-ark-turn/README.md), not a fleet scheduler.
It prepares an isolated synthetic Goal, roster and worktrees, then launches one
local DSH coordinator Turn. Each member uses the existing Todo and Turn owners:
`--host dsh` locally, or `--host generic-cli` with the Ark provider remotely.
The optional `--topology cloud-led` scenario retains cloud-to-local delegation.
Neither profile replaces a persistent steward session or installs a supervisor.

## Run

From a matching source checkout, install the optional providers into the same
interpreter. Use Node 24.21 or later for the qualified File/SQLite example.
Default LoopX installations do not download either SDK.

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
tracked files. The default `local-led` run permits at most two attempts for each
of four member tasks: up to four DSH member Turns, four Ark member Turns and one
local coordinator Turn, with a 20-minute outer bound. The `cloud-led` alternative
permits eight local attempts and one cloud coordinator Turn. Rejected attempts
also consume provider usage. Do not use an active Goal or research workspace.

```bash
uv run --no-sync --extra test python examples/managed-research-team/research_team.py \
  run "$DEMO_ROOT" --model "$ARK_MODEL_ID" --environment-id "$ARK_ENVIRONMENT_ID"

uv run --no-sync --extra test python examples/managed-research-team/research_team.py \
  validate-report "$DEMO_ROOT"
```

The launcher exits unsuccessfully unless the lead Turn commits validated
progress and the host completes its canonical Todo. Inspect `completion.json`,
`lead/report.json`, `accepted/`, `turns/`, `lead-turn.json`
and `provider-receipts/` inside that private directory. These local artifacts
are not public demo fixtures or publishable run logs. Inspect canonical state
with the existing CLI, using absolute values for the two local paths:

```bash
uv run --no-sync --extra test python -m loopx.cli \
  --registry "$DEMO_ROOT/registry.json" --runtime-root "$DEMO_ROOT/runtime" \
  --format json todo list --goal-id synthetic-managed-research

uv run --no-sync --extra test python -m loopx.cli \
  --registry "$DEMO_ROOT/registry.json" --runtime-root "$DEMO_ROOT/runtime" \
  --format json goal-acceptance inspect --goal-id synthetic-managed-research

uv run --no-sync --extra test python -m loopx.cli \
  --registry "$DEMO_ROOT/registry.json" --runtime-root "$DEMO_ROOT/runtime" \
  --format json goal-acceptance verify --goal-id synthetic-managed-research --execute
```

The host receipt's tool ACK only means a result reached the provider. Each
worker must pass the independent validator, canonical Turn writeback, and fresh
TS-owned Todo completion. Only then does delegation return accepted evidence.
The lead must adopt all four exact artifact hashes and pass a separate aggregate
validator that also reads current canonical child completions and bindings.
The `accepted/` files are disposable evidence copies: changing or inventing
them cannot complete a task. Repeated delegation reads canonical state and
revalidates the output without spending another Turn.

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

## Integration with shared Goal acceptance

The launcher now consumes the canonical authority merged in
[PR #4683](https://github.com/huangruiteng/loopx/pull/4683).
`bootstrap.ts` exclusively creates a new disposable runtime, constructs native
Todo records and invokes the production owner-configuration API once. It does
not import test helpers, promote an existing Goal, or modify an active registry.
The initial roster contains four stable worker/revision tasks and one report
task; questions and execution order remain the coordinator's decisions.
In `local-led`, the local analyst and cloud reviewer handle initial evidence,
while the cloud analyst and local reviewer handle corrected evidence. The cloud
reviewer must wait for canonical completion of the local analysis, read it
through its bound tool, independently verify it and adopt its exact hash.
Submitting or delegating that review too early is rejected without starting a
member Turn. The roster and dependency declaration are also pinned verifier
inputs, so editing them cannot silently remove an acceptance requirement.

Each child binds only its own pinned criterion. The report criterion validates
all four completed dependencies, matching current TS binding guards, exact
artifact hashes and research conclusions. This avoids a cycle where a child
would need the final report before finishing. `turn --todo-id` selects the exact
authorized task through the existing quota owner; it never falls back to a
different task and does not retarget a resumed Turn.

`acceptance.py` reads Todo and acceptance projections at the same provider
revision, rejecting a concurrent change. It performs domain checks; it cannot
write completion state or configure bindings. The trusted host invokes the
ordinary `todo complete` path, which freshly executes the pinned validator and
commits through TS authority and CAS. Binding, lifecycle, lease and quota rules
are not recreated in Python. Completion observations such as `no_followup`
preserve the work digest; changed requirements still stale the association.

All five Todos may become done while the Goal stays active. Turn progress,
task completion, configured-check acceptance and owner approval of the whole
Goal remain separate facts. The aggregate dependency check is specific to this
example, not a new general work-graph join protocol.

Autonomous creation of new bound work still needs a scoped, intent-preserving
derivation policy under R2/R3/R4. The model gets no configure/disable tool, and
delegation never impersonates the owner to repair a stale contract.

Deterministic integration tests execute real File and SQLite providers and the
production CLI. They reject forged acceptance copies, incomplete dependencies,
semantic task edits, changed pinned validators, changed artifacts after a prior
check, wrong report hashes and failed Turns. They also prove child-before-parent
completion, retry on the same task, exact out-of-order selection, completed-work
reuse and refusal to bootstrap over existing state:

```bash
uv run --no-sync --extra test python -m pytest -q \
  packages/loopx-ark-turn/tests/test_canonical_team.py
```

## Qualification recorded for this slice

Both profiles passed with the real public Ark API (`arkruntime 0.8.0`,
`doubao-seed-2-1-pro-260628`) and real DSH (`deepseek-harness-sdk 0.1.5rc1`,
`deepseek-v4-flash@high`):

| Profile | Executed relationship | Canonical readback |
| --- | --- | --- |
| Local lead, mixed members | Two DSH and two Ark members; cloud reviewer adopts completed local analysis; results return to local DSH lead | Four child Todos and report Todo done; all configured checks pass; Goal active |
| Cloud lead, local members | Ark chooses questions/order for two DSH identities over both revisions and adopts four outputs | Five Todos done; all configured checks pass; Goal active |

Owned Ark sessions and Agent definitions were confirmed absent; the experiment
owner separately deleted the disposable Environments. No model calls run in CI.
This validates synthetic evidence with real execution, not real-market research
quality or an attached persistent Codex task.

Earlier qualification attempts failed on event identity decoding, pagination,
missing local runtime and ambiguous source-count scope. They were not accepted
as successful work. The fixes use the custom-tool event id as result correlation,
opaque `next_page` tokens, a local dependency preflight, explicit current-period
source counting and actionable field-level rejection. An interrupted canary
also cleaned its owned resources; a cleanup retry retired a known pending
session without repeating work. The local-led integration also exposed DSH's
intentional MCP credential scrubbing, repaired with explicit environment
references. A mixed run recovered after a tool request timeout: concurrent
relaunch was refused, the original task completed, and the coordinator retrieved
its result and repaired the report's dependency hash. Coordinator tool waits now
cover the bounded child Turn plus its completion/readback; rejection feedback
names the mismatched dependency. Uncertain *creation* still requires manual
reconciliation. These are bounded successes after repairs, not reliability,
throughput, cancellation-supervision or arbitrary-scale claims.

A final mixed run rejected a malformed source list and a cloud execution
timeout; the local lead retried both and reached five independently verified
completions. The timed-out cloud attempt left a known pending session, which
the experiment owner reconciled and confirmed absent before deleting the
Environment. The child host deadline now reserves room beyond Ark execution
for deletion and absence checks. This does not guarantee immediate provider
deletion or replace receipt-based reconciliation.

Deterministic checks use the real SDK over synthetic HTTP fixtures plus a real
stdio MCP process. They cover input/capability mismatch, duplicate and changed
event identities, pagination beyond 200 events, timeout/cancellation, competing
starts, cleanup-only replay and semantic/dependency mutations. Both existing
DSH CLI smokes are byte-identical against the pre-change baseline; dropping the
Turn identity in a disposable baseline makes the same oracle reject writeback.

## Boundaries and cleanup

The model does not choose an executable, credential, workspace, roster or
validator. The trusted MCP service binds the caller and permits only the fixed
worker/revision assignments. It serializes delegated Turns and permits two
attempts per worker/revision. It deliberately does not implement a new queue,
Inbox, lease owner or continuation mechanism. The configured Agent identities and
all canonical work remain in LoopX; ephemeral provider sessions are execution
resources. MCP tool execution uses local OS permissions and requires a trusted
server; the cloud sandbox does not isolate local subprocesses.

DSH intentionally scrubs credential-shaped variables from MCP subprocesses.
The local lead's Cordis patch explicitly forwards the two provider credentials
using `!!js process.env.NAME` references. Only variable names are written to
configuration; values stay in the local execution environment and never enter
cloud tool arguments/results. The local service refuses startup without that
explicit environment. Ark worker MCP processes receive neither provider key.

The main profile exercises a local DSH coordinator with mixed DSH/Ark members;
the secondary profile exercises a cloud coordinator calling local workers.
Cloud members only receive their assigned input, authorized upstream artifact
and output tool; no arbitrary filesystem or shell tool is exposed.
This does not establish arbitrary team size, parallel fairness,
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

主路径是本地协调员组织两个本地 DSH 成员和两个云端 Ark 成员，自行决定问题和
委派顺序。本地分析员先提交初始资料分析，云端核验员必须取得已完成的产物、
独立核验并采用其精确哈希；另两个成员分析修订资料，最后结果回到本地汇总。
启动脚本只准备隔离环境、预授权名单和验收合同并启动一次 Turn，没有人为输入
`phase` 推进业务。加 `--topology cloud-led` 可运行云端协调员委派本地成员的辅助场景。
这次本地协调端用已接入的 DSH Turn 验证，尚未把既有的长期 Codex 任务接成持久管家。

按上面的命令安装两种可选 SDK，配置模型、已有云端 Environment 和凭据，再使用
新的私有目录运行。`validate-report` 会重新检查计算、期间可比性、来源独立性、
修订采用和四份依赖的哈希。工具返回、worker 通过验收、总报告通过验收是不同事实。
所有演示数据都是虚构数据，不涉及真实证券建议、交易或私有研究资料。

启动器已接入 #4683 合并后的 TS 验收权威：启动前一次性建立四个“成员 × 资料版本”
任务和一个总报告任务，绑定固定验证器。模型自行决定问题和委派顺序；成员交付后
须通过真实 Todo 完成并读回，才向协调员返回 accepted。总报告检查四个子任务的
当前完成状态、绑定与产物哈希，再完成自己的 Todo；五个 Todo 都完成也不关闭 Goal。

File / SQLite 集成测试覆盖子任务先完成、同任务重试、完成后复用、伪造已验收文件、
错误依赖、验证后改产物、修改验证器和语义工作变更。管家不能在委派时重配验收，
也不能靠缓存中的 accepted 标记绕过 TS 权威。bootstrap 仅限新建隔离示例，不是
生产 Goal 晋升工具。动态拆分和多层级调度仍须接有范围的 work-graph 授权。

这提供了可复用的本地/云端受控工作单元，以及“managed Agent 可以继续委派”的
实际调用样例。它还不是完整数字团队产品：持久 Inbox/queue/steer、自动扩缩容、
多层级恢复及前端/Lark 团队入口仍需沿现有 RFC 完成。本次不会改变管家默认执行器
或看板。正常结束会清理本次云端 Agent 和会话，不删除你配置的 Environment；失败
时保留私有回执，按适配器说明检查和清理，不能用删除回执来掩盖未清理资源。
