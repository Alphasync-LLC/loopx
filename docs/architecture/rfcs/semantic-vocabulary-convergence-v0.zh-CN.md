# RFC：语义词表收敛与提交期漂移检查（v0）

- **RFC status：** Draft
- **Delivery maturity：** Partial（M0 的注册表与漂移 smoke 随本 RFC 一起交付）
- **Authors / owners：** LoopX 贡献者；控制面内核维护者拥有批准权
- **Created：** 2026-09-15
- **Last normative revision：** 2026-09-15
- **Implementation baseline：** `1dc6ad8d8`
- **Related contracts：** `loopx/control_plane/semantic_vocabulary_v0.json`、
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

1. **什么成为权威。** 一份机器可读的注册表
   `loopx/control_plane/semantic_vocabulary_v0.json`，为每个跨模块词表命名：
   允许定义它的确切模块、词表之间的全射投影，以及仓库同意只降不升的退休预算。
   一支公共 smoke `examples/control_plane/semantic-vocabulary-drift-smoke.py`
   在每次 premerge 与 full-public 运行时用注册表核对代码。任何扩宽词表、
   分叉常量或让旧表面重新增长的改动，必须在同一个 diff 里修改注册表，
   评审者因此能把语义变化当作变化看见。
2. **什么不变。** 运行时行为、线上格式、枚举类本身。每个枚举继续住在自己的
   owner 模块里；本阶段注册表只核对代码，不生成代码。
3. **默认与可选边界。** 检查对仓库始终开启。它没有运行时开关，因为它从不在
   产品内运行。
4. **主要约束。** 失败即关闭且确定性。未注册字面量、第二个定义模块、预算超支，
   或注册表中列出但没有任何模块携带的值，每一项都让 smoke 失败。smoke 只读
   已跟踪源码，不打印任何私有数据。
5. **本 RFC 不批准的事。** 把三套 Turn 结果枚举合并为一套、删除任何旧的
   should-run 字段、删除任何 Python 孪生模块、重命名任何现有值。这些属于后续
   里程碑，各自受 `AGENTS.md` 中 schema 缩减规则的门控。

## 2. 问题与动机

LoopX 由大量小型 agent 驱动的 PR 生长而成。每个 PR 在需要之处加上它需要的
词汇。结果不是错误行为，而是漂移：同一概念多种拼法，同一常量在多个文件定义，
以及任何模块都可扩宽而无人察觉的开放字符串集合。评审者无法从 diff 判断一个新
字面量是新状态还是拼写错误，文档也无法跟上一个没人枚举的集合。

在基线上审计出的具体失败：

- `TURN_ENVELOPE_SCHEMA_VERSION` 定义了三次：
  `loopx/control_plane/quota/turn_envelope.py:16`、
  `loopx/control_plane/quota/turn_envelope.ts:13`，以及
  `loopx/control_plane/turn_driver/driver.py:31` 的一份私有副本。任一文件升版本
  都会悄悄割裂 envelope 契约。M0 删除该副本。
- Turn 结果种类靠手工维护了两份：`transaction.py:28` 的 `LoopXTurnResultKind`
  （12 值）与 `settlement.ts:49` 的 `TURN_RESULT_KINDS`（12 值）。今天一致；
  没有任何测试断言过这点。
- `effective_action` 是开放字符串集合。11 个模块产出 28 个不同字面量，消费方
  靠字符串比较分发；两侧都没有枚举，文档以散文提到其中约十个。
- 三套近似同构的 Turn 结果词表并存：`LoopXTurnResultKind`（12）、
  `LoopXTurnRoute`（8）、`LoopDisposition`（8）。route 到 disposition 的投影是
  `loop_controller.py:127-135` 的私有字典；没有任何声明说它是全射。
- 文档已称为 legacy 的六个 should-run 决策字段（`execution_obligation`、
  `heartbeat_recommendation`、`work_lane_contract`、
  `external_evidence_observation`、`goal_boundary`、`protocol_action_packet`）
  仍各被 7 到 35 个 Python 模块提及，没有棘轮阻止新消费者。
- `loopx/control_plane` 下有 43 对同名 `.py`/`.ts` 模块，而迁移 RFC 是
  replacement-first。这个数量没有守卫。
- 词族在没有术语表的情况下扩散：`loopx/` 下含 `gate` 的标识符 561 个、
  `scope` 536、`packet` 285、`handoff` 200、`settlement` 170。

