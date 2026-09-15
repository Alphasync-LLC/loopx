# RFC：语义词表收敛与提交期漂移检查（v0）

- **RFC status：** Draft
- **Delivery maturity：** Partial（M0 的注册表、生成清单与漂移 smoke 随本 RFC 一起交付）
- **Authors / owners：** LoopX 贡献者；控制面内核维护者拥有批准权
- **Created：** 2026-09-15
- **Last normative revision：** 2026-09-15
- **Implementation baseline：** `1dc6ad8d8`
- **Related contracts：** `loopx/semantics/vocabulary_v0.json`、
  `loopx/semantics/inventory_v0.json`、
  `loopx/control_plane/turn_transaction_contract.json`、
  `loopx/control_plane/coordination/coordination_state_contract_v0.json`、
  [Turn Envelope v0](../../reference/protocols/turn-envelope-v0.md)、
  [Turn Loop Controller v0](../../reference/protocols/turn-loop-controller-v0.md)、
  [TypeScript 控制面迁移 v0](typescript-control-plane-migration-v0.zh-CN.md)
- **Language mirror：** [English](https://github.com/huangruiteng/loopx/blob/main/docs/architecture/rfcs/semantic-vocabulary-convergence-v0.md)

## 文档地图与维护契约

本 RFC 同时交付英文版 `semantic-vocabulary-convergence-v0.md` 与本中文语义镜像；
两者互相链接，规范章节变更时必须同步修订。

- 第 1-10 节是持久的设计与验收契约。
- 第 11 节是规范性交付计划。
- 第 12 节是未决决策；建议答案不等于批准。
- 附录是非规范的执行账本、决策日志、证据登记与被否决方案。

RFC 成熟度与交付成熟度彼此独立。带日期的进度条目不修改规范章节。

---

## 1. 决策摘要

1. **什么成为权威。** `loopx/semantics/` 下的两份文件。策展注册表
   `vocabulary_v0.json` 为每个内核与跨运行时词表命名：允许定义它的确切
   `module::Symbol`、词表之间的关系（同一概念、共享字段名、子集）、完整投影，
   以及仓库同意只降不升的预算。生成清单 `inventory_v0.json` 映射 `loopx/` 下
   每一个闭集载体：字符串枚举、`Literal` 别名、命名闭集、TypeScript `as const`
   数组，以及在多个模块中定义的每个常量名。一支公共 smoke
   `examples/semantic-vocabulary-drift-smoke.py` 在每次 premerge 与 full-public
   运行时用两份文件核对代码。任何扩宽词表、分叉常量、新增载体或削弱注册表的
   改动，必须在同一个 diff 里修改注册表或重新生成清单，评审者因此能把语义
   变化当作变化看见。
2. **什么不变。** 运行时行为、线上格式、枚举类本身。每个枚举继续住在自己的
   owner 模块里；注册表通过 AST 与文本扫描核对代码，不生成代码，产品代码也
   永不导入它。
3. **默认与可选边界。** 检查对仓库始终开启。它没有运行时开关，因为它从不在
   产品内运行。
4. **主要约束。** 失败即关闭、确定性、且不能仅靠改数据被削弱。任一运行时的
   未注册字面量、第二个定义模块、预算超支、注册表列出但无模块携带的值、过期
   的清单、不带符号的 owner 声明、低于记录下限的覆盖计数，每一项都让 smoke
   失败。扫描识别的分发形式写在 smoke 里而不在注册表里。smoke 只读已跟踪
   源码，不打印任何私有数据。
5. **本 RFC 不批准的事。** 把三套 Turn 结果枚举合并为一套、拆分
   `effective_action` 的三个槽位、删除任何旧的 should-run 字段、删除任何
   Python 孪生模块、重命名任何现有值。这些属于后续里程碑，各自受 `AGENTS.md`
   中 schema 缩减规则的门控。

## 2. 问题与动机

LoopX 由大量小型 agent 驱动的 PR 生长而成。每个 PR 在需要之处加上它需要的
词汇。结果不是错误行为，而是漂移：同一概念多种拼法，同一常量在多个文件定义，
同一字段名承载不同词表，以及任何模块都可扩宽而无人察觉的开放字符串集合。
评审者无法从 diff 判断一个新字面量是新状态还是拼写错误，文档也无法跟上一个
没人枚举的集合。

语义面是全仓库的，不是 Turn 内核的局部问题。清单生成器在基线上扫描 `loopx/`
下 1169 个源文件得到：

| 载体 | 数量 | 说明 |
| --- | --- | --- |
| Python 字符串枚举 | 102 | 控制面 29、capabilities 17、extensions 6 |
| 命名闭集（`NAME = frozenset/tuple` 字符串） | 490 | 66 个是字段列表、31 kinds、31 states、29 statuses |
| `Literal[...]` 别名 | 8 | |
| TypeScript `as const` 数组 | 40 | 21 个有值集相等的 Python 侧；14 个没有 |
| 命名字符串常量 | 2002 | 754 个是 `*_SCHEMA_VERSION` |
| 同名同值、跨两个运行时 | 166 | 合法的 py/ts 孪生 |
| 同名同值、同一运行时 | 25 个名字 / 58 处定义 | 分叉；其中 7 个是 schema 版本 |
| 同名不同值 | 18 个名字 / 59 处定义 | 见下 |

在基线上审计出的具体失败：

- `TURN_ENVELOPE_SCHEMA_VERSION` 定义了三次：
  `loopx/control_plane/quota/turn_envelope.py:16`、
  `loopx/control_plane/quota/turn_envelope.ts:13`，以及
  `loopx/control_plane/turn_driver/driver.py:31` 的一份私有副本。M0 删除该副本。
- `HANDOFF_MODES` 由 TypeScript owner 定义，又在
  `control_plane/testing/authority_e2e_fixtures.py:33` 以字面元组重定义。M0 让
  夹具元组从 `HandoffMode` 枚举派生。
- 同一值集跨运行时有两个名字：`work_items/delivery_outcome.ts` 的
  `MATERIAL_DELIVERY_OUTCOMES` 等于 `goals/goal_frontier/outcome_continuity.py`
  的 `VISION_OUTCOME_CHECKPOINT_MATERIAL_OUTCOMES`。两者都是 `DeliveryOutcome`
  去掉 `surface_only`；没有任何地方说明这一点。
- 同名不同值：`DECISION_CONTEXT_CAPABILITY_ID` 在
  `capabilities/decision_context/packets.py:18` 是 `decision_context`，在
  `extension_provider.py:24` 是 `decision-context`；`MCP_REQUIREMENT` 在
  `kunluncode_goal_mode/cli.py:28` 是 `mcp==1.28.1`，在
  `claude_goal_mode/scripts/install.py:83` 是 `mcp<2`。另外 16 个名字是模块内
  通用常量（`SCHEMA_VERSION`、`COMMAND`、`CAPABILITY_ID`），今天的碰撞无害，
  明天却不可见。
- Turn 结果种类靠手工维护了两份：`transaction.py:28` 的 `LoopXTurnResultKind`
  与 `settlement.ts:49` 的 `TURN_RESULT_KINDS`。今天一致；没有任何测试断言过。
  另外 11 对 py/ts 词表同样如此（settlement 的 step、binding、failure kind，
  receipt-bound phase，scheduler transition，Todo completion 的 continuation 与
  recovery，delivery outcome，delivery workspace kind，Goal amendment class，
  Todo decision scope）。
- `effective_action` 是两侧都没有枚举的开放字符串集合。Python 与 TypeScript
  共靠字符串比较分发 31 个不同字面量。其中两个（`observe_replay`、
  `block_replay`）由 `turn_journal.ts:656` 写入 Turn Envelope 的 replay
  observation 槽位，根本不是 should-run 裁决。另外两个
  （`quota_action_selection_deferred`、`quota_action_selection_rejected`）是
  `cli_commands/quota.py:279` 复制进该槽位的 quota 错误码。
  `AgentScopeFrontierAction` 的值又被写进同一 envelope 的
  `agent_scope_frontier.effective_action` 槽位。一个字段名，三套词表。
  `user_gate.py:162` 还把该槽位与 `skip` 比较，而没有任何生产者写入它。
- 三套近似同构的 Turn 结果词表并存：`LoopXTurnResultKind`（12）、
  `LoopXTurnRoute`（8）、`LoopDisposition`（8），`repair`/`repair_required` 与
  `replan`/`replan_required` 是同一裁决的不同拼法。route 到 disposition 的投影
  是 `loop_controller.py:126` 的私有字典；没有任何声明说它覆盖全部输入。真正承重的
  `decide_loop_disposition` 决策表（result kind、retryable、attempt budget、
  decision user action、durable no-follow-up）只存在于控制器协议文档的散文里。
- 文档已称为 legacy 的六个 should-run 决策字段仍各被 7 到 35 个 Python 模块
  提及，没有棘轮阻止新消费者。
- `loopx/control_plane` 下有 43 对同名 `.py`/`.ts` 模块，而迁移 RFC 是
  replacement-first。这个数量没有守卫。
- 仓库已经在运行一支 AST 支撑的控制面债务棘轮
  （`loopx/canary/maintainability_ratchet.py`），带评审化的例外生命周期，但它
  度量的是模块指标与依赖方向，不是词表形状。词表漂移没有棘轮。

现有 owner 无法在本地解决，因为每处修复天然跨模块：Turn driver、quota、
todos、capabilities 与 TypeScript 运行时各自拥有同一想法的一种拼法。

### 不变量

- **I1 单一 owner。** 每个注册词表或常量，恰有注册表列出的定义模块，且注册的
  符号名在 `loopx/` 下别无定义。其余模块一律 import。
- **I2 闭集。** 注册词表可携带的每个值都被列出。任一运行时的代码都不携带未
  注册的值，注册表也不列出代码不携带的值。
- **I3 跨运行时一致。** 词表同时有 Python 与 TypeScript owner 时，两侧集合完全
  相同。
- **I4 完整投影。** 注册投影为每个源值恰好命名一次：要么映射，要么声明拒绝。
- **I5 棘轮只降。** 退休、孪生与清单预算可在任何 PR 中调低。每个预算在 smoke
  里另由一个 `BUDGET_ANCHOR`（或 `RETIREMENT_ANCHOR`）字面量钉住，每个下限由
  一个 `COVERAGE_ANCHOR` 钉住，沿用
  `tests/control_plane/test_m6_quality_gates.py` 的 `RFC_MODULE_BUDGETS` 锚点
  模式，但有一处刻意的不同：注册表的值必须**等于**锚点。先例用 `<=` 比较，
  这会让一个已收紧到锚点以下的预算，在之后的 PR 里不改任何代码就涨回锚点。
  相等性让每次收紧都是两个文件的 diff，每次放松都是评审者可见的代码修改。
- **I6 同 diff 可见。** 语义变化与其注册表修改或清单再生成落在同一个可评审
  diff 里。
- **I7 确定性且公开安全。** 检查只读已跟踪源码，不需网络或凭据，失败文本只
  命名文件与值，绝不含私有数据。
- **I8 覆盖只增。** 注册词表数、owner 符号数、投影数、关系数、schema 版本数
  与扫描后缀集合被记录为下限。owner 只能是 `module::Symbol` 或 `null`；裸模块
  路径被拒绝，null owner 必须声明字面量扫描。扫描识别的分发形式固定在 smoke
  里。因此一次注册表修改不可能悄悄收窄守卫所见。
- **I9 两种载体形状都被度量。** 词表进入代码的形态有两种：字符串常量
  （`NAME = "value"`）与多值载体（枚举、命名闭集、`Literal` 别名、
  TypeScript `as const` 数组）。两者适用同一条冲突规则：同一个名字在两个模块
  中被定义，值集相同是孪生，值集不同是分叉。冲突预算只统计共享词表子集；
  `SCHEMA_VERSION`、`COMMAND`、`*_LABEL` 这类模块局部约定名仍保留在清单
  总数中可见，但不算漂移。
- **I10 在 PR 路径上。** 漂移 smoke 通过
  `tests/architecture/test_semantic_vocabulary_drift.py` 跑在默认 `pytest`
  扫描里，因此在每个运行 Python 测试的 PR 上失败即关闭。`examples/` 下的舰队
  发现与 `repo-architecture-budget` premerge profile 是附加表面，不是义务：
  舰队在合并后和按日程运行，premerge 按改动路径的 token 选择。

## 3. 范围与非目标

### 范围内

- 注册表文件、其 schema，以及编辑它的所有权规则。
- 生成清单、带 `--check` 的生成器及其单元测试。
- 漂移 smoke 及其在 premerge 与 full-public 舰队中的位置。
- M0 注册的词表：四个 Turn 内核集合（`turn_result_kind`、`turn_route`、
  `loop_disposition`、`effective_action`）、`agent_scope_frontier_action` 与
  `lease_action`，以及基线上 Python 与 TypeScript owner 值集相等的二十个跨
  运行时集合；route 到 disposition 的投影；九条关系；Turn Envelope 的 schema
  版本；六个旧 should-run 字段；控制面孪生数量；清单的分叉与冲突预算。
- 后续里程碑：把 `effective_action` 变成类型化枚举、拆分其三个槽位、通过契约
  发布投影、按现有仓库规则退休旧字段与孪生模块。

### 非目标

- 改变任何运行时决策、载荷形状或线上格式。
- 手工策展每个闭集。清单映射全部闭集；只有跨模块或跨运行时边界并被分发的
  词表才带 owner、值与关系进入策展层。
- 取代 `turn_transaction_contract.json` 或
  `coordination_state_contract_v0.json`。它们仍是各自阶段与记录的 owner；本
  注册表可以引用它们，不能复述它们。
- 取代 `maintainability_ratchet.py`。它拥有模块指标与依赖方向；本注册表拥有
  词表形状。两者的例外生命周期是否合并见第 12 节 Q7。
- 用散文术语表作为强制机制。术语表是有用的伴随物，在第 12 节跟踪，但它不能
  让构建失败。

## 4. 现行系统契约

基线 `1dc6ad8d8` 上的事实：

- `turn_transaction_contract.json` 是两个运行时同时读取的唯一契约：
  `effect_program.py:160-166` 加载阶段元组，`turn_journal.ts:1` 导入该 JSON。
  这是注册表作为共享事实源所效仿的模板。
- `coordination_state_contract_v0.json` 更进一步，通过
  `scripts/generate_coordination_state_contract.py --check` 生成
  `coordination_state_contract_generated.py` 与
  `coordination_state_contract.generated.ts`，由
  `tests/control_plane/test_coordination_state_contract.py` 守卫。清单生成器
  现在效仿它，M2 提议的生成阶段之后效仿它。
- canary runner 会发现每个已跟踪的 `examples/**/*-smoke.py`
  （`loopx/canary/runner.py:392`），因此 `examples/` 下的 smoke 无需在
  `planner.py` 或 `premerge.py` 登记。
- `loopx/canary/maintainability_ratchet.py` 是现有的 AST 支撑的控制面债务棘轮。
  它带有含 `retirement_plan` 的评审化例外并检测过期例外 id。它的对象是模块
  体积、`Any` 密度、决策点数量与禁止的依赖方向；它不读取枚举或常量的值。
- `AGENTS.md` 已要求状态分类使用类型化枚举、禁止 Python 为控制面权威建立第二
  事实源、新增模块前做 scope-fit 评审、并要求任何 schema 缩减获得维护者批准。
  本 RFC 增加的是让这些规则在 diff 中可观测的检查；它不改变规则本身。
- `loopx.control_plane` 的 package data 已经打包 `*.json`；`pyproject.toml`
  增加一行，让 `loopx.semantics` 以同样方式打包其两份 JSON。

## 5. 提议架构

### 所有权与权威

注册表由控制面内核维护者拥有。任何贡献者可以调低预算，或随携带它的代码一起
新增一个值。只有维护者可以批准调高预算、删除值或迁移 owner 模块，批准记入
附录 B。

禁止的替代权威：第二份注册表、复述已注册值的模块内列表，或宣称对已注册词表
具有规范性的散文表格。

### 状态模型与 schema

`loopx/semantics/vocabulary_v0.json`，`schema_version` 为
`loopx_semantic_vocabulary_v0`。键集合是封闭的；未知的顶层键或词表键让 smoke
失败。

| 键 | 内容 | 检查 |
| --- | --- | --- |
| `coverage_floor` | 词表、owner 符号、字面量扫描字段、投影、关系、schema 版本的数量；扫描后缀集合 | 实际计数不低于下限，声明的后缀覆盖下限集合，且每个下限必须等于其 `COVERAGE_ANCHOR`（I8） |
| `vocabularies.<name>.owners` | `python` 与 `typescript`，各为 `path::Symbol` 或 `null` | 枚举成员、闭集成员、`Literal` 别名或 `as const` 数组等于 `values`；该符号只在 owner 模块中定义（I1、I2、I3） |
| `vocabularies.<name>.tier`、`status` | `kernel`、`cross_runtime`、`cross_module`；`canonical`、`legacy`、`merge_candidate` | 封闭枚举 |
| `vocabularies.<name>.literal_scan` | `field`、根目录、后缀 | 固定分发形式捕获的每个字面量都已注册；每个注册值被捕获或来自变量（I2） |
| `vocabularies.<name>.variable_sourced_values` | 值到生产者模块 | 生产者仍包含带引号的该值 |
| `vocabularies.<name>.value_notes`、`deprecated_values` | 逐值评审备注；计划删除的值 | 名字必须是已注册值 |
| `relations.same_concept` | `vocabulary.value` 成员组 | 每个成员可解析 |
| `relations.shared_field_names` | 一个字段名、其槽位及各槽位承载的词表或值 | 每个槽位可解析 |
| `relations.subsets` | 超集词表、排除值、子集符号的 owner | owner 符号等于超集减排除值 |
| `projections.<name>.mapping` | 源值到目标值或 `null` | 键等于源词表；映射值与 owner 函数一致；`null` 路由抛出（I4） |
| `schema_versions.<name>` | 常量名、值、owner 模块 | 唯一的定义模块就是列出的 owner 且都携带该值（I1） |
| `retirement_ledger.<group>.fields` | 每字段的 Python 与 TypeScript 模块预算 | 实际模块数不超过预算，且字段集合与每个预算与 `RETIREMENT_ANCHOR` 一致（I5） |
| `dual_runtime_twins` | 根目录与模块预算 | 同名 `.py`/`.ts` 对数不超过预算（I5） |
| `inventory_ratchets` | 同运行时分叉的名字数与定义数、冲突的名字数与定义数、schema 版本分叉数、多值孪生与分叉数，以及共享词表冲突与分叉子集的预算 | 清单摘要计数不超过预算，且每个预算必须等于其 `BUDGET_ANCHOR` 条目（I5、I9） |

`loopx/semantics/inventory_v0.json`，`schema_version` 为
`loopx_semantic_inventory_v0`，由 `scripts/generate_semantic_inventory.py` 生成，
必须与新鲜构建完全一致。它每行一条地列出 Python 枚举、闭集、`Literal` 别名、
TypeScript `as const` 数组，以及拆为跨运行时孪生、同运行时分叉、冲突值、多值
孪生与多值分叉四类的重复定义。每个多值冲突都带上全部定义模块及其值集，因此
可评审的是分叉本身而不只是计数。消费者计数由 `--report` 打印，合并候选组通过 `merge_candidate_groups` 获取，
两者均不提交，因此普通的消费者改动不会碰这个文件；合并候选是建议性的，因为值集
相同并不能证明是同一个概念。单模块的字符串常量只计数，不列出。

值是只增的。删除一个值、字段、owner 或关系属于 schema 缩减，遵循 `AGENTS.md`
规则：枚举受影响表面、调研生产者与读者、在同一 diff 中调低下限、记录维护者
批准。

### 命令或事件生命周期

检查只有一个命令：运行 smoke。它幂等且无副作用。失败文本命名词表、违规文件与
值，修复是机械的：注册该值、import 该常量，或收窄改动范围。

### Provider 或扩展契约

新词表通过一个 PR 加入：新增注册表条目、提高覆盖下限，若存在 TypeScript owner
则指名其 `as const` 数组。当一个词表被多个模块分发或跨越 Python/TypeScript
边界时，即有资格进入策展层；其余由清单映射而不策展。新增任何载体都要在同一
PR 中重新生成清单。

## 6. 备选方案与设计选择

| 备选 | 为何现在不选 |
| --- | --- |
| 一个 PR 把三套 Turn 枚举合一 | 违背 I5 式的渐进；三套枚举有不同 owner 与变化原因（settlement、route、controller）。先注册并投影，只在投影证明同一后再合并（第 12 节 Q2）。 |
| 依赖 `mypy` 的 `Literal` 类型 | 覆盖不到 TypeScript、JSON 载荷与 CLI；而漂移恰恰发生在这些边界。 |
| 仅靠文档术语表 | 不能让构建失败；仓库已有十一份自称 mental model 的文档且没有术语表，这本身就是症状。 |
| 立即从注册表生成绑定 | owner 尚未定下之前为时过早。生成是 M2，效仿协调契约先例。 |
| CI 里不带注册表的 grep 式 lint | 把允许集合编码进 linter，变成没有评审痕迹的第二份注册表。 |
| 扩展 `maintainability_ratchet.py` 而不新建注册表 | 它的对象是模块指标与依赖方向，按模块设上限；词表形状需要值、owner 与关系。两者共享棘轮思想而非数据模型。例外生命周期是否合并见 Q7。 |
| 把扫描正则放进注册表 | 数据里的正则可以在扩宽词表的同一次修改中被收窄；M0 评审表明第一版模式漏掉了全部 TypeScript `===` 分发点。形式固定在 smoke 里，后缀集合设下限。 |
| 在清单中提交消费者计数 | 每次消费者改动都会搅动文件，让新鲜度检查变成噪音。计数通过 `--report` 保持为参考信息。 |

## 7. 安全、隐私与兼容

- M0 没有任何运行时路径导入注册表；检查存在与否，产品行为不变。
- 扫描器使用 `git ls-files --cached -z` 枚举索引中的源文件路径，再读取工作树内容。
  未跟踪与忽略文件不进入清单；新增源文件需先暂存路径，再重新生成清单。已跟踪
  的符号链接与无法解析的 Python 源码使检查失败；运行时需要带 Git 元数据的检出。
- 字面量及 TypeScript 载体扫描同时识别单引号与双引号。它们仍是结构性文本
  扫描，不是完整解析器，也不做数据流分析。
- 字面量扫描根目录与后缀、孪生模块根目录与预算均有代码锚点；仅修改 JSON
  不能缩窄扫描范围或提高孪生预算。
- 失败文本只使用仓库相对路径与已注册标识符。
- 旧的读写方不受影响。预算冻结其当前分布，不删除任何一处引用。
- 构建期检查不涉及混合版本。M2 引入生成绑定时，生成器的 `--check` 模式与
  smoke 同时运行，过期的生成文件无法合入。

## 8. 迁移与回滚

- **准入。** M0 落地时注册表与清单和基线完全一致，外加两处保持行为的修改以让
  owner 检查通过：`driver.py` 中重复的 `TURN_ENVELOPE_SCHEMA_VERSION` 改为
  import，authority e2e 夹具中的 `HANDOFF_MODES` 元组改为从 `HandoffMode` 枚举
  派生。
- **回滚。** 删除 smoke、`loopx/semantics/` 包、生成器、其测试与 `pyproject.toml`
  的那一行即恢复原状，无运行时影响。后续里程碑在第 11 节各带回滚。
- **不可回退点。** M0 没有。M3 的字段删除是第一个不可逆步骤，逐个门控。

## 9. 验证与验收

| 声明 | 测试或证据 | 要求结果 | 边界 / 排除 |
| --- | --- | --- | --- |
| 基线上注册表与清单和代码一致 | `python3.11 examples/semantic-vocabulary-drift-smoke.py` | `ok` 并输出覆盖、棘轮、预算与孪生报告 | 只证明已注册词表与已映射载体的一致性 |
| 清单新鲜 | `python3.11 scripts/generate_semantic_inventory.py --check` | 退出码 0 | 仅结构性映射 |
| 扫描器分类规则 | `pytest tests/architecture/test_semantic_inventory.py` | 通过 | 夹具仓库；规则来自本 RFC 而非输出 |
| Python 侧扩宽 `effective_action` 时失败关闭 | 通过 `==`、成员测试或条件表达式加一个未注册字面量 | 失败文本命名该值与文件 | 突变练习；非提交测试 |
| TypeScript 侧扩宽 `effective_action` 时失败关闭 | 通过 `===` 或三元表达式加一个未注册字面量 | 同上 | 同上 |
| 分叉常量时失败关闭 | 在非 owner 模块重定义 `TURN_ENVELOPE_SCHEMA_VERSION` 或 `HANDOFF_MODES`，重新生成清单 | 失败列出多出的定义模块或分叉预算 | 同上 |
| Python 与 TypeScript owner 不能分叉 | 从已注册 `as const` 数组删一项，或扩宽已注册枚举 | 失败命名缺失或未注册的值 | 同上 |
| 注册表不能仅靠改数据被削弱 | 声明裸模块 owner；删掉一个 owner；把后缀收窄为 `.py`；重命名一个被关系引用的词表；加一个未知键 | 每项都失败并点名规则 | 同上 |
| 新载体可见 | 新增一个枚举而不重新生成 | 失败文本说清单过期 | 同上 |
| 冲突拼法不能增长 | 为已冲突名字加第三种值，重新生成 | 失败命名定义数预算 | 同上 |
| 多值冲突不能增长 | 让一个闭集名在两个模块中以不同值集定义，或以相同值集定义，并重新生成 | `multi_value_forks` 或 `multi_value_twins` 失败并命名新名字 | 突变练习；非提交测试 |
| 注册表不能放松自己的棘轮 | 在同一 diff 中调低任一 `coverage_floor` 计数、调高任一 `inventory_ratchets` 预算或退休预算，同时删掉它所统计的覆盖 | `COVERAGE_ANCHOR`、`BUDGET_ANCHOR` 或 `RETIREMENT_ANCHOR` 失败并命名被锚定的值 | 突变练习；挪动锚点是一次评审者可见的代码修改 |
| 已收紧的预算不能漂回过期锚点 | 只调低注册表预算而不动锚点 | 失败文本指出注册表值与锚点不等 | 用相等而非 `<=`；修法是同 diff 调低锚点 |
| smoke 在 PR 路径上 | `pytest tests/architecture/test_semantic_vocabulary_drift.py` | 通过；该测试被 `python-tests.yml` 的默认 `pytest -q` 扫描收集 | 舰队与 premerge 表面不是义务（I10） |
| premerge 会为 `loopx/` 的 diff 选中该 smoke | `loopx canary premerge --changed-file loopx/control_plane/turn_driver/loop_controller.py` | 计划在 `repo-architecture-budget` 下列出 `examples/semantic-vocabulary-drift-smoke.py` | 选择靠触发词；pytest 包装才是保证 |
| 度量覆盖两种载体形状并过滤局部命名 | `pytest tests/architecture/test_semantic_inventory.py` | 通过，含冲突与模块局部约定两组夹具 | 规则来自本 RFC 而非扫描输出 |
| 两处 owner 修正不改变行为 | `pytest tests/test_loopx_turn_transaction.py tests/test_loop_turn_loop_controller.py tests/test_turn_loop_disposition.py tests/test_loopx_turn_managed_step.py tests/control_plane -k authority` 与 `loopx canary premerge --from-git-diff` | 通过 | 在干净树上可复现的 `main` 既有环境失败除外 |
| 文档治理接受这对 RFC | `python3 examples/docs-governance-smoke.py` | 通过 | 检查镜像、链接、索引 |

已知边界，写明是为了不让这个检查被过度信任：

- **改名可以洗白冲突。** 冲突按名字归组，因此把分叉的一侧改名会降低计数而
  不消除漂移。这里的评审辅助是建议性合并报告；值集相同不能做成硬预算，因为
  `CONFIDENCE_LEVELS` 与 `EDGE_CASE_COMPLEXITIES` 共享 `high/low/medium` 却
  含义不同。
- **单元素载体不可见。** 只有一个字符串成员的闭集不构成词表，因此把一个两值
  集合降为一个值会让它完全退出清单。
- **字面量扫描可能误读同一行上无关的比较。** 形如
  `log("effective_action", kind === "repair_required")` 会被捕获为
  `effective_action` 的值。为了让失败消失而登记被报告的值会扩宽词表，正确做法
  是同时登记字段名与字面量，或改写该行；失败文本会给出文件，评审时可见。
- **锚点是代码而非历史。** PR 仍可挪动锚点，但必须修改一个具名字面量，就在
  注册表改动的旁边。因为检查是相等性，锚点不可能过期，但它也不记住曾达到的
  最低值；那段历史在 git log 里。

## 10. 运维契约

该检查不可能影响运行中的系统：它只在测试、premerge 与 CI 中执行。其操作者
界面就是失败文本。不适用可观测性、容量或值班契约。

它在哪里运行，以及哪个表面是义务：

| 表面 | 触发 | 选择 | 角色 |
| --- | --- | --- | --- |
| `pytest` 扫描，`python-tests.yml` | 每个分类为需运行 Python 测试的 PR | 经 `tests/architecture/test_semantic_vocabulary_drift.py` 始终被收集 | **提交时义务（I10）** |
| `loopx canary premerge` | 本地，开 PR 之前 | `repo-architecture-budget` profile，触发词含 `loopx/`、`examples/`、`scripts/`、`refactor` | 早期本地信号 |
| 全量公共 smoke 舰队 | push 到 `main`、每日日程、手动触发 | `examples/**/*-smoke.py` 发现 | 合并后确认；按设计不是 PR 必需检查 |

在这张表存在之前，RFC 说 smoke "在 premerge 与 CI 中运行"。在基线上这只在合并
后成立：premerge 对只改 `loopx/control_plane/` 的 diff 不会选中该 smoke，而舰队
工作流被刻意设为非 PR 必需检查。舰队能发现的 smoke 不是提交时检查，除非某个
必需的 PR 作业收集它。

## 11. 规范性交付计划

| 里程碑 | 交付行为 | 进入门 | 退出证据 | 回滚 |
| --- | --- | --- | --- | --- |
| M0 | 含 26 个词表与 9 条关系的注册表、带 `--check` 的生成清单、带固定分发形式与覆盖下限的漂移 smoke、删除两处 owner 分叉、RFC 索引条目 | 本 RFC 开启 | 第 9 节各行全绿；20 类突变失败关闭 | 删除 smoke、`loopx/semantics/`、生成器及其测试 |
| M1 | 单一 owner 模块中的 `EffectiveAction` 类型化枚举；replay observation 与 frontier 槽位拆出（Q6）；生产者与消费者 import 它；注册表 `literal_scan` 收紧到枚举 | M0 合入；owner 模块已定（Q3）；槽位拆分已决（Q6） | smoke 绿；owner 之外零裸 `effective_action` 字面量；status/should-run 的 parity fixture 不变 | 回退为字面量；注册表保留集合 |
| M2 | route 到 disposition 的投影、`decide_loop_disposition` 决策表与跨运行时集合通过共享契约发布，生成 Python 与 TypeScript 绑定，效仿协调契约生成器 | M1 合入；Q2 与 Q7 已决 | 生成器 `--check` 与 smoke 绿；`settlement.ts` 与 `transaction.py` 读取生成集合 | 从上一版契约重新生成 |
| M3 | 逐字段退休旧 should-run 字段，每个 PR 一个字段，预算降到零并删除字段 | 经生产者/读者调研证明该字段外部读者为零 | 按 `AGENTS.md` 的 schema 缩减记录；附录 B 条目 | 从最后一个写方恢复字段 |
| M4 | 随迁移 RFC 的每次 replacement-first 切换调低孪生预算 | 每个切换 PR | 同 diff 中的预算修改 | 无需；预算跟随代码 |

## 12. 未决决策

1. **注册表位置。** Owner：内核维护者。M0 实现于 `loopx/semantics/`，因为范围是
   全仓库的，而 `loopx/control_plane/` 与 `docs/reference/` 都不是；该包只含两份
   JSON 与扫描器，没有任何产品代码导入它。在记入附录 B 之前这只是提案。M1 前
   需定。
2. **是否合并 `LoopXTurnRoute` 与 `LoopDisposition`？** Owner：Turn driver owner。
   投影覆盖全部输入但非单射（`blocked` 与 `wait` 都映到 `wait`），而 `stop`、
   `terminal`、`contract_error` 只在一侧存在。`same_concept` 关系记录了四个共享
   裁决。建议：两者都保留，M2 发布投影，待 managed-step 消费者成熟后再议。
   M2 前需定。
3. **`EffectiveAction` 的 owner 模块。** 注册表今天不声明 owner，因为不存在任何
   符号；字面量扫描是唯一检查。选项：`quota/should_run_packet.py`（最大生产者）、
   新建 `quota/effective_action.py`，或按迁移 RFC 以 TypeScript `turn_envelope.ts`
   为 owner 并生成 Python 绑定。建议：若 M2 先落地则以 TypeScript 为 owner 并
   生成 Python 绑定；否则新建 `quota/effective_action.py`。M1 前需定。
4. **伴随术语表。** 是否新增 `docs/reference/glossary.md`，从注册表的 `meaning`
   字段与清单生成。Owner：文档维护者。建议：是，在 M1 生成以免漂移。
5. **词族命名规则。** `gate`、`scope`、`packet`、`handoff`、`settlement` 词族中的
   新标识符是否必须在评审中引用术语表条目。这是评审规则而非 smoke；建议在
   术语表存在后纳入 first-review roster。
6. **拆分 `effective_action` 的三个槽位。** decision 槽位、`agent_scope_frontier`
   槽位与 replay observation 槽位在同一个 Turn Envelope 里共用一个字段名、承载
   三套词表；`skip` 被比较却从未被生产。选项：重命名 observation 与 frontier
   槽位，或保留一个字段并注册其并集。Owner：Turn Envelope owner。建议：在 M1
   重命名，让 Q3 的枚举只有一种含义。M1 前需定。
7. **与 `maintainability_ratchet.py` 的关系。** 清单棘轮是否采用它的评审化例外
   生命周期（`retirement_plan`、过期例外检测），还是保持为纯预算。建议：在 M2
   生成落地时采用，让有书面理由的分叉可以被例外而非被预算。Owner：canary
   维护者。
8. **从清单到注册表的晋升规则。** 外部消费者模块不少于三个或存在跨运行时孪生
   的已映射载体是否必须策展。建议：现在作为评审规则采用，待清单积累一个季度
   历史后再由 smoke 强制。Owner：内核维护者。

## 附录 A：执行账本（非规范）

### 2026-09-15 — 随 RFC 开启 M0

- **基线：** `1dc6ad8d8`
- **交付：** 含四个词表、一个投影、一个 schema 版本、六个旧字段预算、一个孪生
  预算的注册表；漂移 smoke；`driver.py` 中重复的 `TURN_ENVELOPE_SCHEMA_VERSION`
  改为 import。
- **证据：** 第 9 节各行；见附录 C。
- **已知缺口：** 投影检查在 M2 发布之前导入私有的 `_route_to_disposition`。
- **对规范设计的影响：** 无。

### 2026-09-15 — 评审后修订 M0；范围改为全仓库

- **基线：** `1dc6ad8d8`
- **触发：** 一次评审发现第一版字面量扫描对 TypeScript 完全失明（`===` 从不
  匹配）、基线上已有两个未注册值（`observe_replay`、`block_replay`），以及
  owner 检查会静默跳过任何不带符号的 owner。
- **交付：** 注册表迁至 `loopx/semantics/vocabulary_v0.json` 并扩为 26 个词表、
  46 个 owner 符号、9 条关系与覆盖下限；生成清单 `inventory_v0.json`，带
  `--check` 的生成器与单元测试；smoke 重写为固定分发形式（比较、赋值、三元、
  成员、条件表达式）、基于 AST 的 owner 解析、owner 排他性、清单新鲜度与
  分叉/冲突预算；`HANDOFF_MODES` 夹具分叉改为从枚举派生。
- **证据：** 附录 C 的 E6 到 E10。
- **已知缺口：** 承重的 `decide_loop_disposition` 决策表仍只有散文（M2）；
  字面量扫描无法把一个字面量归到 `effective_action` 三个槽位中的某一个（Q6）；
  扫描无法跟随变量传值，因此两个 quota 错误码以"变量来源值"登记并核验生产者，
  而非被证明。
- **对规范设计的影响：** 第 1 至 5、8、9、11、12 节修订；新增 I8。记为未合入
  草案的当日修订。

### 2026-09-15 — 第二次评审后修复 M0 的度量

- **基线：** `1dc6ad8d8`
- **触发：** 第二次评审对 smoke 跑了 14 种攻击，7 种逃逸：单独调低某个
  `coverage_floor`、一次调低全部下限、调高 `inventory_ratchets` 或某个退休
  预算，以及最关键的——在同一个 diff 中删掉一个 owner 并同时调低对应的下限。
  下限与被它守护的文件在同一个文件里，且只用 `>=` 比较，因此注册表可以放松
  自己的棘轮。I5 与 I8 当时是散文，不是机器约束。
- **同时发现：** 冲突检测只跑字符串常量，599 个多值载体只被列出、从未被比较。
  基线上已经有四个同名分叉，其中 `SOURCE_SURFACES` 被定义四次、四套不同值集，
  另有 19 个隐藏孪生。另外，18 个 `conflicting_values` 名字中有 16 个是模块
  局部约定（`SCHEMA_VERSION` 出现 16 次，另有 `COMMAND`、`REQUEST_SCHEMA`、
  `SURFACE`），因此该预算主要在度量局部命名。
- **交付：** smoke 中新增锚点 `COVERAGE_ANCHOR`、`COVERAGE_SUFFIX_ANCHOR`、
  `BUDGET_ANCHOR`、`RETIREMENT_ANCHOR`，关闭全部七种逃逸；
  `multi_value_name_collisions` 让枚举、闭集、`Literal` 别名与 `as const`
  数组适用字符串常量的冲突规则，四个分叉与 19 个孪生按当日计数入预算；
  `MODULE_LOCAL_CONVENTION` 让局部名保留在可见总数中但不进入语义预算
  （`conflicting_values_semantic` 为 2，`same_runtime_forks_semantic` 为 18）；
  针对 32 组同名异名同值集的建议性合并候选报告；在独立冲突夹具上新增两个
  扫描器测试；新增 I9 并写明第 9 节的边界。
- **证据：** 附录 C 的 E11 到 E13。
- **已知缺口：** 冲突按名字归组，因此改名仍可洗白一个；单元素载体不可见；
  字面量扫描可能误读同一行上无关的比较。
- **对规范设计的影响：** I5 与 I8 从"意图"改写为"已强制"；新增 I9；第 5 节
  表格与第 9 节各行更新。现在放松预算的唯一方式是挪动锚点，而那是一次代码
  修改。
- **被收紧的未决项：** Q7 可能从"采纳 `maintainability_ratchet` 的例外
  生命周期"收敛为"共用它的锚点模式"，因为本 smoke 已经在用该模式。

### 2026-09-15 — 第三次评审后把 M0 放上 PR 路径

- **基线：** `1dc6ad8d8`
- **触发：** 第三次评审问 smoke 到底在哪里运行。对只改 `loop_controller.py`
  与 `turn_envelope.ts` 的 diff 做 premerge 规划，得到 32 条命令，不含本
  smoke；`full-public-smokes.yml` 只在 push 到 `main` 与每日日程触发，且文档
  写明刻意不作 PR 必需检查。每个 PR 都跑的唯一表面是 `pytest` 扫描，而已提交
  的测试只覆盖夹具上的扫描器。RFC 的"提交时"声明因此只在合并后成立。
- **同时发现：** 每个锚点都用 `<=`（下限用 `>=`）比较，忠实复制了
  `RFC_MODULE_BUDGETS` 先例。一个 PR 把预算收紧到锚点以下后，后续 PR 可以不
  改代码把它涨回锚点，棘轮停在锚点最后的值上。
- **交付：** `tests/architecture/test_semantic_vocabulary_drift.py` 在默认扫描
  里以子进程运行 smoke；smoke 加入 `repo-architecture-budget` premerge
  profile，与可维护性棘轮并列；三处锚点比较改为相等；新增 I10；第 10 节增加
  表面表格。
- **证据：** 附录 C 的 E14 到 E16。
- **已知缺口：** pytest 包装每次扫描约耗 3 秒；premerge 选择仍依赖触发词匹配
  改动路径。
- **对规范设计的影响：** I5 改述为相等并说明偏离先例的理由；新增 I10；第 9 节
  增三行；第 10 节从一句话改写为表面表格。

## 附录 B：决策日志

| 日期 | 决策 | Owner / 批准 | 备选 | 变更的规范章节 |
| --- | --- | --- | --- | --- |
| — | 尚无记录 | — | — | — |

## 附录 C：证据登记

| 证据 id | 声明 | 基线 / 环境 | 产物或命令 | 结果 | 隐私 / 有效性边界 |
| --- | --- | --- | --- | --- | --- |
| E1 | envelope schema 常量有三处定义 | `1dc6ad8d8` | `rg -n 'TURN_ENVELOPE_SCHEMA_VERSION\s*=' loopx` | 3 个文件 | 仅源码 |
| E2 | `loopx/` 下 28 个不同的 `effective_action` 字面量 | `1dc6ad8d8` | smoke 的 `literal_scan` | 28 | 受正则约束；不含散文提及 |
| E3 | 控制面下 43 对 py/ts 孪生 | `1dc6ad8d8` | smoke 孪生报告 | 43 | 仅同名规则 |
| E4 | 旧字段分布 | `1dc6ad8d8` | smoke 预算报告 | 见注册表 | 模块提及数，非调用点 |
| E6 | 闭集载体全局普查 | `1dc6ad8d8` | `python3.11 scripts/generate_semantic_inventory.py` 摘要 | 102 枚举、490 闭集、8 别名、40 数组、2002 命名常量、166 孪生、25/58 分叉、18/59 冲突 | AST 与 `as const` 文本扫描；仅模块级 |
| E7 | 第一版扫描模式捕获零个 TypeScript 站点 | `1dc6ad8d8` | 对每个含 `effective_action` 的 `.ts` 行应用该模式 | 7 个分发文件中 0 个匹配；`===` 总是失败 | 受模式约束 |
| E8 | 第一版 smoke 全绿时基线上已有两个未注册 `effective_action` 值 | `1dc6ad8d8` | `turn_journal.ts:656` 三元表达式 | `observe_replay`、`block_replay` | 同上 |
| E9 | owner 检查跳过了裸模块 owner | `1dc6ad8d8` | 第一版 smoke 的 `if "::" in python_owner` | `effective_action` 的 owner 从未被检查 | 读码加突变 |
| E10 | 二十个漂移突变全部失败关闭（TS `===`、TS 三元、Python 成员、经 `or ""` 的 Python `==`、裸 owner、删 owner、收窄后缀、重命名词表、分叉符号、删 TS 值、扩宽枚举、改投影、旧字段回涨、清单过期、第三种冲突拼法、死值、变量生产者消失、子集破坏、schema 版本分叉、注册表未知键） | `1dc6ad8d8` + 本地改动，改动新增载体时重新生成清单，每次运行后恢复 | 临时改动后以 `python3 -B` 运行 smoke | 20/20 退出码 1 并点名规则、值或文件 | 本地练习，非提交测试 |
| E5 | 九个漂移突变全部失败关闭（含数字与不含数字的未注册字面量、分叉常量、删除 TS 种类、扩宽 Python 枚举、改投影、旧字段回涨、注册表死值、新 py/ts 孪生） | `1dc6ad8d8` + 本地改动，每次运行后恢复 | 临时改动后以 `python3 -B` 运行 smoke | 9/9 退出码 1 并命名违规值或文件 | 本地练习，非提交测试；同尺寸同秒改写需 `-B` 绕过过期字节码 |
| E11 | 注册表可以在一个 diff 内放松自己的棘轮 | `1dc6ad8d8` + 本地改动 | 十四种注册表突变：调低一个下限、调低全部下限、在删掉它统计的 owner 的同时调低下限、调高全部 `inventory_ratchets` 条目、调高单个条目、调高一个退休预算 | 锚点前 7 种逃逸，锚点后 0 种；每个被捕获的失败都命名被锚定的值 | 本地练习，非提交测试 |
| E12 | 599 个多值载体只被列出、从未被比较 | `1dc6ad8d8` | 对枚举、闭集、`Literal` 别名与 `as const` 数组应用冲突规则 | 基线上已有 4 个同名分叉（10 个定义）与 19 个孪生，均未入预算；仅 `SOURCE_SURFACES` 就有四套不同值集 | 按名字归组；一次改名会把一个名字移出比较 |
| E14 | smoke 不在 PR 路径上 | `1dc6ad8d8` + M0 | `loopx canary premerge --changed-file loopx/control_plane/turn_driver/loop_controller.py --changed-file loopx/control_plane/quota/turn_envelope.ts`；`.github/workflows/full-public-smokes.yml` 的触发条件 | 规划 32 条命令，smoke 缺席；舰队只在 push 到 `main` 与日程运行 | 按路径 token 选择；CI 接线读自工作流文件 |
| E15 | 已收紧的预算可以漂回锚点 | `1dc6ad8d8` + M0 | smoke 中的 `ratchets[key] <= BUDGET_ANCHOR[key]` 与 `floor[key] >= anchored` | 收紧后的预算与锚点之间的任何值都能通过 | 代码阅读；先例用同样的比较 |
| E16 | 相等性关闭停滞，包装进入扫描 | `1dc6ad8d8` + M0 | 只调低一个 `inventory_ratchets` 条目而不动锚点，然后在干净树上跑 `pytest tests/architecture/test_semantic_vocabulary_drift.py` | 突变失败并同时命名两个值；包装约 3 秒通过 | 本地练习加已提交测试 |
| E13 | 冲突预算主要在度量局部命名 | `1dc6ad8d8` | 对 `conflicting_values` 与 `same_runtime_forks` 名字应用 `MODULE_LOCAL_CONVENTION` | 18 个冲突中 16 个、25 个分叉中 7 个是模块局部约定；语义子集分别为 2 与 18 | 分类是名字模式，已在扫描器中说明并由夹具测试钉住 |

## 附录 D：被否决或取代的方案

见第 6 节。单 PR 合并枚举被否决，因为三套枚举变化原因不同；可重开该决策的证据
是 M2 之后投影被证明为双射。

## 附录 E：事故与评审教训

- 跨运行时手工同步的平行常量列表在其中一侧改变之前总能通过评审；接受第二份
  副本之前必须先有一致性检查。
- 在大模块里私有抽一份共享常量看起来无害，却是 schema 版本分叉最常见的方式。
  测试夹具是第二常见的方式：`HANDOFF_MODES` 被复制进了一个 e2e 夹具。
- 只接受 `[a-z_]` 的字面量扫描在 M0 突变练习中悄悄放过了 `_v2` 拼法。应捕获
  所有带引号字符串并单独校验形状，让畸形值被报告而非被忽略。
- 按 Python 例子写出的扫描模式在 TypeScript 上一个都不匹配；一个在含违规的
  基线上仍然全绿的守卫，只证明守卫是盲的。在宣称不变量之前，对注册表声称
  覆盖的每个运行时做突变测试。
- 当注册表既是规范又是校验器的输入，一次数据修改就能削弱校验器。把识别形式
  留在代码里、给覆盖计数设下限、拒绝不是 `module::Symbol` 的 owner。
- 只按名字计数的棘轮会放过已冲突名字的第三种拼法。定义数与名字数都要预算。
- 舰队能发现的 smoke 不是提交时检查。要问它被哪个必需的 PR 作业收集，并用
  一个只改被守护代码的 diff 做规划，看选择是否找到它。如果答案是"合并后"，
  这条不变量就是报告，不是门。
- 用 `<=` 比较的锚点只钉住写下它时的值。之后的每次收紧都无保护，直到有人记得
  挪锚点。用相等性比较，两个值就分不开。
- 同一个字段名可以在一个 envelope 里承载多套词表；看得见字段的扫描看不见
  槽位。把槽位记为关系，让歧义成为已登记的事实，而不是注册表背书的意外。
