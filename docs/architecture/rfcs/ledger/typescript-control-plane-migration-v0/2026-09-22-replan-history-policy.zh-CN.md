# Replan 历史决策归属

目标来源为总纲 #4574 与 T3 消费侧 TS 迁移。原有 Python 历史扫描分别处理重试、
ACK、中性记账及 agent 归属，规则已经分叉。本次统一到一次
`work_item.replan_history.project` 请求，并在 TS 内直接复用 Todo resume planner。
Python 保留历史解码、指纹及 obligation 呈现；删除被替代的触发扫描和重复词表。

基线 `709734cd6` 上独立编写的四个反例失败：周期复盘重复累计重试、监控重复
累计重试、ACK 未截断进展停滞、记账打断同质进展。新实现修复这些问题，保持
阈值、优先级和 obligation 标识。280 行多 agent 交错 fixture 与边界负例验证
先归属后 ACK、重试、无效身份、输入拒绝及不修改源数据。File/SQLite 消费侧测试
使用真实持久化 provider，删除展示文件后读取状态并执行 quota CLI。

本机只读演练覆盖 345 条活动 Todo、600 条历史记录和五个 agent：五个历史投影
与基线一致，隔离 File/SQLite 读后核对及公开 quota CLI 通过，活动源未修改。
该证据仅限活动读模型，不证明完整 Goal 晋升。独立的完整捕获因归档依赖缺少或
不兼容的 role/task-class 事实而拒绝；这个迁移阻塞保留，没有绕过门禁或改写活动状态。

本次闭合历史触发决策族，不代表全部 T3 或默认切换。进展指纹解码、obligation
组装、frontier 结算及完整捕获资格仍有各自归属。没有加入模型观察器、provider
切换、前端配置项或可选 capability。
