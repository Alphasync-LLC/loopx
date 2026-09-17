# Quota Monitor Observation Receipt v0 / 配额监控观察回执 v0

## English

### Problem

A heartbeat Turn has exactly one quota settlement identity. When an
`advancement_task` is already bound to that identity, a newly due
`continuous_monitor` must not replace it. The monitor still needs a durable
observation receipt so that its cadence does not starve while long-running
advancement work remains active.

### Contract

- The heartbeat receipt's `todo_id` remains the only settlement Todo. Only
  that Todo may be used by `refresh-state` and `quota spend-slot`.
- `quota monitor-poll --todo-id <monitor>` may record auxiliary, no-spend
  observations in the same Turn only when each requested Todo is a due
  `continuous_monitor` visible to the same Agent. Admission checks the Todo
  authority as well as the bounded decision projection, so a due monitor is
  not rejected merely because it falls outside the compact list.
- The monitor receipt records both `settlement_todo_id` and the observed
  monitor `todo_id`. They may differ; this never grants a second delivery or
  quota-spend identity.
- Each auxiliary observation has an operation identity scoped by the monitor
  Todo, or by a digest of `target_key` when there is no Todo id. Exact retries
  replay that observation; changed content conflicts only with the same monitor
  identity; another due monitor receives an independent no-spend receipt.
  Shipped turn-only receipts remain replayable for their original monitor.
- A receipt-bound monitor remains strict: another monitor cannot be substituted
  for the Turn's settlement Todo. Multiple auxiliary receipts never change the
  already-bound settlement identity.
- After an unchanged auxiliary observation, the original advancement Todo
  remains selected. A material observation may create its independently routed
  successor through the existing monitor contract, but it still does not
  replace the Turn's settlement identity.

### Acceptance

The CLI path must prove that multiple due monitors can each update their cadence
and replay idempotently in one settlement Turn without spending quota, while a
guard replay continues to select the original advancement Todo. Existing
wrong-Todo tests for receipt-bound monitor Turns must remain passing.

### Canonical leased observations and recovery

For a promoted Goal, an existing Monitor execution can supply its current lease
key and version. Read the existing lease first; this command neither acquires
nor renews/releases it:

```bash
loopx task-lease inspect --goal-id "$GOAL" --todo-id "$MONITOR"
loopx quota monitor-poll --goal-id "$GOAL" --agent-id "$AGENT" \
  --todo-id "$MONITOR" --result-hash "$OBSERVED_HASH" \
  --task-lease-idempotency-key "$LEASE_KEY" --task-lease-expected-version "$VERSION" \
  --turn-instance-id "$TURN" --execute
loopx todo list --goal-id "$GOAL"
```

The caller must already have an admitted Monitor Turn and any required host
capabilities. External observation remains the caller's effect; `--result-hash`
does not perform a network poll. Add `--material-change --next-agent-todo ...
--next-action-kind ...` only for changed evidence that needs independent work.

- The registered actor, claim, binding, exclusions and current lease are checked
  against the same canonical revision as observation/generation/successor writes.
  A stale key/version, expired lease, soft-claim lease request or missing hard-lease
  proof rejects the complete mutation. Observation timestamps cannot revive a
  lease. The existing lease remains byte-for-byte unchanged.
  This closes a previous hard-mode hole: a Monitor with no lease could write
  merely because the old implementation only rejected retained leases.
- Canonical due monitors no longer carry the blanket unsupported-writeback
  marker. The scheduler can select them; selection itself is not a lease grant.
- New quota pending receipts use `quota_monitor_poll_pending_admission_v1` to
  freeze the original admitted decision and provider plan before business writes.
  After process loss, retry the **same Turn, observation, intent and original
  proof**. Its durable business receipt can settle after lease release/expiry,
  with the original decision as the event's `before` state. A new observation
  still needs current authority. Quota settlement never spends a delivery slot.
- Lease-bearing quota/provider requests and provider plans use v1; proof-less
  requests retain v0, including their original digests. Completed v0 settlement
  receipts remain readable. Old v0 *pending* receipts have no frozen admission:
  they recover if current admission still holds, otherwise report
  `legacy_monitor_admission_unavailable` and preserve evidence for reconciliation.
  Do not fabricate a historical decision, delete the receipt or repeat a known
  committed effect under a fresh identity to bypass that condition.

File, SQLite and service-opened PostgreSQL share these transaction semantics.
This is not provider activation, new-Goal default selection, cross-host service
qualification or whole-Goal promotion. Unpromoted legacy Goals reject explicit
lease proof. Before downgrading to a version without this protocol, finish v1
pending settlements; older binaries cannot interpret them. Never disable a
writer fence to recover by writing an older Markdown projection.

The bounded real-source rehearsal clones read-only source state and adds only
synthetic records in disposable runtimes. It requires an isolated PostgreSQL URL:

