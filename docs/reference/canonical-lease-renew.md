# Canonical lease renewal, transfer and release

An already promoted local File or SQLite Goal runs `task-lease renew`,
`transfer` and `release` through one TypeScript coordination transaction owner.
Previously only renewal used that provider path; transfer/release hit the legacy
writer fence. Unpromoted Goals retain the legacy transaction path. Selecting a
provider does not promote a Goal or grant execution authority.

## Operate the current lease

Read the current canonical lease and use its owner, execution key and version:

```bash
loopx --registry registry.json task-lease inspect \
  --goal-id example-goal --todo-id todo_work --format json
loopx --registry registry.json task-lease transfer \
  --goal-id example-goal --todo-id todo_work --owner agent-a \
  --idempotency-key execution-a --expected-version 3 \
  --new-owner agent-b --new-idempotency-key execution-b --ttl-seconds 600
loopx --registry registry.json task-lease renew \
  --goal-id example-goal --todo-id todo_work --owner agent-b \
  --idempotency-key execution-b --expected-version 4 --ttl-seconds 600
loopx --registry registry.json task-lease release \
  --goal-id example-goal --todo-id todo_work --owner agent-b \
  --idempotency-key execution-b --expected-version 5
```

The example assumes an active lease at version 3 and an unclaimed Todo or a Todo
already assigned to the eligible receiver. Transfer does not reassign the Todo
claim, override an exclusion, or widen write scopes. Use the actual readback
versions, not these example numbers.

| Operation | State change | Admission |
| --- | --- | --- |
| Renew | Version +1; owner/key/epoch/scopes unchanged; expiry is runtime clock + TTL | Active lease, current proof, registered eligible owner, active open Todo |
| Transfer | Version +1 and epoch +1; replace owner/key; retain scopes; set expiry | Active lease, current proof, registered sender and eligible receiver; new execution key |
| Release | Retain version/epoch; persist released status and timestamps | Current owner/key/version proof; expiry, removed registration and closed/archived Todo do not prevent cleanup |

A missing lease at expected version 0 or an already released matching lease
returns a durable `no_change` receipt. Its storage cursor can advance while
lease state, timestamps and domain events remain unchanged. A wrong version or
wrong proof never becomes successful cleanup. Renew/transfer reject archived
Todos and safe-integer generation exhaustion before writing. The generation
check also protects the legacy path; release at that generation remains legal.

## Commit, retry and readback

One provider CAS commits the lease projection, event and original receipt.
Operation identity includes operation, Goal, Todo, owner, execution key and
expected version. The immutable request digest additionally binds TTL and the
transfer receiver/key. A retry with changed intent is rejected. The shipped
renewal receipt schema, identity and digest encoding remain compatible.

`status=replayed` and `idempotent=true` return historical results even after a
later renewal, transfer, release or expiry. They do not grant present execution
rights or renew again. Freeze the original request after a lost/ambiguous
response; recover its receipt, then inspect current state before new work.

The canonical-only lifecycle request is closed and versioned. The prior
renew-only wire remains accepted for renewal only. An older runtime rejects the
new schema entirely. Missing/invalid fences, changed registration facts before
renew/transfer, unavailable providers and CAS conflicts fail closed. They never
fall back to a lease file or stale/malformed Markdown. Release admission uses the existing proof without a registration snapshot.
The CLI still resolves its runtime root from the registry or explicit override.

Responses expose provider/revision/cursor and current-versus-expected version
on a version conflict. They do not invent a `lease_path`, write a second shadow
authority or require Todo Markdown regeneration for a lease-only change.

## Provider and delivery boundary

The local opening handle supplies provider provenance; lease commands no longer
classify stores with concrete File/SQLite class checks. PostgreSQL uses that
same handle only when a service owner supplies the existing scoped factory and
matching store incarnation. There is no credential-bearing CLI option, implicit
service activation or fallback. The real PostgreSQL rehearsal exercises this
public native lifecycle route as well as the storage contract.

This closes existing-lease mutation under shared-authority L3 / roadmap R5.
Fresh acquisition/reclaim, executor holder/terminal fences and automatic
cross-agent result return retain their own callers and qualification. A lease
transfer alone does not prove a completed collaboration journey. No storage
format, default profile, active-Goal migration, D2 soak or D3 promotion changes.

