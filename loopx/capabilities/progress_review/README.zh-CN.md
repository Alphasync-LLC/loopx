# 进展评估哨兵

[English](README.md)

进展评估哨兵让一个 Goal 消费**类型化的漂移回执**。回执由一个可选的、外部的、有界评估器在每次捕获到的工作转换后写入。能力默认关闭。`shadow` 模式下核心只记录和展示回执；`assist` 模式下，连续若干条已完成的漂移回执会变成**已有的** `autonomous_replan_obligation`，除此之外不改变任何行为。

它要补的是现有类型化重复保险丝按构造看不见的一种情形：Agent 每轮自报 `advanced`、每轮更换 `hypothesis_id`、测试始终全绿，但限定文件的实际变化只是改名和调整字段顺序。今天这类工作只能在 20 条 durable run 之后由周期复审兜底发现。

## 核心做什么、不做什么

| 核心会 | 核心不会 |
| --- | --- |
| 只通过一个严格 schema `progress_review_receipt_v0` 读取回执 | 调用模型、读取原始 diff、导入观察器包 |
| 按 `turn_instance_id` 关联 run 行，缺失时退回 `(generated_at, agent_id)` | 覆盖或补充 Agent 自己的 `progress_observation` |
| 只计入状态为 `completed` 且所选漂移信号为 `True` 的回执 | 把 `unknown`、`abstained`、`failed`、`stale` 或缺失的回执算作漂移 |
| 在已确认的自主重规划处停止计数并重新武装 | 暂停 Turn、打开 user gate、判定 Goal 验收 |
| 要求被计数的回执共享同一个 Goal 契约修订 | 让契约变化前的回执继续生效 |

类型化重复保险丝保持优先。只有它沉默时，回执连续段才会补充证据。

## 策略

```bash
loopx configure-goal --goal-id <goal-id> --progress-review-mode shadow --execute
loopx configure-goal --goal-id <goal-id> --progress-review-mode assist \
  --progress-review-signal noul --progress-review-drift-threshold 2 --execute
loopx configure-goal --goal-id <goal-id> --clear-progress-review-configuration --execute
```

| 字段 | 取值 | 含义 |
| --- | --- | --- |
| `mode` | `off`、`shadow`、`assist` | `off` 不加载任何内容；`shadow` 记录并展示；`assist` 可以触发义务 |
| `signal` | `noul`、`choice` | 哪一组判断算作漂移 |
| `drift_threshold` | 2–20 | 触发义务前需要的连续已完成漂移回执数 |

策略保存在 Goal 注册表的 `control_plane.progress_review`，可在 `loopx configure-goal --goal-id <goal-id>` 输出的 `feature_summary` 和 Dashboard 能力编辑器中看到。格式错误的配置块会安全地退回 `off`。

## 回执

回执由可选的 `loopx-jev-pilot` 发行版中的观察器写入 `<runtime-root>/goals/<goal-id>/progress-review/receipts/<event-id>.json`（见 [`packages/loopx-jev/DRIFT_SHADOW.zh-CN.md`](../../../packages/loopx-jev/DRIFT_SHADOW.zh-CN.md)）。每条回执只包含类型化字段：

- 身份：`goal_id`、`event_id`、`evidence_id`、`contract_revision`、`sequence`，以及 run 的 `turn_instance_id`、`generated_at`、`agent_id`、`todo_id`；
- `status`：`completed`、`abstained`、`failed`、`not_evaluated`、`stale`；
- `judgments.choice`：`relation` 与 `increment` 标签或 null；
- `judgments.noul`：`behavior_change`、`serves_acceptance`、`evidence_increment` 的概率或 null；
- `drift_signal.noul`、`drift_signal.choice`：`true`、`false` 或 null；
- `timing_ns`、`usage`、`label_probability_threshold`、`recorded_at`。

漂移信号由观察器按其配置的标签阈值 `t` 推导：

- `noul`：`P(behavior_change) ≤ 1−t` **且** `P(serves_acceptance) ≤ 1−t` 为漂移；任一概率 `≥ t` 为非漂移；其余为 null。
- `choice`：`relation = off_goal` **且** `increment = no_new_evidence` 为漂移；`on_goal`、`necessary_prerequisite` 或 `new_evidence` 为非漂移；其余为 null。

因此，服务于验收条件的纯文档或纯测试工作在两种信号下都不算漂移。

## 你会看到什么

只要策略不是 `off`，`loopx status --format json` 会在 Goal 条目及其 `project_asset` 中增加 `external_progress_review`：按状态统计的回执数、按信号统计的漂移数，以及最新回执的类型化判断。`assist` 模式下，满足条件的连续段表现为一个 `autonomous_replan_obligation`，其 trigger 的 `kind` 为 `external_progress_review_drift`，`frontier_identity` 为 `progress_review:<evidence-id>`，附带一条 P1 todo 动作以及一贯的 `required: true`、`stop_condition` 和 ack 契约。心跳提示词已经要求 Agent 遵守该义务并用类型化重规划确认。

## 验证差异

`packages/loopx-jev` 附带对照命令：

```bash
loopx-jev sentinel compare \
  --matrix packages/loopx-jev/tests/fixtures/sentinel/matrix.json \
  --responses packages/loopx-jev/tests/fixtures/sentinel/responses \
  --output /tmp/sentinel-comparison.json
```

它对每个录制序列报告：类型化重复保险丝首次触发的轮次（对自报 advanced 的序列在序列内永不触发）、每种回执信号首次标记漂移的轮次，以及 gold 标注为 on-goal 的序列上的误报。不加 `--live` 时回放已提交的 provider 响应，因此 CI 无需 key 即可复现数字。`python3 examples/progress-review-sentinel-smoke.py` 运行同一回放。

## 录制对照结果

16 序列矩阵的已提交 live 录制（`jev-1.13.0`，35 轮，每轮自报 `advanced`）：

| | 类型化重复保险丝 | `noul` 回执 | `choice` 回执 |
| --- | --- | --- | --- |
| 在 gold 轮或之后标记的漂移序列 | 0/9 | 6/9 | 4/9 |
| 阈值 2 下达到 `assist` 义务 | 0/9 | 6/9 | 1/9 |
| 真实 on-goal 上游提交被误报 | 0/7 | 0/7 | 0/7 |

6 个纯装饰性序列全部在第 1 轮被标记、第 2 轮即可触发义务，而周期复审要等 20 条 durable run。真实实现落地后对同一文件的装饰性改动未被标记；一次已执行的负结果探测在三次 live 中有两次被标记。完整表格、延迟与波动见[操作指南](../../../packages/loopx-jev/DRIFT_SHADOW.zh-CN.md)。

## 边界与下一步

升级（义务被忽略后打开 user gate）与暂停仍是未来工作，本能力不授予。观察器的预测质量与本集成是两个独立问题：先让一个 Goal 运行在 `shadow`，用 `loopx-jev drift label` 标注回执，比较首次告警轮次后再开启 `assist`。
