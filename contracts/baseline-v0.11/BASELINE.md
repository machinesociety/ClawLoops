# ClawLoops 冻结基线（baseline-v0.11）

冻结目标：把 **字段、状态机、错误码、接口边界** 在 “Authentik 首版接入 + Runtime V1 冻结 + 无真实邮箱用户友好” 前提下定死，避免联调阶段口径漂移。

- **基线版本**：v0.11-no-real-email-friendly
- **冻结日期**：2026-03-25
- **权威来源（v0.11）**：`docs/后端/MVP_Contract.md`、`docs/后端/Architecture_Design.md`、`docs/后端/API_Spec.md`、`docs/后端/AUTHENTIK_Implementation_Guide.md`、`docs/前端/页面调用流程_BFF编排.md`、`docs/前端/UI_状态模型.md`
- **单一真相源**：本目录内 JSON 冻结物为准（Markdown 仅解释）

本目录冻结物：

- `enums.json`：枚举唯一真相源
- `errors.json`：错误码注册表
- `user_runtime_binding.schema.json`：`UserRuntimeBinding` JSON Schema
- `invitation.schema.json`：`Invitation` JSON Schema（v0.11 新增冻结对象）
- `api-boundary.json`：接口边界与禁止字段规则

## v0.11 新增冻结重点

- 管理员初始化口径统一按 **`akadmin`**（角色真相，不是用户名必须叫 admin）
- invitation 双层模型 + **延迟创建**（平台 token 为业务真相，Authentik itoken 仅为身份执行引用）
- `POST /api/v1/auth/post-login` 作为 **幂等收口入口**（前端主动调用，不依赖前端 body 传 pendingSession）
- `/api/v1/auth/access` **永远返回 200**，仅用于状态判断（disabled 返回 allowed=false + reason=USER_DISABLED）
- `admin` 登录后默认进入 `/admin`；普通用户登录后默认进入 `/app`
- `/workspace-entry` 作为 **唯一工作区跳转裁决接口**，前端只在 `ready=true` 时跳 `browserUrl`
- runtime V1 冻结：固定镜像、固定命令、固定网络 `clawloops_shared`、固定 alias、固定端口 `18789`、RM internal API **同步执行**，并且 RM `ensure-running` 请求体 **删除 `imageRef`** 且 `compat` 必填

## 兼容性规则

- 允许：新增可选字段/错误码/枚举值，但不得改变既有语义
- 禁止：字段重命名、语义改写、删除字段、把 `desiredState/observedState` 合并
- 禁止：把 `browserUrl/internalEndpoint` 合并为单字段

## Changelog

- v0.11（2026-03-25）：引入 Invitation 冻结对象；统一 akadmin 口径；补齐无真实邮箱用户友好字段；强化 `/admin/home`、`/app` 默认落点与 `workspace-entry` 唯一跳转裁决；收敛 runtime V1 与 RM internal contract。