```bash
LOOPX_TEST_POSTGRES_URL="$DISPOSABLE_POSTGRES_URL" \
uv run --extra test python examples/control_plane/authority-monitor-poll-rehearsal.py \
  --registry "$REGISTRY" --goal-id "$GOAL" --baseline-repo "$FROZEN_BASELINE" \
  --execute-isolated-postgresql
```

## 中文

### 问题

一次 heartbeat Turn 只有一个配额结算身份。当 `advancement_task` 已绑定该身份时，
新到期的 `continuous_monitor` 不得替换它；但监控仍需形成持久观察回执，否则长期
推进任务存在时，监控周期会永久饥饿。

### 契约

- heartbeat 回执中的 `todo_id` 始终是唯一结算 Todo；只有它可用于
  `refresh-state` 与 `quota spend-slot`。
- 仅当每个请求对象都是同一 Agent 可见且已到期的 `continuous_monitor` 时，
  `quota monitor-poll --todo-id <monitor>` 才可在同一 Turn 写入辅助、不计费
  的观察回执。准入同时检查 Todo 权威源与有界决策投影，不能仅因到期 monitor
  位于精简列表之外就拒绝它。
- 监控回执同时记录 `settlement_todo_id` 与被观察的 monitor `todo_id`。
  二者允许不同，但不会因此产生第二个交付或配额结算身份。
- 每个辅助观察按 monitor Todo 建立操作身份；没有 Todo id 时，按
  `target_key` 摘要建立身份。精确重试只重放该观察；同一 monitor 下内容变化
  只与该 monitor 冲突；另一个到期 monitor 获得独立的不计费回执。已发布的
  Turn-only 旧回执仍可对原 monitor 重放。
- 若 heartbeat 本身绑定的是 monitor，仍保持严格身份，不能把另一个 monitor
  替换为本 Turn 的结算 Todo；多个辅助回执也绝不改变既有结算身份。
- 辅助观察无变化后，原 advancement Todo 继续保持选中；若观察发生重大变化，
  可按既有 monitor 契约创建独立路由的 successor，但仍不替换本 Turn 的结算身份。

### 验收

CLI 端到端测试必须证明：多个到期 monitor 能在同一结算 Turn 中分别更新周期并
幂等重放、全程不消耗配额；随后重放 guard 仍选择原 advancement Todo。同时，
receipt-bound monitor Turn 的错误 Todo 替换测试必须继续通过。

### Canonical 带租约观察与恢复

已晋升 Goal 的 Monitor 若已有执行租约，可用上述命令读取租约，并传入当前 key 和
version。调用方须已有合法 Monitor Turn 和所需 host capabilities；外部观察由调用方
执行，`--result-hash` 不会自行发起网络轮询。只有新证据需要独立工作时才增加
`--material-change --next-agent-todo ... --next-action-kind ...`。

- 注册 actor、claim、binding、exclusion 和当前租约在同一 canonical revision 上校验；
  观察、generation 与 successor 原子提交。过期、错 key/version、soft-claim 下携带租约
  或 hard-lease 下缺少凭据均整笔拒绝。旧观察时间不能复活租约；租约内容保持不变。
  同时修复旧 hard-mode 缺口：过去仅检查“是否保留 lease”，反而让没有租约的 Monitor
  在 hard mode 下写入；现在该分支明确拒绝。
- Canonical 到期 Monitor 不再被统一标为“不支持 writeback”，可进入调度选择；被选中
  本身不授予执行租约。此默认变化只影响 canonical Monitor 的调度可见性。
- 新 pending receipt 使用 `quota_monitor_poll_pending_admission_v1`，在业务写入前
  冻结原准入决策与 provider plan。进程丢失后，用**相同 Turn、观察、intent 和原凭据**
  重试；已提交业务的回执可在租约释放／过期后补结算，event 的 `before` 仍是原决策。
  新观察依旧需要当前权限；结算不消耗 delivery slot。
- 携带租约的 quota/provider request 和 provider plan 使用 v1；无 proof 的请求保留
  v0 及原 digest，已完成的 v0 结算继续可读。旧 v0 pending 没有冻结准入：当前准入仍
  成立时可恢复，否则报告 `legacy_monitor_admission_unavailable`，保留证据供核对。
  不得伪造历史准入、删除回执，或换新 identity 重做已知提交的业务来绕过它。

File、SQLite 与经 service 打开的 PostgreSQL 共用此事务语义；这不等于 provider
启用、新 Goal 默认切换、跨 host 资格或整 Goal 晋升。未晋升 Goal 拒绝显式租约凭据。
降级到不支持此协议的版本前，应先完成 v1 pending settlement；旧程序无法解释它们。
不得通过关闭 writer fence、恢复旧 Markdown 写入来绕过恢复要求。

上述 rehearsal 命令只读源数据，在临时 runtime 中增加合成记录，比较冻结基线及三个
真实后端；要求隔离 PostgreSQL，输出限于计数和摘要，不写回原 Goal。
