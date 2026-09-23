# Goal 实例身份与孤儿状态恢复（v0）

- **RFC 状态：** Draft
- **交付成熟度：** Proposal
- **作者／Owner：** LoopX contributors
- **创建日期：** 2026-09-23
- **最后规范修订：** 2026-09-23
- **实现基线：** `d3dc4083c9c73911addeae8c0643640f0046874b`
- **相关契约：** [Issue #4801](https://github.com/loopx-project/loopx/issues/4801)、[orphan fence 切片 #4808](https://github.com/loopx-project/loopx/pull/4808)
- **语言镜像：** [英文语义镜像](goal-instance-identity-and-orphan-recovery-v0.md)

## 文档地图与维护契约

第 1-10 节是长期设计与验收契约，第 11 节是规范性交付计划，第 12
节记录未决事项；其中的建议不等同于批准。附录只记录非规范性证据和决策历史。

中英文文档互为语义镜像。任何规范性变更都必须在同一个 PR 中同步修改两份文档。

---

## 1. 决策摘要

本 RFC 共同作出五项决策：

1. `goal_id` 保留为面向人的别名。由项目 registry 拥有且不可变的
   `goal_instance_id` 标识一次 Goal 生命周期。
2. 每个持久 host、session、channel、automation、Turn 和 quota binding
   都携带精确二元组。只有源项目 registry 可以授权执行；全局投影和 binding
   store 都不能授权。
3. 只有启用严格项目 registry envelope 后才能启用实例身份。已发布的旧二进制
   无法把该 envelope 解码为 registry，这构成 mixed-writer 的机械门禁。
4. 孤儿恢复是一个 preview-first、有 journal 的生命周期操作。操作者必须对每个
   candidate 明确选择 `adopt`、`migrate`、`archive` 或 `delete`，系统不得猜测
   或合并。
5. Legacy registry 和 binding 仍可检查、备份和迁移；在最终 enforcement
   版本中只能读取，不能激活 host、恢复 session、投递 channel、唤醒
   automation、修改 Goal 状态或消费 quota。

现有 state-file 位置、host 专属 runtime 目录布局、provider revision、
Lease 和全局 registry 的角色都不会成为新的 Goal authority。本 RFC 不批准
自动清理所有外部 provider、自动选择 candidate，也不允许普通 bootstrap
直接修改孤儿状态。

## 2. 问题与动机

当前 `goal_id` 同时承担展示名称和持久身份。Goal 可能已从项目 registry
消失，但 active-state 文件、session、host binding、Goal Channel 和 heartbeat
automation 仍然存在。之后创建同名 Goal 时，这些旧记录可能被误认为当前记录。
这是典型的 ABA 问题：

1. 名为 `release` 的 Goal A 创建了持久 attachment。
2. Goal A 被删除，但部分 attachment 仍存在。
3. 系统创建了同名 Goal B。
4. 只保存 `release` 的 attachment 无法区分 A 和 B。

#4808 已交付的 fence 会在 registry 中不存在 Goal、但项目中仍有状态 candidate
时阻止 guided bootstrap。它仍无法区分 Goal 生命周期、解决 orphan，也无法在
删除后同名重建时让旧 attachment 失效。

任何单独 host 或 session store 都无法局部解决该问题。若 host 自行生成身份，
它就成为第二个 Goal authority；若删除流程同步理解所有 provider，它就变成跨
owner 的分布式清理事务。LoopX 需要的是一个承载 authority 的身份，以及在每个
effect 边界对源 registry 的最终检查。

### 不变量

1. 只有源项目 registry 可以创建或解析 Goal instance。
2. Goal 终局删除后重新创建时必须获得新的随机 instance ID，即使复用了
   `goal_id`、路径、objective 或配置。
3. 配置更新、provider 重连、Lease 续期、新 Turn 或 binding 改写都不能轮换
   instance ID。
4. stale、缺失、畸形或 legacy binding 不能为 instance-aware Goal 授权执行。
5. stale 全局投影可以辅助路由，但不能授权写入。
6. 未完成的 orphan-resolution journal 必须阻止所有 Goal 激活与修改，即使项目
   Goal 记录已经发布。
7. resolution 最终只能留下一个被选择的可写状态 authority，或保持 Goal
   缺失且没有可写 candidate。
8. 破坏性 resolution 必须具备已验证的定向备份、精确 plan digest、显式 Goal
   确认和写后回读。
9. crash retry 必须复用 prepared instance ID 和 provider idempotency key。
10. 已发布的旧 writer 不能静默打开或改写 instance-aware 项目 registry。

## 3. 范围与非目标

### 范围内

- 项目 registry 所有的 Goal 生命周期身份和精确 binding 比较。
- 面向旧 reader/writer 的 registry 级兼容边界。
- 在所有第一方持久 binding owner 中传播 instance。
- 在激活、恢复、投递、状态修改和 quota 授权处做最终检查。
- 项目本地 orphan state 的 preview、backup、apply、resume 和 rollback。
- orphan state、legacy identity、stale binding、stale 全局投影、未完成 journal
  和人工清理的诊断。
- 将 observation 与 enforcement 分离的分阶段迁移。

### 非目标

- 改变面向人的 `goal_id`，或把 instance ID 放进 state path。
- 迁移 Codex、Pi、OpenCode 或其他 host 的底层 runtime 目录。
- 合并多个 active-state candidate。
- 将 timestamp、路径、内容相等、全局投影或 host 记录当作身份依据。
- 把外部 provider 的物理删除作为安全边界。
- 引入公开、通用的 binding-provider 框架。
- 改变 Claim、Lease、authority revision、Turn 或 provider idempotency
  语义；它们只新增 Goal instance 绑定。
- 允许旧二进制降级或编辑严格 registry。

## 4. 当前系统契约

以下是指定基线上的实现事实，不是提议行为：

- `loopx/bootstrap.py` 按 `id` 构造和合并 Goal 记录。强制合并可能替换完整
  Goal 记录。
- `loopx/registry.py` 和 `loopx/history.py` 接受任意 JSON object 作为
  registry，不拒绝未知 `schema_version`。
- 项目 registry 通常位于 `.loopx/registry.json`；全局 registry 条目携带
  `source_registry`，属于同步投影。
- `loopx/control_plane/goals/orphaned_goal_state.py` 发现当前和 legacy
  state candidate，并提供 #4808 的只读 bootstrap fence。
- `loopx/state_backup.py` 拥有现有 backup 格式和验证机制。
- Goal 删除与 host/session/channel 数据分别由不同 owner 管理。从 registry
  删除 Goal 不能证明所有 attachment 都已物理删除。
- 当前 Goal attachment 通常绑定 `goal_id`、路径、session ID 或 store 专属
  revision，没有任何字段标识一次同名 Goal 生命周期。
- 当前 registry loader 对 object 的宽松解析意味着：新增 capability 字段或
  告警无法阻止已发布旧二进制继续写入。

因此，本 RFC 把 mixed-writer 排除定义为 storage-format 要求，而不是诊断建议。

## 5. 提议架构

### 5.1 Ownership 与 authority

源项目 registry 拥有 Goal identity。只有在持有现有 registry mutation lock
并提交全新 Goal 记录时，它才能生成 `goal_instance_id`。全局 registry 只复制
该身份并继续作为路由投影。

`loopx/control_plane/goals/identity.py` 负责纯解析和比较，不得生成或持久化
ID。当前 storage owner 继续持久化和校验自己的 binding。
`orphaned_goal_state.py` 继续负责只读 discovery 和 fence。新的
`loopx/control_plane/goals/orphaned_goal_state_resolution.py` 负责
resolution policy、journaling、recovery 和 receipt，同时把文件备份、registry
修改和 owner 本地清理委托给现有 owner。

任何 binding 记录、host 状态、timestamp、state-file 路径或全局 registry
条目都不得创建、推断、修复或覆盖 Goal identity。

### 5.2 Goal identity 模型

`goal_instance_id` 是 opaque、immutable、public-safe 的非凭证字段。规范格式
为 `ginst_` 加 32 个小写十六进制字符，包含 128 个随机 bit。

```python
from dataclasses import dataclass
from typing import Literal, NewType

GoalId = NewType("GoalId", str)
GoalInstanceId = NewType("GoalInstanceId", str)


@dataclass(frozen=True, slots=True)
class GoalRef:
    goal_id: GoalId
    goal_instance_id: GoalInstanceId


@dataclass(frozen=True, slots=True)
class LegacyGoalRef:
    goal_id: GoalId


RegisteredGoalRef = GoalRef | LegacyGoalRef


@dataclass(frozen=True, slots=True)
class BindingMatch:
    decision: Literal[
        "current",
        "legacy_read_only",
        "missing_goal_instance_id",
        "goal_instance_mismatch",
        "goal_not_registered",
        "resolution_in_progress",
        "invalid",
    ]
```

Instance-aware Goal 记录包含：

```json
{
  "id": "release-2026",
  "goal_instance_id": "ginst_6ff38d6d143d4b72a6ff894b95f067c1",
  "status": "active",
  "repo": "/project",
  "state_file": ".codex/goals/release-2026/ACTIVE_GOAL_STATE.md"
}
```

上面的绝对路径只作说明，并非公开证据。持久路径继续遵守现有隐私和可移植性规则。

每个持久 attachment 保存：

```json
{
  "goal_id": "release-2026",
  "goal_instance_id": "ginst_6ff38d6d143d4b72a6ff894b95f067c1"
}
```

匹配矩阵必须穷尽：

| Registry 状态 | Binding 状态 | 只读检查 | 执行或修改 |
| --- | --- | ---: | ---: |
| 精确 instance | 完全相同的 instance | 允许 | 最终源检查后允许 |
| 精确 instance | 缺失 instance | 带 finding 允许 | 拒绝 |
| 精确 instance | 不同 instance | 带 finding 允许 | 拒绝 |
| Legacy Goal | Legacy binding | 带 finding 允许 | enforcement 版本拒绝 |
| Legacy Goal | Instance binding | 带 finding 允许 | 拒绝 |
| Goal 缺失 | 任意 binding | 作为历史记录允许 | 拒绝 |
| Resolution 未完成 | 任意 binding | 带 finding 允许 | 拒绝 |
| 记录非法 | 任意 | fail closed | 拒绝 |

较早的 observation 版本可以报告 legacy execution 而不拦截，但不能声称已满足
ABA 不变量。Enforcement 版本不保留 `legacy_compatible` 执行分支。

### 5.3 身份独立性

以下 revision domain 相互独立：

| 事件或身份 | 是否轮换 `goal_instance_id` | 原因 |
| --- | ---: | --- |
| 终局退休后重新创建 | 是 | 开始新的 Goal 生命周期 |
| 创建 Goal 的 orphan `adopt` 或 `migrate` | 是 | 建立新的 authority |
| 强制 bootstrap 或配置更新 | 否 | 修改同一生命周期内的配置 |
| Provider 重连或 provider revision | 否 | 修改 attachment 或 backend generation |
| Authority revision 或 migration receipt | 否 | 版本化 authority state，而非 Goal 存在性 |
| Claim 或 Lease epoch | 否 | 协调同一生命周期内的工作 |
| 新 Turn 或 session | 否 | 在同一生命周期中创建执行 lineage |
| Binding revision | 否 | 版本化单个 owner 的 attachment |
| 全局 registry 同步 | 否 | 复制源拥有的 identity |
| 回滚到 orphan bytes | 永不恢复 | 恢复的 bytes 没有执行 authority |

`--force` 不能替换 instance ID。导入到新的项目 authority 时必须生成新 identity，
不得复制由另一个 registry 拥有的 identity。

### 5.4 严格 registry envelope 与 mixed-writer 门禁

Instance identity 按项目 registry 激活，而不是按单个 Goal 激活。激活后的
registry 继续使用原路径，但 JSON 根从 legacy object 改为严格的双元素 array
envelope：

```json
[
  {
    "schema_version": "loopx_project_registry_envelope_v1",
    "minimum_writer_protocol": "goal_instance_v1",
    "payload_sha256": "sha256:..."
  },
  {
    "schema_version": "0.1",
    "goals": []
  }
]
```

该形状有意与已发布 legacy loader 不兼容；旧 loader 要求 JSON 根必须是
object，因此会在选择 Goal 或执行 registry-backed mutation 前失败。禁止只给
object 增加字段，因为旧代码会忽略该字段。

新代码只能通过统一 registry codec 打开两种格式：

```python
@dataclass(frozen=True, slots=True)
class OpenedProjectRegistry:
    format: Literal["legacy_object_v0", "strict_envelope_v1"]
    payload: dict[str, object]
    writer_protocol: str | None
    payload_sha256: str


def open_project_registry(path: Path) -> OpenedProjectRegistry: ...


def mutate_project_registry(
    path: Path,
    operation: str,
    reducer: Callable[[OpenedProjectRegistry], ProjectRegistryMutation],
) -> ProjectRegistryReceipt: ...
```

Transaction API 负责保留 envelope、验证 payload digest 和原子写回。M0 后禁止
直接写项目 registry。仓库检查维护完整的项目 registry writer 清单；新增绕过
路径时必须失败。

激活采用 preview-first，并作用于整个 registry：

```console
loopx activate-goal-instance-identity --project . --format json

loopx activate-goal-instance-identity \
  --project . \
  --execute \
  --plan-revision sha256:31ab... \
  --confirm-registry-path .loopx/registry.json
```

Apply 必须满足：

1. registry 中任何 Goal 都不存在活跃 host、session、automation 或 Goal
   mutation lease；
2. legacy object 和受影响本地 binding 已完成并验证备份；
3. 所有已安装第一方 host 都声明 `goal_instance_v1`；
4. 所有当前 Goal 在同一次原子 envelope 写入中获得新 instance ID；
5. 所有 legacy binding 在显式重建前均不可执行；
6. 新 codec 回读成功，并且 oldest supported released writer 的黑盒拒绝测试通过。

新建空项目可以直接使用严格 envelope。已有 legacy registry 在全局激活成功前
不能生成任何 instance ID。空 legacy registry 上的 orphan `adopt` 或 `migrate`
可以在同一个 prepared transaction 中完成激活；若还有其他 legacy Goal，则必须
先完成 registry-wide activation。

全局 registry 继续使用 object 投影，因为它不是执行 authority。旧全局 writer
最多使投影 stale；所有可执行路径都必须回读严格源 registry。Status 报告 stale
投影，并由当前 writer 修复。

删除严格 registry、把 payload 手工提取成 legacy object，或绕过 envelope 编辑
都属于不受支持的人工破坏。本 threat model 防止第一方 mixed-version writer 的
意外写入，不防止同一操作系统主体蓄意篡改文件系统。

### 5.5 Binding owner 与最终检查

首个实现使用私有穷尽 owner 表，不提供公开插件接口：

| Owner | 持久 binding | 必须执行的最终检查 |
| --- | --- | --- |
| 项目 registry | session 和 thread binding | 返回可恢复 route 前 |
| Attached host | activation 和 lock identity | 创建 lock 或 execution request 前 |
| Chat store | Goal session 和 upstream thread | create、direct resume 或 latest lookup 前 |
| Turn driver | lineage 和 host session digest | queue 和 settlement 前 |
| Pi 和 OpenCode | 本地 authority/binding 记录 | host action 和 quota call 前 |
| Goal Channel / Lark | channel binding 和 connection | 入站或出站 delivery 前 |
| Heartbeat automation | installed command 和解析 inventory | wake 和 quota call 前 |
| Scheduler 和 quota | executable hint 和 spend request | Todo selection 和 spend 前 |

每条 inventory row 包含稳定 owner revision：

```python
@dataclass(frozen=True, slots=True)
class BindingObservation:
    owner: str
    locator: str
    binding_revision: str
    content_sha256: str
    observed_goal_ref: GoalRef | LegacyGoalRef | None
    cleanup_mode: Literal["local_idempotent", "external_unverified", "none"]
```

完整排序后的 inventory 和每个 `binding_revision` 都进入 migration 与
orphan-resolution plan digest。新增第一方持久 owner 时必须同步更新 owner 表和
穷尽性测试。

所有可执行路径遵守同一顺序：

1. 解析 route，必要时通过全局 registry。
2. 通过严格 codec 打开源项目 registry。
3. 拒绝 legacy Goal 或未完成 resolution journal。
4. 比较 registry 和调用方携带的精确 `GoalRef`。
5. 在该边界第一个 effect 之前立即重新验证。
6. 只有之后才能创建 lock、返回 resumable record、delivery、write 或 spend。

Host activation 检查不能替代 state writeback 或 quota spend 检查。长生命周期
进程可能跨越 Goal 的删除和重建。

### 5.6 Orphan resolution 命令

除非带 `--execute`，命令只做 dry run。每个发现的 candidate 都必须有明确
disposition：

```console
loopx resolve-orphaned-goal-state \
  --project . \
  --goal-id release-2026 \
  --disposition .codex/goals/release-2026/ACTIVE_GOAL_STATE.md=adopt \
  --disposition .claude/goals/release-2026/ACTIVE_GOAL_STATE.md=archive \
  --objective "Ship the release" \
  --domain engineering \
  --role owner \
  --format json
```

- `adopt` 保持一个选中 candidate 位于已经 canonical 的位置，并以新 Goal
  instance 注册。
- `migrate` 通过 canonical state-path helper 移动一个选中 candidate，在相同
  human Goal ID 下注册新 instance。
- `archive` 把 candidate 移出所有 active Goal root。
- `delete` 只有在定向 backup 验证后才删除 candidate。

最多一个 candidate 可以是 `adopt` 或 `migrate`；其余 candidate 必须是
`archive` 或 `delete`。只有 archive/delete 的计划让 Goal 保持缺失。系统不提供
隐式 winner、内容合并、任意 destination path 或重命名 target Goal。

Preview 在计算 digest 前验证：

- project 和 registry 位于声明的 authority boundary 内；
- 每个 candidate 是 allowed Goal root 内可读的 regular file；
- candidate 和 parent 都不是 symlink；
- resolved path 不 escape、alias 或互相重复；
- 请求的 Goal 不存在于项目 registry；
- 同一 Goal 不存在其他 resolution；
- 所有 candidate tree digest 和 binding-owner revision 稳定；
- migration destination 由 canonical path helper 选择；
- 需要创建 Goal 时，其 specification 完整。

执行必须绑定 preview 和人工意图：

```console
loopx resolve-orphaned-goal-state \
  --project . \
  --goal-id release-2026 \
  --disposition .codex/goals/release-2026/ACTIVE_GOAL_STATE.md=adopt \
  --disposition .claude/goals/release-2026/ACTIVE_GOAL_STATE.md=archive \
  --objective "Ship the release" \
  --domain engineering \
  --role owner \
  --execute \
  --plan-revision sha256:82e3... \
  --confirm-goal-id release-2026
```

### 5.7 Resolution transaction 与 journal

Journal 位于
`.loopx/lifecycle/orphaned-goal-state/<goal-id>/<plan-revision>.json`。它是
lifecycle metadata，不是第二个 Goal registry。

Apply transaction：

1. 按一个文档化顺序获取 lifecycle、registry 和受影响 owner lock。
2. 完全相同的 replay 直接返回已有 complete receipt。
3. 重建 plan，并要求 registry、candidate、owner、Goal specification 和
   plan digest 完全一致。
4. 通过 `state_backup.py` 写入并验证一个定向 backup。
5. 若将创建 Goal，则生成 instance ID，并在首次 candidate mutation 前把它
   持久写入 `prepared` journal。
6. 幂等应用 candidate disposition，并记录每一步；archive destination 包含
   plan revision。
7. 只有选中 candidate 到达 planned canonical route 且所有竞争 candidate
   都失活后，才能发布项目 Goal。
8. 使用精确 retired `(goal_id, goal_instance_id)` selector 和稳定 idempotency
   key 请求 owner 本地 revocation。
9. 把项目记录同步到全局投影。
10. 回读所有 candidate、owner receipt、registry、全局投影、backup proof 和最终
    orphan fence 后，才能把 journal 标记为 complete。

Prepared 或 incomplete journal 会阻止全部 activation 和 mutation，即使步骤 7
已经发布项目 Goal。Retry 必须复用 journal 中的 instance ID、resolution ID、
owner selector 和 provider idempotency key。

Completion receipt 包含：

- plan revision、resolution ID 和 terminal journal digest；
- 每个 candidate 操作前后的 digest；
- 源项目 registry digest 和精确 Goal reference；
- 全局投影结果与 digest，或 typed pending-sync finding；
- 与路径无关的 backup manifest digest 和验证证明；
- 每个 binding-owner observation、revision、cleanup request 和 readback；
- 每个本地 removal receipt；
- 每个外部 `manual_cleanup_required` finding；
- 最终 orphan fence 和 in-progress fence 结果。

### 5.8 逻辑 revocation 与 owner cleanup

精确 instance mismatch 是安全边界。Resolution 不依赖所有 store 的物理删除。

Revocation selector 必须始终包含完整 retired pair：

```python
@dataclass(frozen=True, slots=True)
class RevocationSelector:
    goal_id: GoalId
    retired_goal_instance_id: GoalInstanceId
```

禁止只按 Goal ID 清理，因为它可能删除刚创建的新 instance。支持幂等删除的本地
owner 必须先返回 receipt，resolution 才能完成。无法验证删除结果的外部 provider
保持逻辑 inert，并产生 `manual_cleanup_required`；该 finding 不会让 stale
execution 重新变得可能。

### 5.9 Rollback

Rollback 同样采用 preview-first，并绑定 digest：

```console
loopx rollback-orphaned-goal-resolution \
  --project . \
  --goal-id release-2026 \
  --resolution-id ores_... \
  --format json

loopx rollback-orphaned-goal-resolution \
  --project . \
  --goal-id release-2026 \
  --resolution-id ores_... \
  --execute \
  --plan-revision sha256:... \
  --confirm-goal-id release-2026
```

Rollback 只能把已验证 bytes 恢复到 orphaned、fenced 状态，不能恢复 retired
Goal instance ID 或 binding authority。在任何 resolution 后 Goal write、Todo
mutation、quota spend、session/channel 创建、automation 安装或 binding revision
发生后，rollback 必须拒绝。成功 rollback 通过 lifecycle owner 删除新 Goal，
恢复 candidate bytes，验证 digest，并让 diagnose 重新以
`orphaned_goal_state` 报告 unhealthy。

若 rollback 已不合法，恢复只能向前执行：完成 journal，通过普通 lifecycle
退休新 Goal，再创建新的 resolution plan。

### 5.10 模块地图

| 模块 | 职责 |
| --- | --- |
| `loopx/control_plane/goals/identity.py` | Goal reference type、parser 和穷尽 match policy |
| `loopx/control_plane/projects/registry_codec.py` | Legacy object／strict envelope decode、digest 验证和保留格式的 transaction |
| `loopx/bootstrap.py` | 只在提交新建时生成 identity；更新时保留 identity |
| `loopx/global_registry.py` | 复制 identity、分类 instance replacement、永不生成 |
| `loopx/control_plane/goals/orphaned_goal_state.py` | Candidate discovery 和只读 fence |
| `loopx/control_plane/goals/orphaned_goal_state_resolution.py` | Plan、apply、journal recovery、revocation 编排、rollback |
| `loopx/state_backup.py` | 定向 backup plan、archive、manifest 和验证 |
| 现有 binding owner | 持久化二元组、校验二元组并执行 owner 本地 cleanup |
| `loopx/control_plane/goals/global_registry_health.py` | Typed health finding |
| `loopx/diagnose.py` | 展示 finding，不成为新的 detector 或 writer |
| CLI adapter | 只解析参数和渲染 typed result |

## 6. 替代方案与设计选择

### Generation counter

`goal_id` 下的 counter 需要在删除后永久保留 tombstone，或依赖第二个全局
allocator。源 registry 生成随机 identity 不需要这两项，也不要求 ID 有序。

### 在目录路径中加入 instance ID

Instance-segment path 可以隔离文件，却不能标识 session、channel、automation
或 quota call；同时会迫使所有面向人的路径 consumer 参与大范围迁移。记录级
identity 无需引入该无关布局变更即可修复已报告 ABA 问题。

### 删除 Goal 时清理所有 binding

跨 provider 删除不具备原子性，还会迫使 Goal lifecycle 理解所有 storage
实现。精确匹配先让 stale record 失活；owner 本地清理只改善卫生，不承担
authority。

### 给当前 registry object 增加 capability 字段

已发布的旧 loader 接受未知 object 字段和 schema value，因此仍可能静默改写
instance-aware registry，不满足 mixed-writer 不变量。

### 新 registry 路径加 redirect object

已发布的旧二进制可能忽略 redirect，继续写旧路径并形成 split authority。同一路径
上的不兼容根形状会产生确定性 decode failure。

### 自动选择或合并 candidate

路径优先级、修改时间和内容相等都不能证明 authority。多个 candidate 可能代表
分叉历史，必须由操作者逐个分类。

### 一个模块同时负责 discovery 和 mutation

把小型只读 fence 与 backup、journaling、cleanup、rollback 和 registry
publication 合并，会让稳定 detector 混入大型事务。独立 resolution owner
保留深的 plan/apply 接口，又不会把 fence 模块变成 lifecycle service。

## 7. 安全、隐私与兼容性

Identity 和 digest 是 public-safe metadata，不是凭证。Backup、candidate 内容、
session payload、本地绝对路径、provider handle 和原始状态属于 private runtime
data，不得进入公开 receipt、log、fixture 或文档。

Strict envelope 为受支持的第一方二进制提供 format-level split-brain 防护。
满足以下条件前不得激活：

- 仓库内所有项目 registry writer 都使用 codec transaction；
- 打包后的 Python 和 TypeScript surface 通过同一 writer inventory；
- 每个已安装第一方 host 都报告所需 protocol；
- 黑盒测试证明 oldest supported old package 拒绝 strict fixture 且 bytes
  不变；
- 当前代码证明精确 read/write/readback 和 crash safety。

Legacy object registry 仍可用于 status、diagnose、backup、activation preview
和 orphan-resolution preview。在 observation 版本中，它可以继续执行但必须明确
报告“不提供保障”；在 enforcement 版本中，它只能读取，直至 activation 完成。

Strict registry 不支持降级。当前代码无法满足 manifest 时，必须在修改前返回
`unsupported_registry_writer_protocol`。恢复必须使用当前或更高版本，不能为旧
writer 解包 payload。

源 registry 不可用、digest mismatch、envelope 畸形、instance 缺失、resolution
未完成或 owner inventory 歧义都必须 fail closed。全局投影不可用可能延迟可见性，
但不能授权执行。

## 8. 迁移与回滚

迁移有两个范围：

1. **新项目。** 创建严格空 envelope，并在首次 Goal 的 committed registry
   transaction 中生成 identity。
2. **已有项目。** Preview registry-wide activation，quiesce 每个 Goal，备份
   registry 和本地 binding，为所有当前 Goal 生成新 instance，原子写入严格
   envelope，并要求所有 attachment 显式重连。

不得自动认可任何现有 attachment。系统没有证据证明一条 unstamped record
属于当前生命周期，而不是更早的同名 Goal。

已验证 strict-envelope write 是 activation cutover point：

- 写入前，abort 让 legacy object 保持 authority。
- 写入后，旧二进制和 unstamped binding 均不受支持并 fail closed。
- 后续步骤失败时，当前代码恢复 activation journal。
- 恢复 legacy execution 不属于 rollback。

Orphan archive/delete 不创建 Goal，因此无需 identity activation。Orphan
adopt/migrate 必须使用已严格化 registry、新建严格 registry，或由同一 plan
准入原子 registry-wide activation。

Resolution prepare 前 abort 不改变任何状态。Prepare 后必须重试同一个 plan。
独立 rollback 命令仅在没有任何 resolution 后业务写入时合法，并只能恢复
orphaned、non-executable bytes。

## 9. 验证与验收

| 声明 | 测试或证据 | 必须结果 | 边界／排除项 |
| --- | --- | --- | --- |
| 同名重建被 fence | 删除 A，保留全部 attachment，以相同 alias 创建 B，遍历所有 owner | 所有旧路径在 effect 或 quota 前拒绝 | 不要求 provider 物理删除 |
| 更新保留生命周期 | 强制更新配置、provider 重连、Lease 续期、新 Turn | Registry 和新记录使用相同 instance ID | 不要求 binding revision 不变 |
| Legacy 只读 | 执行 status、backup、migration preview、activation、resume、delivery、write、spend | 读取带 finding 成功；所有 effect 拒绝 | Observation 版本明确更弱 |
| 旧 writer 被机械拒绝 | 用 oldest supported released package 操作 strict fixture | 非零 typed/decode failure，registry bytes 完全不变 | 覆盖受支持第一方 package，不覆盖任意脚本 |
| Strict codec 穷尽 | 静态 writer inventory 加 Python/TS conformance | 不存在项目 registry 直接写绕过 | 测试 helper 可使用隔离 fixture |
| 源 authority 胜过全局投影 | 制造 stale 全局条目，调用所有 executable route | 源 mismatch 拒绝 | 全局 routing availability 独立 |
| Preview 纯只读 | Preview 1、2、4 个 candidate | 不写 file、registry、binding 或 journal | 允许读取 filesystem metadata |
| Plan 绑定完整状态 | Preview 后修改 candidate、owner revision、registry 或 Goal spec | Apply 在 backup/mutation 前拒绝 | 无 |
| 路径校验 fail closed | Symlink、escape、重复路径、非 regular 或不可读 candidate | Preview/apply 拒绝 | 合法 destination 由 canonical helper 拥有 |
| Crash retry 幂等 | 在每个 journal step 后 crash | 单一 instance ID，无重复 archive/delete，owner key 相同 | 外部人工清理可保留 |
| 已发布但未完成仍被 fence | 项目发布后、全局同步／完成前 crash | Activation、mutation 和 quota 拒绝 | Status 仍可读 |
| Cleanup 失败仍安全 | 让一个本地和一个外部 owner cleanup 失败 | Instance mismatch 保持 inert；journal 重试本地 owner；外部 finding 保留 | 完成必须等待所需本地 receipt |
| Receipt 完整 | 对照 owner 表和全部 readback | 每个 owner/candidate/registry/global/backup/fence row 都存在 | 排除原始 private 内容 |
| 破坏前已有 backup | 在 backup 验证前后注入失败 | Proof 前不破坏；已验证 restore 可用 | Archive-only 仍做定向 backup |
| Rollback 被 fence | 分别在 resolution 后写入前后 rollback | 早期恢复 orphan fence；晚期拒绝 | 永不恢复旧 authority |
| 诊断持续 unhealthy | 构造 orphan、legacy、mismatch、stale global 和 incomplete journal | Typed finding 和精确 next action | Diagnose 不做 repair |

实现还必须运行现有 bootstrap、registry、deletion、session、host、Goal Channel、
heartbeat、quota、backup、docs-governance 和 public-safety suite。跳过任何 owner
row 都不算验收。

## 10. 运维契约

稳定 finding 包括：

- `orphaned_goal_state`
- `orphan_resolution_in_progress`
- `legacy_goal_identity`
- `goal_instance_id_missing`
- `goal_instance_mismatch`
- `goal_not_registered`
- `stale_global_goal_instance`
- `unsupported_registry_writer_protocol`
- `binding_owner_inventory_changed`
- `manual_cleanup_required`

每个 rejection 都应在 public-safe 前提下标识 source registry、Goal alias、
expected/observed instance、owner、retryability 和一个 lifecycle next action，
不得暴露 raw state、credential、本地 session 内容或 provider secret。

Status 和 diagnose 只读。它们可以检查 legacy registry、historical binding、
strict envelope 和 incomplete journal，不能 stamp identity、修复全局投影、选择
candidate 或完成 cleanup。

Lifecycle 按现有 backup retention policy 为每次 resolution 保留一个 verified
backup 和一个 terminal receipt。Incomplete journal 不得自动 GC。本地 cleanup
retry 必须幂等。External manual cleanup 只作提示，因为 logical revocation
已经阻止执行。

## 11. 规范性交付计划

| 里程碑 | 交付行为 | 入口门禁 | 退出证据 | 回滚 |
| --- | --- | --- | --- | --- |
| M0：registry codec 与 writer census | 双格式 read codec、保留 strict format 的 transaction、穷尽 writer inventory；不生成 identity | RFC review | 当前 suites、direct-writer ratchet、old-package strict-fixture rejection | 删除未使用 codec；全部 registry 仍是 legacy object |
| M1：observation 与 stamped binding | Identity type、owner inventory、附加 binding 字段、diagnostics；不 enforcement | M0 green | 跨 owner read/write fixture；legacy 行为明确标为不受保护 | 停止输出可选 binding 字段 |
| M2：activation 与 strict creation | Preview-first registry activation；新项目使用 strict envelope；只在 strict transaction 中生成 ID | M0/M1 green；host capability census | Quiescence、backup、old-writer denial、strict readback、update-preserves-ID 测试 | 只可在 envelope 写入前回退；之后向前修复 |
| M3：最终 enforcement | Legacy execution 只读；所有 owner 和 quota boundary 做精确最终源检查 | Migration guidance 已发布；executable caller inventory 完整 | ABA、stale global、long-lived process、missing-ID rejection matrix | 不降级；使用当前版本和迁移 |
| M4：orphan resolution | Preview、定向 backup、prepared journal、candidate disposition、owner cleanup、完整 receipt | M2/M3 identity boundary | Purity、path、crash-point、cleanup、receipt 验收行 | Resume 或 digest-bound rollback 到 fenced orphan state |
| M5：legacy cohort migration | 已有项目 registry-wide migration 和 host reconnection | M2-M4 运维证据 | 端到端 multi-Goal migration 和 diagnostics | Cutover 前 abort；之后向前修复 |

任何代码在 M0 前都不能生成 `goal_instance_id`。只要任何第一方可执行路径仍保留
legacy fallback，M3 就不能声称满足 ABA 保证。M4 可以先交付 archive/delete，
但不得创建 Goal 或削弱现有 fence。

## 12. 未决事项

1. **最低支持旧 package。** Release owner 在 M0 退出前决定。建议测试支持策略
   中最旧的版本以及紧邻前一版本；证据为黑盒 mutation matrix。
2. **Activation 命令名称和确认 token。** CLI owner 在 M2 前决定。建议使用本文
   所示 registry-wide `activate-goal-instance-identity`，因为 envelope 边界无法
   诚实地按单 Goal 激活。
3. **Canonical migration destination。** State-path owner 在 M4 前决定。建议
   使用 host-neutral path 工作提供的 canonical helper，不接受自由目标路径。
4. **全局同步终局语义。** Registry owner 在 M4 前决定。建议在全局投影回读
   成功前保持 `local_committed`，并由 incomplete journal 的源检查继续阻止执行。
5. **保留期限。** Operations owner 在 M4 前决定。建议复用当前 targeted-backup
   retention，并让 terminal receipt 的保留期不少于任一 owner 保留 stale binding
   的时间。

---

## 附录 A：执行记录（非规范性）

### 2026-09-23 — 设计综合

- **基线：** `d3dc4083c9c73911addeae8c0643640f0046874b`
- **已交付：** 仅 RFC 提案。
- **证据：** 已检查当前 registry、bootstrap、deletion、binding、orphan fence、
  backup、全局投影和文档契约。
- **已知缺口：** 尚无 runtime 实现或 acceptance fixture。
- **对规范设计的影响：** 初始提案。

## 附录 B：决策日志

| 日期 | 决策 | Owner／批准 | 替代方案 | 变更的规范章节 |
| --- | --- | --- | --- | --- |
| 2026-09-23 | 提议 source-owned 随机 Goal instance identity 与 strict registry envelope | 提案；等待 maintainer 批准 | Counter、path identity、附加 capability marker | 初始 RFC |
| 2026-09-23 | 提议显式 journaled orphan resolution 与 owner-local cleanup | 提案；等待 maintainer 批准 | 自动 merge、集中式 provider deletion | 初始 RFC |

## 附录 C：证据登记

| 证据 ID | 声明 | 基线／环境 | Artifact 或命令 | 结果 | 隐私／有效性边界 |
| --- | --- | --- | --- | --- | --- |
| E1 | 当前 loader 接受任意 object schema，并拒绝非 object 根 | 指定基线 | 检查 `loopx/registry.py`、`loopx/history.py`、`loopx/bootstrap.py` | observed | 静态当前代码事实 |
| E2 | 已交付 fence 阻止 orphan guided bootstrap，但不执行 resolution | 指定基线 | Issue #4801 和 PR #4808 | observed | 公开 issue 和代码范围 |
| E3 | 全局条目是 source projection | 指定基线 | 检查 `loopx/global_registry.py` | observed | 静态当前代码事实 |
| E4 | Strict envelope 拒绝 oldest supported old writer 且不修改状态 | 未来 M0 fixture | 已发布 package 黑盒测试 | unverified | 生成 identity 前必须完成 |
| E5 | 每个持久 binding owner 验证精确 identity | 未来 M1-M3 fixture | Owner inventory conformance suite | unverified | Enforcement 前必须完成 |
| E6 | Resolution 可在 crash 后安全恢复 | 未来 M4 fixture | Fault-injection 和 restore matrix | unverified | 破坏性使用前必须完成 |

## 附录 D：已拒绝或被替代的方案

- 只有 warning 的 writer capability marker 无法限制不理解 marker 的旧代码。
- Redirect object 让旧路径继续可写，允许 split authority。
- 全局 counter 会让 projection 成为 allocator，或要求永久 tombstone。
- 自动 binding upgrade 只能按 alias 猜测历史，因此禁止。
- 把全 provider cleanup 当作 commit precondition 会让 availability 耦合所有
  integration，且仍不能证明 external deletion。
- Runtime-directory migration 无法解决非文件 binding，并且超出 issue #4801。

## 附录 E：事故与评审经验

- 当前状态 healthy 不能证明它与更早的同名 Goal 连续。
- 若旧代码会忽略 compatibility check，advisory check 就不是 writer fence。
- Crash safety 要求首次移动 candidate 前持久化新 identity，并让 journal 本身
  成为 execution fence。
- Cleanup 与 authorization 是两个问题：stale record 可以保留用于 audit，同时
  由精确 identity matching 保持 inert。