现有 owner 无法在本地解决，因为每处修复天然跨模块：Turn driver、quota、
todos 与 TypeScript 运行时各自拥有同一想法的一种拼法。

### 不变量

- **I1 单一 owner。** 每个注册词表或常量，恰有注册表列出的定义模块。其余模块
  一律 import。
- **I2 闭集。** 注册词表可携带的每个值都被列出。代码不携带未注册的值，注册表
  也不列出代码不携带的值。
- **I3 跨运行时一致。** 词表同时有 Python 与 TypeScript owner 时，两侧集合完全
  相同。
- **I4 全射投影。** 注册投影为每个源值恰好命名一次：要么映射，要么声明拒绝。
- **I5 棘轮只降。** 退休预算与孪生预算可在任何 PR 中调低。调高需要维护者批准
  并记入附录 B。
- **I6 同 diff 可见。** 语义变化与其注册表修改落在同一个可评审 diff 里。
- **I7 确定性且公开安全。** 检查只读已跟踪源码，不需网络或凭据，失败文本只
  命名文件与值，绝不含私有数据。

## 3. 范围与非目标

### 范围内

- 注册表文件、其 schema，以及编辑它的所有权规则。
- 漂移 smoke 及其在 premerge 与 full-public 舰队中的位置。
- M0 注册的词表：`turn_result_kind`、`turn_route`、`loop_disposition`、
  `effective_action`、route 到 disposition 的投影、Turn Envelope 的 schema
  版本、六个旧 should-run 字段、控制面孪生数量。
- 后续里程碑：把 `effective_action` 变成类型化枚举、通过契约发布投影、按现有
  仓库规则退休旧字段与孪生模块。

### 非目标

- 改变任何运行时决策、载荷形状或线上格式。
- 注册仓库里的每个字符串。只有跨模块或跨运行时边界并被分发的词表属于这里。
- 取代 `turn_transaction_contract.json` 或
  `coordination_state_contract_v0.json`。它们仍是各自阶段与记录的 owner；本
  注册表可以引用它们，不能复述它们。
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
  `tests/control_plane/test_coordination_state_contract.py` 守卫。这是 M2 提议的
  生成阶段所效仿的模板。
- premerge 选择器（`loopx canary premerge --from-git-diff`）与 full-public 工作流
  会发现每个已跟踪的 `examples/**/*-smoke.py`，因此 `examples/control_plane/`
  下的 smoke 无需注册。
- `AGENTS.md` 已要求状态分类使用类型化枚举、禁止 Python 为控制面权威建立第二
  事实源、并要求任何 schema 缩减获得维护者批准。本 RFC 增加的是让这些规则在
  diff 中可观测的检查；它不改变规则本身。
- 现有模块体积棘轮（CLI 模块体积 smoke 中的 `STARTER_MODULE_LIMITS`）确立了
  "冻结基线只许收缩"的仓库先例。

## 5. 提议架构

### 所有权与权威

注册表由控制面内核维护者拥有。任何贡献者可以调低预算，或随携带它的代码一起
新增一个值。只有维护者可以批准调高预算、删除值或迁移 owner 模块，批准记入
附录 B。

禁止的替代权威：第二份注册表、复述已注册值的模块内列表，或宣称对已注册词表
具有规范性的散文表格。

### 状态模型与 schema

`semantic_vocabulary_v0.json`，`schema_version` 为 `loopx_semantic_vocabulary_v0`：

| 键 | 内容 | 检查 |
| --- | --- | --- |
| `vocabularies.<name>.owners` | `python: path::Symbol`，可选 `typescript: path::CONST` | 枚举成员与 `as const` 数组等于 `values`（I1、I2、I3） |
| `vocabularies.<name>.literal_scan` | 根目录、后缀、捕获值的正则 | 每个捕获的字面量都已注册；每个注册值至少在某处被捕获（I2） |
| `projections.<name>.mapping` | 源值到目标值或 `null` | 键等于源词表；映射值与 owner 函数一致；`null` 路由抛出（I4） |
| `schema_versions.<name>` | 常量名、值、owner 模块 | 唯一的定义模块就是列出的 owner（I1） |
| `retirement_ledger.<group>.fields` | 每字段的 Python 与 TypeScript 模块预算 | 实际模块数不超过预算（I5） |
| `dual_runtime_twins` | 根目录与模块预算 | 同名 `.py`/`.ts` 对数不超过预算（I5） |

值是只增的。删除一个值、字段或 owner 属于 schema 缩减，遵循 `AGENTS.md` 规则：
枚举受影响表面、调研生产者与读者、记录维护者批准。

