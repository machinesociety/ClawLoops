# ClawLoops 冻结基线（baseline-v0.3）

冻结目标：把 **字段、状态机、错误码、接口边界** 定死，后续任何改动必须遵守“兼容性规则/变更流程”，避免反复返工。

- **基线版本**：v0.3
- **冻结日期**：2026-03-13
- **权威来源（本次已对齐 v0.3）**：`/workspace/MVP_Contract.md`、`/workspace/Architecture_Design.md`、`/workspace/API_Spec.md`
- **单一真相源**：本目录内的 JSON 冻结物为准（Markdown 仅做解释与索引）

本目录冻结物：

- `enums.json`：枚举唯一真相源
- `errors.json`：错误码注册表
- `user_runtime_binding.schema.json`：`UserRuntimeBinding` JSON Schema
- `api-boundary.json`：接口边界与禁止字段规则

## 1. 全局字段与命名约定（冻结）

### 1.1 全局标识字段（冻结）

- **userId**：平台内部用户唯一标识，例如 `u_001`
- **subjectId**：外部身份唯一标识，例如 `authentik:12345`
- **tenantId**：租户标识；MVP 固定 `t_default`
- **role**：`user / admin`（见 `enums.json`）

### 1.2 禁止命名漂移（冻结）

禁止把以下字段随意改名（任何重命名都视为破坏性变更）：

- `userId` 不得改为 `uid`
- `runtimeId` 不得改为 `containerId`
- `browserUrl` / `internalEndpoint` 不得合并回单一 `endpoint`
- `desiredState` / `observedState` 不得合并回单一 `status`

## 2. 核心对象：UserRuntimeBinding（冻结）

### 2.1 结构冻结

`UserRuntimeBinding` 必须遵守 `user_runtime_binding.schema.json`。

关键语义（冻结）：

- **desiredState**：平台目标状态（见 `enums.json` 的 `runtime.desiredState`）
- **observedState**：宿主机观测状态（见 `enums.json` 的 `runtime.observedState`）
- **browserUrl**：用户/浏览器唯一入口；**仅表示入口，不代表匿名可访问**（仍需 Traefik + Authentik 前置鉴权）
- **internalEndpoint**：平台内部服务访问地址；**禁止**对普通用户侧暴露
- **retentionPolicy**：删除语义（见 `enums.json`），MVP 默认 `preserve_workspace`
- **lastError**：最近一次编排失败信息（用于前端/后台展示）

### 2.2 首次 binding 初始化职责（冻结）

首次创建/分配 `runtimeId / volumeId / default imageRef / default retentionPolicy` 的唯一入口：

- `POST /internal/users/{userId}/runtime-binding/ensure`（由“模块 2：租户与用户资源控制”提供）

冻结禁止项：

- 模块 3（编排层）不得自行生成 `runtimeId/volumeId/default imageRef`

## 3. 枚举与状态机（冻结）

所有枚举以 `enums.json` 为唯一真相源；任何枚举增删改都必须走变更流程。

### 3.1 用户状态机（冻结）

- `user.status = active | disabled`
- 语义：disabled 用户“可识别身份”，但业务能力统一收口（见第 5 章）

### 3.2 runtime 状态机（冻结）

- `desiredState = running | stopped | deleted`
- `observedState = creating | running | stopped | error | deleted`

约束（冻结）：

- 不允许把二者合并成单一字段

### 3.3 任务状态机（冻结）

- `task.action = ensure_running | stop | delete`
- `task.status = pending | running | succeeded | failed | canceled`
- 异步动作：runtime 启停删返回 `202 + taskId`，前端用 `GET /api/v1/runtime/tasks/{taskId}` 轮询

## 4. 错误码（冻结）

错误码注册表以 `errors.json` 为准；控制面、后端实现与三份叙述文档中的错误码表述必须与本文件保持一致。

强约束（冻结）：

- 未登录：`401 UNAUTHENTICATED`
- 权限不足：`403 ACCESS_DENIED`
- **用户禁用**：`403 USER_DISABLED`（全局收口，见 `api-boundary.json`）
- 平台 provider 凭据不存在：`404 PROVIDER_CREDENTIAL_NOT_FOUND`
- 平台 provider 凭据不可用：`422 PROVIDER_CREDENTIAL_INVALID`

## 5. 接口边界（冻结）

接口边界规则以 `api-boundary.json` 为准。

### 5.1 `/users/me/runtime` vs `/users/me/runtime/status`（冻结）

- **GET `/api/v1/users/me/runtime`**：完整 binding 快照（用于详情/删除确认/排障）；不建议高频轮询
- **GET `/api/v1/users/me/runtime/status`**：轻量投影（用于高频轮询）；禁止返回 `volumeId/imageRef/retentionPolicy`

### 5.2 地址字段边界（冻结）

- 前端/浏览器 **只能** 使用 `browserUrl`
- `internalEndpoint` 仅 internal/admin 场景可见，用户侧响应 **禁止出现**

### 5.3 disabled 用户语义（冻结）

除 `GET /api/v1/auth/me` 外：disabled 用户访问业务接口统一返回 `403 USER_DISABLED`，不得再用 `ready=false` 的变体绕开收口。`/api/v1/auth/access` 与 `/api/v1/users/me/quota` 同样视为业务接口，必须遵守该收口规则。

### 5.4 provider 凭据治理边界（冻结）

- 普通用户不再提供 `/api/v1/models/bindings`、`/api/v1/models/{modelId}/binding`、`/api/v1/credentials*` 等自服务接口。
- 平台 provider 凭据仅通过管理员侧接口管理（参见 `API_Spec.md` 中的 admin/provider-credentials 接口），错误码以 `PROVIDER_CREDENTIAL_*` 系列为准。

## 6. 兼容性规则与变更流程（冻结后的唯一改法）

### 6.1 允许的向后兼容变更（不破坏 v0.3）

- 新增 **可选** 字段（不得改变既有字段语义）
- 新增错误码（不得改变既有错误码语义）
- 新增枚举值（需评估前端与状态机影响；不得复用旧值含义）

### 6.2 禁止的破坏性变更（必须新开基线版本）

- 字段重命名、删除字段、改变字段类型/语义、把可空改为必填
- 改变 `USER_DISABLED` 的全局收口语义
- 合并/重构 `desiredState/observedState`、合并 `browserUrl/internalEndpoint`
- 让模块 3 或前端发号（破坏“binding 首建归口”）

### 6.3 变更步骤（强制）

1. **先改本目录 JSON 冻结物**（`enums.json/errors.json/*schema.json/api-boundary.json`）
2. 再同步更新三份叙述文档（仅解释与引用）
3. 在本文件底部 Changelog 追加一条记录

## 7. Changelog

- v0.2（2026-03-12）：冻结字段/状态机/错误码/API 边界（首次基线）
- v0.3（2026-03-13）：对齐三份 v0.3 文档版本；收紧为“用户只用不配”；调整 provider 凭据错误码命名和禁用语义适用接口列表。

