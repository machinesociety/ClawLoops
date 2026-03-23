# ClawLoops 冻结基线（baseline-v0.8）

冻结目标：把 **字段、状态机、错误码、接口边界** 在 Authentik 首版接入与 runtime V1 冻结语义下定死，避免开发阶段口径漂移。

- **基线版本**：v0.8
- **冻结日期**：2026-03-23
- **权威来源（v0.8）**：`/workspace/MVP_Contract.md`、`/workspace/Architecture_Design.md`、`/workspace/API_Spec.md`、`/workspace/AUTHENTIK_Implementation_Guide.md`
- **单一真相源**：本目录内 JSON 冻结物为准（Markdown 仅解释）

本目录冻结物：

- `enums.json`：枚举唯一真相源
- `errors.json`：错误码注册表
- `user_runtime_binding.schema.json`：`UserRuntimeBinding` JSON Schema
- `api-boundary.json`：接口边界与禁止字段规则

## v0.8 新增冻结重点

- invitation 双层模型与延迟创建
- `POST /api/v1/auth/post-login` 幂等收口
- `/api/v1/auth/access` 永远返回 `200`（状态判断接口）
- `workspace-entry` 作为唯一跳转入口，前端只在 `ready=true` 时跳转
- RuntimeManager internal 接口同步执行，`taskId` 只存在于 Orchestrator 对外层
- runtime V1 固定网络、固定端口、固定 alias、`compat` 必填

## 兼容性规则

- 允许：新增可选字段/错误码/枚举值，但不得改变既有语义
- 禁止：字段重命名、语义改写、删除字段、把 `desiredState/observedState` 合并
- 禁止：把 `browserUrl/internalEndpoint` 合并为单字段

## Changelog

- v0.8（2026-03-23）：引入 invitation/post-login/runtime manager 同步边界与 runtime V1 冻结规则，统一 Authentik 首版口径。
