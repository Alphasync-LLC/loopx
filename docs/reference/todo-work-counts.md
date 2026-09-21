# Todo work counts and bounded display

Todo lists, status and quota summaries carry `work_counts` with schema
`todo_work_counts_v0`. Counts are computed before display limits; quota
recomputes them **after** the existing Agent scope and resume selection.
The contract is read-only. A count never grants a claim, lease, capability,
validation exemption or execution permission.

```sh
loopx --format json todo list --goal-id example --role agent --limit 1 --thin
loopx --format json status --goal-id example
loopx --format json quota should-run --goal-id example --agent-id agent-a
```

The first command returns one Todo while its role summary retains the matched
source's counts. A filtered list describes its filtered source. This is not a
new provider setting: legacy inputs and promoted File/SQLite inputs share the
same typed summary owner. PostgreSQL uses the same provider-neutral records;
service deployment and whole-Goal promotion remain separately qualified.

| Field | Meaning |
| --- | --- |
| `open` | Nonterminal source rows, including blocked work; it is not executable work |
| `advancement` | Observed actionable advancement rows; acceptance-denied and unsatisfied resume rows do not qualify |
| `monitor` | Observed actionable Monitor rows, including future/expired observation context; due/schedule-gap fields retain their existing separate meanings |
| `hidden` | Declared source rows not available for classification, not rows hidden by UI pagination |
| `complete` | Whether the available source covers the declared scope; false counts are lower bounds for classified task kinds |
| `agent_id` | Agent execution scope, or null for an unscoped/role summary |

The observed row count is derived as `open - hidden`; the payload does not
repeat it as a second value that could drift.

`complete=false` survives repeated quota projection, even when the surviving
subset fits on one screen. It cannot certify “Monitor-only work remains.”
Legacy display-only inputs are deduplicated by Todo identity; contradictory
fragments cannot certify completeness. A missing task is never guessed to be
advancement work. Invalid count envelopes and differently scoped count reuse
fail explicitly.

The TypeScript `todos/summary_lanes.ts` owner returns indexes into the one input
array instead of repeating full Todo bodies for each lane. The Python adapter
normalizes legacy fields/timestamps and validates the returned ordinal bounds.
One observation time governs Monitor due and expiry classification within the
batch. Source order, completed/deferred conventions and claimant visibility
remain compatible; `done_count` still includes deferred rows as required by its
existing summary contract.

Intentional corrections: 21 executable Todos no longer become 8 because the
backlog display limit is 8; a compact quota payload no longer turns that count
into 2. Unknown hidden rows are not classified. Public canonical `todo list`
also retains the acceptance guard from the same read revision, so held work
cannot appear executable there while status says it is held. Acceptance-off
reads keep their existing selection behavior.

Markdown stays a permanent display. These reads do not rewrite stale/missing
Markdown, create receipts or mutate canonical records. The additive count
field is not persisted in Todo authority. Older readers can ignore it, but
retain their old undercount behavior; rollback does not require data migration.
T1/T2 caller closure, D1 projection recovery, D2 capacity/elapsed soak and D3
fenced whole-Goal cutover remain separate work.

## Agent-addressed reads

`todo list --agent-id` now composes selection in the same typed summary batch,
sharing scope rules with quota. For User gates, explicit `global_gate` wins,
then `blocks_agent`, then the retained `claimed_by` fallback. User actions use
`bound_agent` first and retained `claimed_by` second. Unscoped records remain
visible. Gate addressing is independent of executor exclusion: an Agent cannot
ignore an explicitly addressed human gate because another Agent owns it.
Agent work still filters by claim and exclusions. A visible row grants no
mutation or execution permission; quota retains its additional eligibility rules.

This intentionally removes other-Agent, claim-only User records from scoped
lists; the old Python list rule ignored their claim while quota honored it.
Unfiltered Goal views retain those records. There is no feature flag or provider
default change. Existing frontend/Lark manager views use the unfiltered Core
read and continue to show the whole Goal; no new configuration editor is needed.

Resume and succession are evaluated on the complete source before selection.
The typed batch filters rows without renumbering their original source indexes,
then builds lanes/counts, and only then applies display limits. Status/identity
filters do not recompute dependencies from their smaller view. The v1 internal
request composes this selection into the existing call; v0 unfiltered callers
retain their wire contract. Python decodes legacy input and renders results,
with no independent Agent-addressing rule.

## 中文说明

`work_counts` 由完整来源计算，随后才裁剪展示。Agent quota 先按原有归属、排除、
能力与作用域规则筛选，再重新计数，不能沿用整个 Goal 的数量。`open` 包含 blocked
任务；`advancement` 才是已观察到的可执行推进任务。Monitor 是否到期仍使用独立字段。

`hidden` 表示未取得、无法分类的来源行，不是界面折叠的行数。`complete=false` 时，
已分类数量只是下界，重复投影也不能把未知变成完整，更不能据此声称“只剩 Monitor”。
旧摘要按 Todo 身份去重，矛盾片段不能证明完整；缺失任务不再被猜成 advancement。

TS 统一批量 lane 分类与计数，Python 保留旧格式解码、时间适配和展示。返回数组位置
索引减少同一任务在多个 lane 的重复传输；一个批次使用同一观察时刻。排序、延期与
完成计数约定、claim 展示保留。canonical `todo list` 同时修复了漏传同版本 acceptance
限制的问题，验收受阻的任务仍可见，但不会被列为可执行。

这不改变 provider 默认值，不授予执行权限，不写回 Markdown 或 canonical 状态。
新增计数字段不进入持久化 Todo；回滚无需数据迁移。默认切换、存量迁移、D1–D3 和旧
Python writer 退出仍有各自的验收条件，不能按本 PR 合并数量推定完成。

Agent 定向列表现与 quota 共用 TS 范围规则：User gate 按 global_gate → blocks_agent →
旧 claimed_by 依次判定，User action 按 bound_agent → 旧 claimed_by 判定。无作用域的
旧记录仍可见；显式人类 gate 不会被执行者 claim/exclusion 消除。Agent 工作仍按
claim/exclusion 筛选，可见不代表获准执行。

这是有意纠正：旧列表忽略仅声明 claimed_by 的 User 记录，导致其他 Agent 的工作混入
当前列表。未筛选的整 Goal 视图仍显示这些记录。依赖和 succession 先在完整来源求值，
TS 再筛选并保留原数组位置，最后生成 lanes、计数和有界展示；筛选后的数组位置不是原
来源位置。无需新增 capability、配置、前端或 Lark 编辑入口，不增加一次筛选 RPC。
