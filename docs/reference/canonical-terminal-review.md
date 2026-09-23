# Canonical terminal review and validation

On an explicitly promoted local Goal, Agent completion and Monitor stop now use
the same reviewed recovery path as Todo edits and User completion. The initiating
Chat action binds the complete provider revision and registry digest, preserves
one operation identity, and acknowledges display only after the existing
projection outbox confirms the current view.

## Operate and recover

For ordinary CLI completion, retain the same explicit completion identity after
a lost response:

```bash
loopx todo complete --goal-id example-goal --todo-id todo_work \
  --agent-id agent-a --completion-identity-key reviewed-result --no-follow-up
loopx todo list --goal-id example-goal --todo-id todo_work
loopx todo project-markdown --goal-id example-goal --execute
```

Use `--no-follow-up` only when no successor is needed. Leased work additionally
requires its current `--task-lease-idempotency-key` and
`--task-lease-expected-version`; owner confirmation is not a lease or a lifecycle
grant. Chat users retry the same failed proposal. A stale proposal requires a
fresh preview, not a replacement identity that bypasses review.

| Boundary | Observable result |
| --- | --- |
| Provider/registration changes before a fresh reviewed completion | Reject before private validation execution; Chat marks the proposal stale |
| Provider changes during validation | Reject the old validation result; Todo remains unfinished |
| Lease expires during validation | Recheck runtime time and reject stale execution proof |
| Canonical commit succeeds, display delivery fails | Business remains committed; Chat reports recoverable failure without a successful display receipt |
| Response/action receipt is lost after commit | Retry recovers the original business receipt before checking current review freshness |
| Same operation carries a changed reviewed note, evidence, reason or basis | Reject identity reuse; never silently acknowledge the changed intent |
| Private declaration is unavailable after successful completion | Business receipt can recover from its public commitment; lossless display recovery still requires restoring the original declaration |

The TypeScript terminal owner performs admission, source checks, validation
planning, lease retirement, linked effects, CAS and receipt recovery. Python
transports facts, resolves private argv only when requested, executes declared
validation and drains projection. It does not decide whether a stale validation
can complete work. The preview executes no validator. Separate user-completion
edits retain their existing combined edit/terminal semantics and old stored Chat
proposals retain their existing protocol.

## Wire and migration boundary

The current Python terminal adapter sends
`loopx_local_coordination_todo_terminal_lifecycle_request_v2` for named
operations. It sends
`loopx_local_coordination_todo_terminal_lifecycle_request_v3` only when it
completes a `continuous_monitor` without an explicit completion identity. In
v3, `operation_id` is null on the wire. The TypeScript owner derives it from
the Goal id, Todo id, and `material_change_generation`. Reopening the Monitor
advances that generation, so a receipt from an earlier cycle cannot complete
the current open cycle. If an explicit operation already completed the current
cycle, v3 records a generation-scoped no-change receipt instead of guessing
that a legacy unscoped receipt belongs to that cycle. A v2 retry can still
recover a legacy receipt by supplying its original operation id. Explicit
identities and non-Monitor completion remain on v2.

The terminal method also accepts these bounded additions:

- `review_basis`, when present, contains exactly `provider_revision` and
  `registry_sha256`. It binds reviewed intent and is part of receipt identity.
- `validation_source_provider_revision` is null before an issued effect and is
  the returned revision on continuation. It is a freshness constraint, not new
  operation identity. Both caller validation and Goal acceptance validation
  require it in v2.
- `validation_declaration_sha256` carries the canonical public commitment.
  Historical recovery precedes private declaration resolution. Fresh execution
  still requires the matching declaration and current authorization.

The existing method may return `resolve_validation` before `execute_validation`.
Both responses bind the source revision; neither commits the business operation.
For a validated fresh completion the host crosses the runtime boundary three
times (resolve, plan effects, commit), versus two before this change. Unvalidated
completion and historical recovery remain one terminal request. This bounded
extra crossing makes receipt recovery independent of host-local argv; it can
disappear when the native host owns declaration resolution and effect execution.

v0/v1 retain their old request fingerprints and validation contract. They reject
the new fields rather than silently discarding obligations. A v2 request without
review preserves the existing CLI terminal fingerprint. Existing receipts are
not rewritten. The public completion facade rejects a reviewed canonical request
if authority has reverted to an unpromoted legacy path.

No provider default, promotion, permission, retention or storage format changes.
Rollback restores compatible code while retaining provider data, receipts and
writer fences. Code that does not recognize the request version cannot execute
it; regenerate a preview with compatible code instead of stripping its review
fields or supplying an operation id for v3. Markdown stays a permanent display.
These changes close the terminal review/recovery family, not all leased metadata
updates, executor-held external-effect fencing, D1–D3 or whole-Goal cutover.

Shared provider conformance uses the complete production-scale fixture, both
native and imported records, stale review/validation, expired proof, lost commit
response and unchanged non-target state. Real File/SQLite Chat HTTP tests exercise
the packaged entrypoint and retry feedback. The frontend runtime decoder and shared action-review plan now recognize the
terminal basis for exactly Agent completion and Monitor stop. The packaged Chat
bundle includes the original-operation retry path and distinguishes pending
display from verified completion; no new configuration or visual control is required. Lark receives no new
command or transport in this slice.