Rollback retains canonical state, receipts and the writer fence. Older code may
reject transfer/release or the new wire; plan for current lease expiry and
restore compatible code. Do not remove the fence or revive stale lease files.

## Validation

The shared production-scale fixture adds an execution-handover dimension while
retaining its mixed status, decision and historical-lease population. Every
AuthorityStore conformance arm covers native/imported records, negative
admission, stale senders, response loss, CAS competition, no-op sealing and
historical replay. Real File/SQLite CLI and killed-process tests cover the host
boundary; PostgreSQL uses an isolated real server. NoKV coverage uses its
existing test transport and is not service qualification.

For a read-only Goal snapshot, compare an immutable clean legacy checkout with
File, SQLite and real PostgreSQL through the native public lifecycle entrypoint:

```bash
# LOOPX_TEST_POSTGRES_URL must identify a disposable server.
uv run --extra test python examples/control_plane/authority-lease-lifecycle-rehearsal.py \
  --registry registry.json --goal-id example-goal \
  --baseline-repo ../loopx-baseline --execute-isolated-postgresql
```

Use the source-checkout Python environment and a qualified SQLite Node runtime.
The runner adds one synthetic Todo/lease only to disposable copies, compares
all operation results and non-target records, and verifies that the live source
is unchanged. It reports the legacy historical-replay rejection as an explicit
semantic improvement, not as normalized parity. Optional `--private-diagnostics`
keeps raw failures in an owner-only file that must not be published. This does
not replace [D2 capacity and continuity qualification](sqlite-authority-store.md).

## 中文操作与语义

已 promoted 的 File/SQLite Goal，其 renew、transfer、release 现在共用一笔 TS
canonical transaction。此前只有 renew 能走 provider，另两项会被旧 writer fence
挡住。未 promoted 的默认路径保持；选择 provider 本身不构成 promotion。

按上面的命令先 inspect，再使用实际 owner/key/version。续租只增加 version；转交
增加 version 和 epoch，必须换 execution key，并检查双方注册及接收方资格；两者
保留 write scopes。转交不改变 Todo claim，不覆盖排除规则。释放保留版本与 epoch，
记录 released 状态和时间；只凭当前 owner/key/version 清理，允许已到期、已注销
owner 和已关闭/归档 Todo。版本不匹配仍拒绝。

缺失 lease 的 version 0 清理及已释放 lease 的匹配清理，会封存 `no_change` receipt：
存储 cursor 可以前进，但 lease、时间和 domain event 不变。归档 Todo 禁止再次
续租/转交；version 或 epoch 无法安全递增时，两种存储路径都拒绝，仍允许释放。

lease/event/receipt 原子提交。重试身份绑定 operation、Goal、Todo、owner、execution
key 和 expected version；不可变 intent 另绑定 TTL 及接收者/key。改 intent 重试会
被拒绝。既有 renew receipt 和 digest 保持兼容。历史 replay 可以跨后续转交、续租、
释放和到期，返回原结果而不改变当前状态，也不重新授予执行权。响应不确定时冻结
原请求恢复，再 inspect 当前状态。

新 wire 只接受既有 lease 的三类操作，旧 renew wire 仍只接受 renew；旧 runtime
会拒绝新 schema。fence、provider、提交前注册源变化或 CAS 失败都不回退。返回值
包含 provider/revision/cursor 及版本冲突细节，不创建第二份 lease/shadow 状态，
不为 lease-only 修改重写 Markdown。释放 admission 不需要注册快照；CLI 仍从 registry
或显式 override 解析 runtime root。

PostgreSQL 复用同一个 opening handle，但必须由 service owner 提供已有的 scoped
factory 并核对 incarnation；没有新增凭据参数或自动启用服务。真实四臂演练验证
相同公共 native 入口；NoKV 仅经过已有测试 transport，不代表其服务已合格。

这是 L3/R5 的既有 lease 修改闭环，fresh acquire/reclaim、executor fence 及自动
结果返回仍须各自验收。没有改存储格式、默认 provider、活动 Goal、D2 soak 或 D3
晋升。回滚保留 canonical state/receipt/fence，考虑旧版本拒绝操作与 lease 到期，
恢复兼容代码；不能删 fence 或复活旧 lease 文件。上面的只读快照演练只修改隔离
副本，输出摘要，核对源与无关记录不变，不能替代完整持久性资格。
