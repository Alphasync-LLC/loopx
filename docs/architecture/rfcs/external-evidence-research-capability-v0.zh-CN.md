# RFC：外部证据研究能力 v0

- 状态：Draft implementation slice
- 范围：provider-neutral 的研究规划、provenance 准入、投影与退休
- 路线图：S8 能力与领域集成
- 语言说明：本文件与英文版语义镜像；语义漂移属于缺陷。

## 问题

LoopX 已有 host 研究方法、connector 库存、provider 生命周期、managed Turn 合同和
下游证据消费者，但它们仍是分散的。一条 registry 记录可以显示 `supported`，却不能
证明 provider 已安装、已启用、ready、被真实调用或被父 Agent 采纳。反过来，host
研究方法也可能产出高质量证据，但没有可供其他 LoopX caller 检查的类型化回执。

产品需要的是一个结果能力，而不是通用 connector executor：把面向决策的研究问题
转换成 provenance、准入、消费与退休均可观察的紧凑证据。

## 决策

新增 `external-evidence-research` capability，协议为
`external_evidence_research_v0`，生命周期为：

`discover → select → provider execute → provenance receipt → parent admit/reject → downstream projection → retire`。

请求必须声明对象、用户活动、决策、证据类型与约束。只有当前读回同时证明
`declared`、`installed`、`enabled`、`ready` 的 provider 才能被选择。provider
分为 `method` 与 `connector`；执行仍归各自既有 owner。

回执绑定精确请求、已选 provider、完成时间与完整回执 digest。每条被采纳来源都包含直接且非文件型引用、来源
家族、证据基础（`stated`、`observed`、`tested` 或 `inferred`）、发现、局限、相关
日期和内容摘要。Core 投影永不携带 provider 原始内容。

父 Agent 必须显式采纳或拒绝。拒绝后可以退休；采纳后必须等下游读回覆盖全部被采纳
source ref，才能退休。

## 所有权与 TypeScript 迁移

本切片遵循 TypeScript 迁移 RFC，但不宣称整个控制面已 promote。纯类型化决策由
TypeScript 拥有，并通过既有 effect runtime 暴露；Python 仅拥有 CLI 参数、本地 JSON
输入与 transport。本 PR 不删除现有 connector 路径，也不建立第二份持久权威。

Connector registry 继续只拥有库存与遥测。`supported` 绝不映射为 `ready=true`；只有
显式 provider 生命周期观察，才可覆盖同 provider id 的 inventory-only 行。

## 产品入口

- CLI：`external-evidence plan|admit|retire`；
- Managed Turn：复用同三个 effect-runtime 方法；
- Frontend/Lark：本 Core 切片不修改。后续 companion slice 只渲染同源 plan/admission
  投影与读回，不建立第二个 registry 或生命周期。

## 验收

- inventory-only connector 不可被选择；
- method 与 connector provider 使用同一协议与回执；
- 过期请求/provider 身份、文件 provenance、未知证据基础均 fail closed；
- 被采纳 source ref 必须是回执来源的子集；
- 全部被采纳来源完成下游覆盖前不得退休；
- CLI 与 effect-runtime TypeScript 测试在源码 checkout 中通过。

## 非目标

- 通用浏览器或搜索引擎；
- provider 凭据存储；
- 原始页面/逐字稿持久化；
- 自动采纳证据；
- 交易、发布或其他下游 effect 权限；
- 把注册或使用计数当作证据质量证明。
