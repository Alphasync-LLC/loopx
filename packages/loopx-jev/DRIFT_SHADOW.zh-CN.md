# D1 限定范围的漂移旁路试点

[English](DRIFT_SHADOW.md)

本功能在真实 `refresh-state` 成功前后采集显式指定文件的变化，由**独立消费进程**调用 Jev，提供历史观察结果。它不会纠正、暂停、重新派发、确认完成或给 Agent 注入消息。集成测试通过不代表已经提高任务成功率或节省时间。

## 实现归属和接入范围

命令位于可选包 `loopx-jev-pilot`，产品入口只有 D1 shadow；没有排序代码、新的内置 capability 或调度器。输入来源明确标为 `scoped_checkpoint_capture`，不自称 Decision Context provider。[决策记录](DESIGN_DECISIONS.zh-CN.md)关联研究历史和证据限制。

现有 L1 `reliability-diagnostics` 的禁止出站、禁止影响 Agent 的契约保持独立，不能拿它的收据证明模型推理合格。本实现不修改它或 `state_refresh.py`，模型请求不会进入核心事务或核心写锁。

这是显式 CLI 接入：在真实刷新调用位置使用 wrapper，并单独运行消费者。原 `loopx refresh-state` 和原生 Codex/Claude 会话保持原行为。本分支没有自动 hook 安装、registry capability 设置、Dashboard 或 Lark 开关。配置绑定本地一个 Goal 观察目录，每个 Goal 应使用独立配置文件。操作者提供契约导出，这不自动证明规范 Goal 验收或工作区独占权。

## 操作方法

使用 Python 3.11+ 和 LoopX 检出要求的 Node 运行时。采集器目前面向 Linux/macOS 的 POSIX 文件处理；Windows 采集未验证，缺少所需文件原语时记录观察不可用。此可选发行包不进入 LoopX 默认 wheel；从源码根目录在新环境中安装，再执行不需要 key 的集成测试：

```bash
uv venv .venv-jev
uv pip install --python .venv-jev/bin/python -e '.[test]' -e packages/loopx-jev
.venv-jev/bin/python -m pytest packages/loopx-jev/tests/test_drift.py packages/loopx-jev/tests/test_drift_cli.py -q
.venv-jev/bin/loopx-jev drift --help
```

本切片只包含 D1，不提供 D2–D8 命令或排序代码。使用 `loopx_jev_drift_config_v0` 和 `minimum_label_probability`；旧多方向试点配置会被拒绝，不会静默提升。配置 key 本身不启用 shadow 或允许出站。失败时原 Agent 工作继续，不会自动启动独立 Agent 裁判。

为已有 Goal 创建被 Git 忽略的本地目录，复制 [config.shadow.json](examples/drift/config.shadow.json) 和 [basis.json](examples/drift/basis.json)。将示例 Goal id、目标、验收条件改为本次契约。可选 `evidence` 引用交付工作区中的常规文件，例如独立产生的测试报告；不要在配置或契约中填写密钥。默认 `allow_egress: false`，确认指定材料允许出站后再设为 true，并在**消费者的环境变量**中配置 `TYPESAFE_API_KEY`。

以下变量代表这个 Goal 已有的本地路径。在待观察的工作**开始之前**建立基线，使用独立交付工作区。每个 `--path` 是一个精确的相对文件路径，允许文件尚未创建，不支持目录或通配符。除了源码，应纳入相关测试和研究产物；不要纳入观察目录、可变 LoopX 状态或凭据。

```bash
loopx-jev drift init --state-dir "$OBSERVER" --config "$CONFIG" \
  --workspace "$WORKSPACE" --basis "$BASIS" \
  --path src/retry.py --path tests/test_retry.py

# 在原刷新调用位置使用，保留原有参数和绑定。
loopx-jev drift refresh --state-dir "$OBSERVER" --config "$CONFIG" -- \
  --registry "$REGISTRY" --runtime-root "$RUNTIME" refresh-state \
  --goal-id "$GOAL_ID" --format json

# 在另一个终端/进程中消费：执行一遍，或在指定时间内轮询。
loopx-jev drift drain --state-dir "$OBSERVER" --config "$CONFIG"
loopx-jev drift drain --state-dir "$OBSERVER" --config "$CONFIG" --watch-seconds 300
loopx-jev drift status --state-dir "$OBSERVER"

loopx-jev drift configure --state-dir "$OBSERVER" --mode off
loopx-jev drift configure --state-dir "$OBSERVER" --mode shadow
```

