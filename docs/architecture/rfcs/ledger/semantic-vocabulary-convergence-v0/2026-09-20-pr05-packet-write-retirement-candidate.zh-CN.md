# PR-05：protocol action packet 写入退休候选

对应 [#4794](https://github.com/loopx-project/loopx/pull/4794)、
[#4447](https://github.com/loopx-project/loopx/issues/4447)。
[协议决定](../../../../reference/protocols/protocol-action-packet-decision-v0.md)
拥有迁移契约。发布版本和历史支持范围仍待确认；本条不授予迁移批准、不关闭 tracker。

- **交付变化。** 删除四个 quota 模块内六个现行写入点，以及失去调用者的 packet
  builder/import。普通、暂停、required-read、capability-intent、host-recovery
  路径使用现有类型化契约。默认完整 decision 也不再输出旧字段，不只是 compact
  view 省略。未新增 flag、schema 词表或决策 owner。
- **保留责任。** Python Markdown 和 TS Effect/Envelope 的历史 reader、
  `protocol_action_packet_fields` 有序语义投影、summary 重建、opaque fallback、
  residue 和签名拒绝仍保留，不重写旧记录。实测 Python 字段迁移面由 5 降为 1，
  TypeScript 仍为 2；同 diff 锚点保留这些兼容 reader，不虚报字段全仓消失。
- **行为证据。** 八组完整新旧 quota payload 只去除 packet 后相等；规范签名文档
  只去除 capsule 中对应见证后相等，摘要值可能因此变化。真实 CLI/重入/Envelope/
  live 测试 149 项通过。更名后的 `quota-without-legacy-packet-smoke.py` 会拒绝旧
  默认输出；原 decision-note 文案 smoke 退役，行为由实际运行和兼容回归保护，
  文档结构继续由 docs governance 校验。
- **版本化读回。** 实际 v1.1.0 源码 `607c11d75` 读取八组新输出和八组带 packet 的
  基线样本，签名含义与 host admission 均通过。安装后的候选 wheel 验证普通/暂停
  输出、打包 TS/JSON 资源、真实 bridge 与 host admission。这是有界合成证据，
  不代表完整历史存档或全部 host 资格已验证。
- **剩余决定。** 发布前确认输出版本、支持的历史格式/窗口、外部消费者范围和
  回退承诺，不默认未知外部 reader 兼容。评审状态与测试通过须分开；交叠的 quota
  构建 PR 仍需在实际集成提交上协调验证。