### 命令或事件生命周期

检查只有一个命令：运行 smoke。它幂等且无副作用。失败文本命名词表、违规文件与
值，修复是机械的：注册该值、import 该常量，或收窄改动范围。

### Provider 或扩展契约

新词表通过一个 PR 加入：新增注册表条目，若存在 TypeScript owner 则同时加其
`as const` 数组。当一个词表被多个模块分发或跨越 Python/TypeScript 边界时，
即有资格注册。

## 6. 备选方案与设计选择

| 备选 | 为何现在不选 |
| --- | --- |
| 一个 PR 把三套 Turn 枚举合一 | 违背 I5 式的渐进；三套枚举有不同 owner 与变化原因（settlement、route、controller）。先注册并投影，只在投影证明同一后再合并（第 12 节 Q2）。 |
| 依赖 `mypy` 的 `Literal` 类型 | 覆盖不到 TypeScript、JSON 载荷与 CLI；而漂移恰恰发生在这些边界。 |
| 仅靠文档术语表 | 不能让构建失败；仓库已有十一份自称 mental model 的文档且没有术语表，这本身就是症状。 |
| 立即从注册表生成绑定 | owner 尚未定下之前为时过早。生成是 M2，效仿协调契约先例。 |
| CI 里不带注册表的 grep 式 lint | 把允许集合编码进 linter，变成没有评审痕迹的第二份注册表。 |

## 7. 安全、隐私与兼容

- M0 没有任何运行时路径导入注册表；检查存在与否，产品行为不变。
- smoke 只读已跟踪的仓库文件，只打印相对仓库根的路径与已注册标识符。
- 旧的读写方不受影响。预算冻结其当前分布，不删除任何一处引用。
- 构建期检查不涉及混合版本。M2 引入生成绑定时，生成器的 `--check` 模式与
  smoke 同时运行，过期的生成文件无法合入。

## 8. 迁移与回滚

- **准入。** M0 落地时注册表与基线完全一致，外加删除那一个重复常量以让 owner
  检查通过。
- **回滚。** 删除 smoke 与注册表即恢复原状，无运行时影响。后续里程碑在第 11
  节各带回滚。
- **不可回退点。** M0 没有。M3 的字段删除是第一个不可逆步骤，逐个门控。

## 9. 验证与验收

| 声明 | 测试或证据 | 要求结果 | 边界 / 排除 |
| --- | --- | --- | --- |
| 基线上注册表与代码一致 | `python3 examples/control_plane/semantic-vocabulary-drift-smoke.py` | `ok` 并输出预算报告 | 只证明已注册词表的一致性 |
| 扩宽 `effective_action` 集合时失败关闭 | 在某个生产者加一个未注册字面量后运行 smoke | 失败文本命名该值与文件 | 突变练习；非提交测试 |
| 分叉 schema 常量时失败关闭 | 在非 owner 模块重定义 `TURN_ENVELOPE_SCHEMA_VERSION` | 失败列出多出的定义模块 | 同上 |
| Python 与 TypeScript 结果种类不能分叉 | 从 `TURN_RESULT_KINDS` 删一项后运行 smoke | 失败命名缺失的值 | 同上 |
| 删除重复常量不改变行为 | `pytest tests/test_loopx_turn_transaction.py tests/test_loop_turn_loop_controller.py tests/test_turn_loop_disposition.py tests/test_loopx_turn_managed_step.py` 与 `loopx canary premerge --from-git-diff` | 通过 | 在干净树上可复现的 `main` 既有环境失败除外 |
| 文档治理接受这对 RFC | `python3 examples/docs-governance-smoke.py` | 通过 | 检查镜像、链接、索引 |

## 10. 运维契约

该检查不可能影响运行中的系统：它只在 premerge 与 CI 中执行。其操作者界面就是
失败文本。不适用可观测性、容量或值班契约。

## 11. 规范性交付计划