受管 Turn 必需的 Agent/Todo/Turn/validation 参数仍须完整传入，wrapper 不豁免原规则。它保留原命令 stdout 和退出码，在 stderr 输出简短采集结果。不传配置即关闭，不读取观察材料或 key，不导入传输模块；dry-run 不采集。核心写入成功但采集失败时，原命令仍成功，观察器记录失败并使基线失效。无效或未知输出不能当成观察成功。

通过 `configure` 关闭/开启：每次变更推进单调版本号，即使配置字节恢复原样，处理中结果仍失效。重新开启后的第一次刷新只重建基线。直接编辑配置会改变内容哈希，但在两次检查之间关闭又恢复原文件无法被检测；撤销请使用命令。目标契约变更也会重建基线。

卸载时恢复原 `loopx refresh-state` 调用，停止消费者，并在所选环境卸载 `loopx-jev-pilot`。本地证据按操作者留存策略删除；删除请求墓碑并建立新目录相当于显式开始新实验和新预算，不是透明续跑。

## 证据、去重和结果含义

- 比较前后检查点之间有效工作文件的净变化，包含期间已提交、已暂存、未暂存的文件变化，以及明确列出的未跟踪文件和可选证据文件；Git 只读。仅暂存区变化而工作文件相同，记为 `index_only_change_unknown`，不交给模型猜测。
- 模型输入同时包含前后检查点的限定文件内容，包括未改动文件，而不只有 delta；单看变动行通常无法理解新测试或实验。仍受整个请求字节上限约束，超限拒绝评估，不悄悄删去必要上下文。相同补丁作用于不同周边源码，使用不同的证据身份。
- 连续读取两次，并在刷新后再次核对；这不是文件系统原子快照或作者归属证明。应使用单写者 worktree。两次读取间改变后又恢复的内容、范围外工作仍不可见，不能靠 diff 证明整个任务的进展。
- 基线重建、无变化、重复事件和重复证据不调用模型。同一 Goal/Agent/Todo/Turn 的检查点补充去重；无 Turn 绑定时采用持久化 run 的摘要。同一契约下相同 delta 不算第二个独立观察；使用显式序号保留顺序，不依赖 JSON 键顺序。
- 排队材料是冻结的历史输入，之后工作区继续工作不使其失效；契约、配置版本、原记录更改或丢失会使其失效。历史结果没有对当前任务的控制权。
- 保留 `on_goal`、`necessary_prerequisite`、`off_goal`、`unknown`，以及独立的证据增量分类。必要测试、研究、负结果、文档都可能推进目标，不要求产生运行时行为变化；`no_new_evidence` 本身不是漂移结论。没有实现连续异常保险丝或自动升级复核。
- 无 key、禁止出站、过期输入、传输失败、弃权分别记录。请求不自动重试；即使详细结果被删除，请求预留仍保留，无法确定是否发出的请求不会再次发送。消费者崩溃后可复用已存的模型响应，不重复调用。

固定上限为 32 个文件、文件文本合计 32 KiB、可选证据文本 32 KiB、delta 32 KiB、16 个待消费观察、256 个事件身份。超限、二进制、符号链接输入拒绝处理，不截取后强行判断。初始化请求预算默认 20 次、最多 100 次，修改配置不能提升已初始化的预算。队列满时使基线失效并显示采集失败，不把漏掉的几轮悄悄算成一轮。

观察目录使用私有权限，JSON 文件权限为 0600。当前基线和待处理 job 包含原始限定材料，必须留在本地忽略目录；完成后删除 job 中的原始 delta，保留简短结果和请求墓碑。复用的凭据模式过滤只是辅助检查，不能保证任意源码都适合出站，仍需审查范围。

`status` 展示状态、判断、采集失败和客户端纳秒计时：采集准备、原命令、最终状态写入前的采集、评估及可用的传输/子进程阶段。父阶段包含子阶段，不能全部相加；缓存计时单独标记。这些不是服务端纯推理耗时，也不是 Agent 节省的时间。

## 仍需验证

测试覆盖真实 Git、真实 refresh CLI、关闭隔离、原权威记录不变、重放/重启、并发生产者、撤销、缺失/错误材料、队列预算，以及注入的未知/错误/模型响应。注入答案验证链路，不验证 Jev 准确率。

进入干预前，需要独立标注留出的多轮任务，对照原流程、Jev shadow 和独立 Agent 裁判，报告误报、漏报、弃权、提前发现时间及完整开销。只有另行授权的干预实验才能证明减少无效工作。监控 `material_change`、原生 hook、规范配置界面和自动纠正不在本次范围。
