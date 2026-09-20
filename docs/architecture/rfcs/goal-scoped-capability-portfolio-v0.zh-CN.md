# RFC：Goal 级能力组合与 Connector 生命周期（v0）

- **RFC 状态：** Draft
- **交付成熟度：** Proposal；现有目录、hook 与外部证据切片只是部分前置
- **作者 / Owner：** LoopX capability 与 control-plane 维护者
- **创建时间：** 2026-09-21
- **最近一次规范修订：** 2026-09-21
- **实现基线：** `0ef7ebd749ec97a698a8fc7f2a29844dd368689b`
- **相关契约：** [总路线图](loopx-overall-roadmap-v0.zh-CN.md)、
  [研究探索](research-exploration-control-plane-v0.zh-CN.md)、
  [Agent Loop Effect](agent-loop-effect-interpreter-v0.zh-CN.md)、
  [结果后 Memory 效果归因](post-outcome-memory-utility-attribution-v0.zh-CN.md)、
  [Extension 参考](../../reference/extensions.md)以及
  [外部证据生命周期 PR #4813](https://github.com/loopx-project/loopx/pull/4813)
- **语言镜像：** [English](goal-scoped-capability-portfolio-v0.md)

## 文档结构与维护约定

第 1–10 节是长期设计和验收契约，第 11 节是规范性交付计划，第 12
节是未决问题。附录只记录非规范性证据和历史。RFC 成熟度与交付成熟度
相互独立。中英文是语义镜像，规范内容必须同步修改。

---

## 1. 决策摘要

LoopX 将新增 **Goal 级 Capability Portfolio**，让 Agent 围绕 Goal 的结果
和验收缺口，判断、选择、组合、评估、降级和退役能力。Portfolio 拥有
采用决策和效果回执，但不会把能力配置、provider 状态、证据、Todo、
授权或 memory 再复制成一份真相。

Portfolio 组合现有 owner：

1. capability catalog 描述可考虑的能力；
2. 原配置和 provider owner 证明生效 revision；
3. `agent_context` 在 `before_plan` 投影有界规划，在 `before_delegate`
   冻结选中路线，在 `after_delegate_result` 返回 typed 结果；
4. external-evidence 生命周期负责稳定研究方法和 connector 的资格认定；
5. Decision Context、Explore 与 reward memory 仍是有自己准入规则的下游。

默认是建议态并 fail-open。Portfolio 不可用时，普通工作仍应继续；只有
选中 Todo 明确要求缺失能力时，才由已有 capability admission 阻断。
自发现可以在已有授权内建议或运行有界 trial，但不能安装软件、启用
provider、扩大 network/write scope、修改模型授权或批准 protected effect。

本 RFC 不批准自动安装能力、connector 市场、Core 内的垂域排序或金融
执行权限。

## 2. 问题与动机

LoopX 已有 catalog、extension、readiness、Goal/Todo capability 要求、三个
Agent-context hook、external-evidence 规划、Explore、Decision Context 和
reward memory。但一个新 Agent 仍需自行猜测这些部件如何组合。当前缺失
的组织逻辑常由垂域 prompt 或本地策略文档补齐，导致采用理由不能跨
session 保留，换一个 Agent 又会重复探索、选择重复来源，或把 provider
ready 错当成证据质量。

Connector 存在同一问题。现有 registry 是有价值的库存和使用遥测；注册、
ready 和调用次数不能证明来源覆盖、时效、rights、真实执行、父 Agent
准入或决策价值。稳定来源应经过发现和有界 trial 才晋升，并在失效、
过期、成本过高或长期无效时降级或退役。

具体例子：一个投研 Goal 需要最新一手证据、独立反证和 read-heavy worker。
Agent 应能发现已有 external-research 方法、一个 qualified source connector
和一条可用 worker route；解释各自的选择理由；冻结 revision 和预算；记录
部分覆盖与失败；最后说明结果是否改变决策。目前这些事实分散在多个
projection 与说明文字里。

### 不变量

- Portfolio 采用永远不能新增或扩大授权。
- 配置仍归原 owner；Portfolio 只保存精确引用、digest 与有界 readback。
- `ready`、`executed`、`read`、`admitted`、`decision-changing`、
  `domain-eligible` 必须彼此区分。
- 同一来源被多个 connector 或 worker 读取，不能算独立证据。
- unknown、stale、partial、unavailable 必须显式；空结果不是完整覆盖。
- 模型回复、tool call、commit 或 connector 调用本身不是效果证据。
- replay 幂等；revision 漂移不能静默复用旧计划。
- CLI、managed Turn、前端和 Lark 读取同一份公开投影。
- 功能关闭和 Portfolio 失败时保留现有 Agent 路径。

## 3. 范围与非目标

### 范围内

- provider-neutral 的 capability descriptor 引用与 Goal adoption record；
- 带明确选择/跳过理由的有界能力组合 DAG；
- trial、use、effect、degradation、retirement 回执；
- 建立在 external-evidence 生命周期之上的 connector qualification profile；
- 通过 `before_plan`、`before_delegate`、`after_delegate_result` 注入；
- exact effective-config 与 provider revision readback；
- CLI/前端/Lark 共享查看与反馈；
- 以 finance 和一个非金融旅程做资格验证。

### 非目标

- 替代 Goal、Todo、quota、claim、lease 或 shared-authority 状态；
- 复制 provider 凭据、原始来源正文或私有配置；
- 将 Decision Context、Explore 或 reward-memory 状态搬进 Portfolio；
- 发明跨不同能力的统一总分；
- 自动安装、授权、支付、发布、签名或交易；
- 把 Portfolio 推荐当成 runtime 或垂域授权；
- 要求每个 Turn 全量扫描全部已安装能力。

## 4. 当前系统契约

在实现基线上：

- capability catalog 与 extension manifest 描述 installed/enabled 实现、
  provider、hook、权限与 readiness；
- capability admission 与 capability memory 提供有界 Goal/provider 和宿主
  观察，但不授予权限；
- Todo capability gate 判断已知任务能否执行，不会从 Goal 缺口发现能力；
- `agent_context` 已支持三个 guidance-only、有界 phase；
- connector registry 保存库存和简单使用遥测，不负责来源资格；
- PR #4813 提议 typed discovery、plan、execution receipt observation、parent
  admission 和 retirement，并将 provider execution 留在 Core 外；
- Decision Context 拥有决策证据，Explore 拥有研究拓扑，reward memory
  拥有经过资格审查的可复用结果经验。

本 RFC 组合这些 owner。它不会让 #4813 自动达到 merge-ready，也不声称其
真实 provider 端到端验证已经交付。

## 5. 建议架构

### Owner 与权限

TypeScript control plane 拥有规范化、identity、合法状态迁移和公开 Portfolio
projection。TS 迁移期间 Python 仅保留 adapter。

Portfolio 只拥有：

- Goal 为什么考虑、trial、采用、降级或退役某项能力；
- 选中的组合和 exact revision；
- use/effect receipt 与复评触发条件。

它仅引用而不复制：catalog/extension 声明、生效配置、provider readiness、
Todo 要求、授权决策、external-evidence receipt，以及 Decision Context、
Explore、memory artifact id。

任何 chat、UI、connector、worker 或垂域 capability 都不能成为另一个
Portfolio writer。所有变更经过一个 typed reducer 和当前 Goal authority
provider。

### 状态模型与 schema

#### `capability_catalog_entry_v1`

这是现有 capability declaration 的规范化引用：

```text
capability_id, capability_revision, owner_ref
outcome_tags[], lifecycle_phases[]
input_schema_ref, output_schema_ref, receipt_schema_ref
provider_requirements[], connector_requirements[]
required_host_capabilities[], required_authority_scopes[]
privacy_class, cost_class, readiness_ref, fallback_ref
```

Portfolio 不编辑该记录。

#### `goal_capability_adoption_v1`

```text
goal_id, adoption_id, portfolio_revision
gap_ref, capability_id, capability_revision
status = candidate | trial | adopted | degraded | retired
reason, alternatives[], expected_effects[]
effective_config_ref, effective_config_revision, config_digest
trial_budget, trial_window, authority_refs[]
use_receipt_refs[], effect_receipt_refs[]
review_after, degradation_conditions[], retirement_conditions[]
created_at, updated_at
```

`gap_ref` 指向结果或验收缺口，不创建第二份 Todo。状态迁移要求 expected
current revision。字段省略表示保留；可选字段按字段定义显式 clear 语义。

#### `capability_composition_plan_v1`

```text
goal_id, todo_id?, turn_id?, composition_id, portfolio_revision
gap_refs[], nodes[], edges[], selected_at, expires_at
node: capability/provider/connector/worker/reducer 引用，
      phase、输入/输出 schema、exact revision、预算、
      所需授权、所需读写范围、disposition、reason
```

`composition_id` 是全部规范化决策字段的 canonical digest。图必须无环。
每个候选都有 `selected`、`skipped`、`unavailable` 或 `incompatible` 及理由。
计划是 guidance，不是执行授权。

#### `capability_use_receipt_v1`

```text
receipt_id, composition_id, node_id, phase
goal/todo/turn identity, exact provider/model/connector revision
started_at, completed_at, cost, latency
coverage, freshness, source_families[], typed_failures[]
output_digest, result_ref
parent_disposition = adopted | ignored | refuted | unknown
decision_effects[], next_lifecycle_proposal
```

对非证据能力，coverage 和 source family 可以显式为 `not_applicable`，不能
伪造。持久化成功、召回、质量合格和实际有用是四个不同事实。

### 命令与事件生命周期

```text
发现 Goal 缺口
  → 投影 catalog 候选
  → 预览 composition
  → 选择有界 trial 或已有 adoption
  → 读回 exact config/provider revision
  → before_delegate 冻结 route
  → after_delegate_result 观察 typed 结果
  → parent adopt / ignore / refute / unknown
  → 提出 keep / reconfigure / degrade / retire
```

变更 identity 为 `(goal_id, adoption_id, expected_revision, operation_id)`。
同一意图 replay 返回原 receipt；identity drift fail-closed。provider/config
revision 漂移使计划失效。丢失响应时先读回 receipt，再重试。

Portfolio 不可读取时，规划继续并报告 `coverage=unknown`。若 Todo 明确要求
缺失能力，由已有 capability admission 只阻断该 Todo；Portfolio 不得削弱它。

### Connector qualification profile

Connector 复用 external-evidence 生命周期，不建平行状态机：

```text
external-research discovery
  → connector candidate
  → bounded trial
  → parent qualification
  → active
  → degraded | retired
```

Connector descriptor 增加 source family、支持操作、coverage domain、发布/
观察时间语义、rights、cost、failure、fallback。call receipt 绑定 exact plan/
provider revision、source refs、coverage interval、freshness、rights snapshot、
cost、latency、failure 和 output digest。注册和 ready 仍只是库存事实。parent
qualification 与 finance evidence eligibility 或其他垂域准入继续分开。

### Runtime 注入

- **`before_plan`：** 投影当前 gap、有效 adoption、stale/unavailable 节点和
  最小有用组合；允许空选择。
- **`before_delegate`：** 冻结 worker/connector/provider revision、预算、
  schema、authority refs 和 composition digest。垂域只描述问题和验收标准；
  通用 delegation owner 控制容量、route 和 result receipt。
- **`after_delegate_result`：** 只消费 typed result receipt，记录 parent
  disposition、成本、覆盖和 decision effect。worker 原始回答不是 adoption
  receipt。

可选 Turn-start 摘要只包含 Portfolio revision、当前 gap、所选组合、stale/
unavailable 节点和下次复评触发条件。完整 catalog 和历史不进入 prompt。

## 6. 替代方案与选择

### 由垂域 skill 组织能力

适合早期实验，但会丢失跨 Agent 采用历史、重复 runtime discovery，并让每个
垂域重复实现失败与授权规则。垂域保留语义和验收，Portfolio 拥有通用组织。

### Connector registry 成为质量 owner

拒绝。Registry 是库存和遥测。来源质量与 parent admission 需要 exact call
证据、时间、覆盖、rights 和垂域规则。

### Decision Context 拥有能力规划

拒绝。Decision Context 组装决策证据，不能成为配置、provider 或授权 owner。

### 完全自动安装

v0 拒绝。它混淆推荐、配置和授权。Portfolio 可以通过现有 governed owner
提出安装/启用建议，但不能隐式执行。

## 7. 安全、隐私与兼容

- Portfolio 默认 advisory，不保存 secret 或原始私有 payload。
- 公共投影隐藏私有来源、账户和付费数据细节，同时保留 typed coverage/
  failure 事实。
- readiness observation 不能变成 durable grant；已有 authority 与 protected
  effect confirmation 继续有效。
- 混合版本 reader 保留 unknown field，拒绝不支持的语义收窄；revision
  mismatch 显式并阻断复用。
- connector rights 过期、revision stale 或执行歧义时进入 unknown/degraded，
  不能静默 active。
- source-family 去重避免多个 wrapper/worker 被算成独立证据。
- 功能关闭时保留现有 planning、delegation、evidence 路径。

## 8. 迁移与回滚

M0 在现有 owner 上增加只读 inspect。M1 在 default-off capability 后保存
candidate 和 trial。现有 registry 记录继续可读，但不批量晋升；connector
只有通过新 exact-revision qualification receipt 才 active。

按 Goal 推进 rollout。开放变更前，preflight 校验 Portfolio owner、authority
provider、配置引用和公开投影。回滚时关闭 Portfolio injection，保留 receipt
供审计；原 catalog、配置、证据和任务 owner 继续运行。v0 不做破坏性
registry migration。

## 9. 验证与验收

| 声明 | 测试或证据 | 必须结果 | 边界 / 排除项 |
| --- | --- | --- | --- |
| Portfolio 不授予权限 | mutation 与对抗 fixture | 扩权请求被拒绝，不写 grant | 不验证每个外部 provider |
| Plan 绑定 exact 语义 | 修改 gap/config/provider/route/budget/graph | digest mismatch fail-closed | 不证明 live execution |
| replay 幂等 | 丢响应与并发重试 fixture | 一次迁移、一份 receipt | provider side effect 仍归 provider |
| 失败保留有用工作 | Portfolio/provider unavailable fixture | 普通 Todo 继续且 coverage unknown；硬要求仅阻断该 Todo | 无 availability SLO |
| Connector 生命周期可审计 | discovery→trial→qualification→degrade→retire fixture | 每步 exact revision + typed reason | 垂域 eligibility 独立验证 |
| 自发现有用 | 新 finance 与非金融 Agent 只收到同一 Goal | 选出最小合理组合或解释空选择 | 两例不证明普遍 uplift |
| 组合改善结果 | 冻结 baseline 对比 Portfolio-assisted trial | 在申明成本内改善首次有效行动、覆盖或决策质量，保留失败 | 不自动生产晋升 |
| 三个 hook 一致 | before-plan/delegate/result 契约测试 | 同一 composition identity 和 route/result lineage | 排除原始模型质量 |
| 产品入口一致 | CLI、打包前端、Lark 验收 | 同 revision/status/reason/cost/coverage/failure | 各 transport 单独资格验证 |
| 垂域边界成立 | finance 与另一垂域 fixture | Core 不理解垂域，domain admission 独立 | 不授予交易权限 |

衡量首次有效行动、证据覆盖、stale/重复来源错误、人工介入、token/费用、
决策变化和 accepted outcome。安装能力数、调用数和输出字数不是成功指标。

## 10. 运维契约

Operator 可查看 Portfolio revision、active/trial/degraded adoption、exact config/
provider revision、近期 typed failure、成本、覆盖和下次 review trigger。只对
revision drift、rights 过期、重复失败、预算耗尽或 required capability 不可用
产生事件提醒；日常成功调用不制造噪声。

每个 Goal/Turn 的容量有界，候选分页，prompt projection 有大小限制。failure
class 区分 unavailable、incompatible、unauthorized、stale、rights-expired、
budget-exhausted、provider-failed、result-unqualified。备份恢复跟随所选 Goal
authority provider，原 provider artifact 跟随原 owner。

## 11. 规范性交付计划

| 里程碑 | 交付行为 | 入口条件 | 退出证据 | 回滚 |
| --- | --- | --- | --- | --- |
| M0 · 契约与 inspect | 四个 schema；在现有 owner 上提供只读 `portfolio inspect/plan` | RFC 评审；明确 catalog/config owner | normalization、mutation、feature-off fixture | 删除投影，不落状态 |
| M1 · 外部证据与 connector trial | #4813 与 connector descriptor/call receipt 对齐，不自动晋升 | exact-plan binding 与 provider boundary 通过 | 一个真实 host method + 一个 connector trial，含 partial/failure receipt | 保留 registry；关闭 qualification write |
| M2 · Goal adoption owner | candidate/trial/adopted/degraded/retired reducer 与 receipt | Goal authority provider 可用 | replay、并发、drift、rollback、recovery 测试 | 关闭 writer，receipt 只读保留 |
| M3 · 三阶段组合 | 三个 Agent-context hook 投影 Portfolio，并接通通用 delegation receipt | M0–M2 identity 稳定 | 无额外提示的新 finance/非金融 Agent trial | 可独立关闭各 hook |
| M4 · 效果资格 | external-only/connector-only/hybrid 实验与 use/effect review、retirement proposal | 冻结指标、预算、stop rule | 完整分母证明收益或明确 no-uplift | adoption 退回 candidate/degraded |
| M5 · 产品旅程 | CLI、打包前端、Lark 共用 inspect/reason/readback/recovery | public projection 稳定 | 跨 session、stale、重连、重复动作验收 | 隐藏变更控件，保留 CLI readback |

RFC 仍为 Draft 时里程碑也可交付。#4813 是 M1 前置，不是整个 Portfolio 的
完成证据。overall-roadmap owner 维护 S8 顺序，canonical Todo 维护执行状态。

## 12. 未决问题

1. **Portfolio storage profile。** Owner：shared-authority 与 capability
   维护者。建议 adoption record 使用当前 Goal authority provider，大 receipt/
   artifact 留在原 owner。M2 前决定。
2. **跨能力比较。** Owner：capability 维护者。建议只在一个明确 Goal gap 内
   多维比较，不产生全局总分。M3/M4 验证。
3. **自动降级阈值。** Owner：capability + domain owner。建议自动提出 proposal，
   只有 typed policy 才应用；不能只因调用少而退役。M4 前决定。
4. **安装建议 UX。** Owner：产品和 extension 维护者。建议 M3 证明选择价值后
   才展示 governed repair/install proposal；它不属于 v0 执行权限。

---

## 附录 A：执行台账（非规范）

### 2026-09-21 — 调研与契约整合

- **基线：** `0ef7ebd749ec97a698a8fc7f2a29844dd368689b`；检查 PR #4813
  `491c0bf3ccd4804091d7611bd85d73f5f466fdd9`。
- **已交付：** 仅 RFC 契约。
- **证据：** 对 catalog、connector registry、capability admission/memory、
  Agent-context hook、Decision Context、Explore、reward memory 和 external-
  evidence proposal 的仓库审计；一次 finance connector inventory/use dogfood
  影响了生命周期设计，但不是公开 qualification evidence。
- **已知缺口：** 无 canonical Portfolio reducer、前端/Lark projection 和双垂域
  效果实验。
- **对规范设计影响：** 初始提案。

## 附录 B：决策日志

| 日期 | 决策 | Owner / 批准 | 替代项 | 修改的规范章节 |
| --- | --- | --- | --- | --- |
| 2026-09-21 | 初始提案，不从实现或沉默推断批准 | 待维护者评审 | 垂域组织、registry 质量 owner、Decision Context owner | 全部 |

## 附录 C：证据登记

| 证据 id | 声明 | 基线 / 环境 | artifact 或命令 | 结果 | 隐私 / 有效性边界 |
| --- | --- | --- | --- | --- | --- |
| E1 | 三个通用 hook phase 已存在 | 实现基线 | `agent_context`/subagent-context 源码与测试 | 已检查 | 静态检查，不证明 live uplift |
| E2 | Registry 是库存/遥测，不是 qualification | 实现基线 | connector-registry schema/CLI | 已检查 | 非穷尽 provider 审计 |
| E3 | external-evidence typed lifecycle 是活跃前置 | PR #4813 exact head | PR diff、测试与 review | open，未上 `main` | 不声明 merge/live provider |

## 附录 D：拒绝或替代方案

第 6 节方案继续保持拒绝，除非新证据证明它们能用更少状态实现同等产品
清晰度并保持所有不变量。

## 附录 E：事故与评审经验

- 能力 installed 或 worker route 被投影，不代表 real call 可以执行。每个
  composition plan 都要 exact authority/readiness readback。
- 成功持久化或 memory exact readback 不代表经验改变未来行为。use 与 effect
  qualification 必须分开。