| 里程碑 | 交付行为 | 进入门 | 退出证据 | 回滚 |
| --- | --- | --- | --- | --- |
| M0 | 注册表、漂移 smoke、删除重复的 `TURN_ENVELOPE_SCHEMA_VERSION`、RFC 索引条目 | 本 RFC 开启 | 第 9 节第 1-6 行全绿 | 删除 smoke 与注册表 |
| M1 | 单一 owner 模块中的 `EffectiveAction` 类型化枚举；生产者与消费者 import 它；注册表 `literal_scan` 收紧到枚举 | M0 合入；owner 模块已定（Q3） | smoke 绿；owner 之外零裸 `effective_action` 字面量；status/should-run 的 parity fixture 不变 | 回退为字面量；注册表保留集合 |
| M2 | route 到 disposition 的投影与结果种类通过共享契约发布，生成 Python 与 TypeScript 绑定，效仿协调契约生成器 | M1 合入；Q2 已决 | 生成器 `--check` 与 smoke 绿；`settlement.ts` 与 `transaction.py` 读取生成集合 | 从上一版契约重新生成 |
| M3 | 逐字段退休旧 should-run 字段，每个 PR 一个字段，预算降到零并删除字段 | 经生产者/读者调研证明该字段外部读者为零 | 按 `AGENTS.md` 的 schema 缩减记录；附录 B 条目 | 从最后一个写方恢复字段 |
| M4 | 随迁移 RFC 的每次 replacement-first 切换调低孪生预算 | 每个切换 PR | 同 diff 中的预算修改 | 无需；预算跟随代码 |

## 12. 未决决策

1. **注册表位置。** Owner：内核维护者。选项：`loopx/control_plane/`（与事务契约
   同处，推荐，符合共享契约先例）或 `docs/reference/`。M1 前需定。
2. **是否合并 `LoopXTurnRoute` 与 `LoopDisposition`？** Owner：Turn driver owner。
   投影是全射但非单射（`blocked` 与 `wait` 都映到 `wait`），而 `stop`、
   `terminal`、`contract_error` 只在一侧存在。建议：两者都保留，M2 发布投影，
   待 managed-step 消费者成熟后再议。M2 前需定。
3. **`EffectiveAction` 的 owner 模块。** 选项：`quota/should_run_packet.py`
   （最大生产者）、新建 `quota/effective_action.py`，或按迁移 RFC 以 TypeScript
   `turn_envelope.ts` 为 owner 并生成 Python 绑定。建议：若 M2 先落地则以
   TypeScript 为 owner 并生成 Python 绑定；否则新建 `quota/effective_action.py`。
   M1 前需定。
4. **伴随术语表。** 是否新增 `docs/reference/glossary.md`，从注册表的 `meaning`
   字段生成，列出每个注册词表的含义并链接拥有它的协议文档。建议：是，在 M1
   生成以免漂移。Owner：文档维护者。
5. **词族命名规则。** `gate`、`scope`、`packet`、`handoff`、`settlement` 词族中的
   新标识符是否必须在评审中引用术语表条目。这是评审规则而非 smoke；建议在
   术语表存在后纳入 first-review roster。

---

## 附录 A：执行账本（非规范）

### 2026-09-15 — 随 RFC 开启 M0

- **基线：** `1dc6ad8d8`
- **交付：** 含四个词表、一个投影、一个 schema 版本、六个旧字段预算、一个孪生
  预算的注册表；漂移 smoke；`driver.py` 中重复的 `TURN_ENVELOPE_SCHEMA_VERSION`
  改为 import。
- **证据：** 第 9 节各行；见附录 C。
- **已知缺口：** 投影检查在 M2 发布之前导入私有的 `_route_to_disposition`。
- **对规范设计的影响：** 无。

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
| E5 | 九个漂移突变全部失败关闭（含数字与不含数字的未注册字面量、分叉常量、删除 TS 种类、扩宽 Python 枚举、改投影、旧字段回涨、注册表死值、新 py/ts 孪生） | `1dc6ad8d8` + 本地改动，每次运行后恢复 | 临时改动后以 `python3 -B` 运行 smoke | 9/9 退出码 1 并命名违规值或文件 | 本地练习，非提交测试；同尺寸同秒改写需 `-B` 绕过过期字节码 |

## 附录 D：被否决或取代的方案

见第 6 节。单 PR 合并枚举被否决，因为三套枚举变化原因不同；可重开该决策的证据
是 M2 之后投影被证明为双射。

## 附录 E：事故与评审教训

- 跨运行时手工同步的平行常量列表在其中一侧改变之前总能通过评审；接受第二份
  副本之前必须先有一致性检查。
- 在大模块里私有抽一份共享常量看起来无害，却是 schema 版本分叉最常见的方式。
- 只接受 `[a-z_]` 的字面量扫描在 M0 突变练习中悄悄放过了 `_v2` 拼法。应捕获
  所有带引号字符串并单独校验形状，让畸形值被报告而非被忽略。
