# PR-05：protocol action packet 新写退休候选

为 [PR #4794](https://github.com/huangruiteng/loopx/pull/4794) 准备的候选迁移合同，
Refs [#4447](https://github.com/huangruiteng/loopx/issues/4447)。本条目不批准发布，
也不关闭 tracker。具体迁移与验收要求由
[协议决策](../../../../reference/protocols/protocol-action-packet-decision-v0.md) 承载。

- **缺口与本次交付。** 公开引用仍要求直接消费 packet，并在每份完整 decision 中
  保留它。五份引用现已区分历史 v0 契约与候选的新 quota/live/paused/recovery
  输出不携带 packet 的行为。现行消费者使用 typed interaction、lane、scheduler
  contracts；不新增 capability、flag 或权限。
- **保留边界。** 保留历史 packet reader、opaque summary、residue、
  `protocol_action_packet_fields`、历史 summary renderer 和签名校验，不重写旧记录。
  新 source 可以少一个 capsule packet witness；source/envelope 一致并不承诺
  与旧 packet-bearing source 的 hash 相同。
- **证据限制。** PR #4794 的合成 absent/v0/opaque/residue fixtures 覆盖指定的
  Python/TypeScript reader 与权限检查，不代表完整历史 archive、未知外部消费者
  或回退当前 1.1.0 reader 已获验证。runtime 写入删除与 producer/display smoke
  更新属于配套实现，不属于本文档切片；集成后仍须验证实际新输出不带 packet。
- **文档切片验证。** 文档治理检查、29 项焦点 Python 测试与 5 项 TypeScript
  兼容测试通过。现有 protocol decision smoke 在旧文案断言处失败，旧章节顺序
  断言也须随配套实现更新。本切片未实测 1.1.0 降级。
- **发布与回退仍待确定。** 用户/maintainer 须在发布前绑定公开输出版本标记与
  历史支持窗口；不承诺日期或支持年限。必须以新输出和保留的历史记录实测
  1.1.0 reader，才能声明降级兼容；回退 producer 本身不能证明这项兼容。
- **有界后续。** 将要求旧 “Keep” 与默认完整 payload 文案的 smoke 改为验证迁移
  边界。现有 semantic projection 与历史读取边界足以承载本切片，无需新增兼容框架。
