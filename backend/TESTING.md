## 概览

本文件说明如何在本地运行 ClawLoops 后端的自动化测试（`pytest`），以及如何基于《MVP 开发基线总契约》《平台设计文档》《统一总接口》执行一套端到端（E2E）验收测试。

目录结构（后端部分）：

- 代码根目录：`backend/`
- 测试目录：`backend/tests/`
  - `tests/api/`：面向 HTTP API 的集成测试
  - `tests/services/`：领域服务与编排服务测试
  - `tests/core/`：认证等核心逻辑测试
  - `tests/repositories/`：仓储层测试

---

## 一、自动化测试（pytest）

### 1. 运行环境准备

- **Python 版本**：>= 3.11（见 `pyproject.toml`）。
- **依赖安装**（推荐在虚拟环境中执行）：

  ```bash
  cd backend
  python -m venv .venv
  source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate

  # 安装应用依赖
  pip install -e .

  # 安装测试依赖（pytest）
  pip install pytest
  ```

- **数据库 / 外部服务依赖**：
  - 默认情况下，`app.core.settings.AppSettings.database_url` 为空时，数据库回退为本地 SQLite 文件：`sqlite:///./clawloops.db`。
  - 目前 `tests/conftest.py` 使用的是内存版用户仓储和 runtime binding 仓储，大部分 API 测试不依赖真实外部数据库/服务即可运行。
  - 若后续引入真实 DB 或外部服务，可以通过环境变量覆盖：
    - `CLAWLOOPS_DATABASE_URL`
    - `CLAWLOOPS_RUNTIME_MANAGER_BASE_URL`
    - `CLAWLOOPS_MODEL_GATEWAY_BASE_URL`

### 2. 一次性跑完所有后端测试

在 `backend/` 目录下执行：

```bash
cd backend
pytest
```

说明：

- 默认会发现并运行 `backend/tests/` 下所有以 `test_*.py` 命名的用例。
- 若想限制在某个子目录，例如只跑 API 层测试：

  ```bash
  pytest tests/api
  ```

- 若只跑某个单文件（调试失败用例时常用）：

  ```bash
  pytest tests/api/test_workspace_entry_api.py
  ```

### 3. 提升输出详细度 / 并行执行

- **详细输出**：

  ```bash
  pytest -vv
  ```

- **失败后快速重试**：pytest 会在 `.pytest_cache` 中记录上一次失败的用例，可使用：

  ```bash
  pytest --last-failed
  ```

- **并行执行**（若自行安装了 `pytest-xdist`）：

  ```bash
  pip install pytest-xdist
  pytest -n auto
  ```

### 4. 常见问题与排查

- **问题：模块导入失败（如 `ModuleNotFoundError: app.core...`）**
  - 确保在 `backend/` 目录内执行 `pytest`，并且已经使用 `pip install -e .` 安装了本地包。

- **问题：SQLite 文件/权限问题**
  - 默认 SQLite 文件为 `backend/clawloops.db`，确认当前用户对该目录有读写权限，必要时删除旧文件重新生成。

- **问题：环境变量缺失**
  - 如果未来某些测试依赖外部服务 URL，可通过设置 `CLAWLOOPS_*` 环境变量来覆盖默认配置。

---

## 二、端到端验收测试大纲（基于契约/架构/API）

本节基于：

- 《MVP 开发基线总契约》（`MVP_Contract.md`）
- 《平台设计文档》（`Architecture_Design.md`）
- 《MVP 统一总接口》（`API_Spec.md`）

建议使用 Postman / Bruno / Thunder Client / curl / HTTPie 等工具执行。

### 1. 用户旅程与模块映射

1. **首次登录并创建用户（模块 1 → 模块 2）**
2. **启动 runtime 并进入工作区（模块 3 → runtime manager → Traefik/Auth）**
3. **查看模型列表与默认模型（模块 4）**
4. **用户自有凭据托管与验证（模块 4）**
5. **查看用量摘要（模块 4 → usage summary）**
6. **管理后台治理（模块 5：用户列表/详情、禁用、runtime 查看与治理）**

### 2. 核心 API 场景清单

#### 场景 A：身份与访问控制

- **接口**：
  - `GET /api/v1/auth/me`
  - `GET /api/v1/auth/access`
- **正向用例**（active 用户）：
  - 前置：带上 `X-Authentik-Subject` 请求头。
  - 期望：
    - `/auth/me` 返回 `userId / subjectId / tenantId / role / isAdmin / isDisabled` 等字段。
    - `/auth/access` 返回允许访问业务的标志（具体 shape 以实现为准）。
- **负向用例**：
  - 未带认证头 / 无登录上下文：受保护接口返回 `401 UNAUTHENTICATED`。
  - disabled 用户（见场景 F）：除 `/auth/me` 外业务接口统一返回 `403 USER_DISABLED`。

#### 场景 B：runtime 生命周期（创建 / 启动 / 查询 / 删除）

- **接口**：
  - `GET /api/v1/users/me/runtime`
  - `GET /api/v1/users/me/runtime/status`
  - `POST /api/v1/users/me/runtime/start`
  - `POST /api/v1/users/me/runtime/stop`
  - `DELETE /api/v1/users/me/runtime`
  - `GET /api/v1/runtime/tasks/{taskId}`
- **步骤示例（首次启动 happy path）**：
  1. `POST /internal/users/sync`（内部）确保用户存在。
  2. 用户带认证头调用 `POST /api/v1/users/me/runtime/start`。
     - 期望：HTTP `202 Accepted`，body 至少包含 `taskId / action=ensure_running / status=accepted`。
  3. 轮询 `GET /api/v1/runtime/tasks/{taskId}`。
     - 期望：`status` 在 `pending / running / succeeded / failed / canceled` 内。
  4. 调 `GET /api/v1/users/me/runtime/status`。
     - 期望：返回 `runtimeId / desiredState / observedState / ready / browserUrl / reason / lastError`。
  5. 调 `GET /api/v1/users/me/runtime`。
     - 期望：返回完整 `UserRuntimeBinding` 快照（不含 `internalEndpoint`）。
- **删除与保留策略**：
  - `DELETE /api/v1/users/me/runtime` 时可在 body 中指定 `retentionPolicy`。
  - 未指定时应使用 binding 中的 `retentionPolicy`，默认 `preserve_workspace`。

#### 场景 C：工作区入口（workspace entry）

- **接口**：
  - `GET /api/v1/workspace-entry`
- **步骤与断言**：
  1. 在无 binding 情况下调用：
     - 期望：`ready=false`，`runtimeId=null`，`browserUrl=null`，`reason="runtime_not_found"`。
  2. 在 binding 存在但 `observedState=stopped` 时：
     - 期望：`ready=false`，`reason="runtime_not_running"`。
  3. 在 `desiredState=running, observedState=creating` 时：
     - 期望：`ready=false`，`reason="runtime_starting"`。
  4. 在 `observedState=running` 且 `browserUrl` 非空时：
     - 期望：`ready=true`，返回非空 `browserUrl`，`reason=null`。
  5. 在 `observedState=error` 且有 `lastError` 时：
     - 期望：`ready=false`，`reason="runtime_error"`。

> 说明：`browserUrl` 只是浏览器入口地址；实际访问仍需经过 Traefik + Authentik 前置鉴权（平台外部可通过访问该 URL 验证 302 / 认证流程是否符合预期）。

#### 场景 D：模型与凭据闭环

- **接口**：
  - `GET /api/v1/models`
  - `GET /api/v1/models/bindings`
  - `GET /api/v1/credentials`
  - `POST /api/v1/credentials`
  - `POST /api/v1/credentials/{credentialId}/verify`
  - `DELETE /api/v1/credentials/{credentialId}`
  - `PUT /api/v1/models/{modelId}/binding`
  - `GET /api/v1/usage/summary`
- **正向用例**：
  1. `GET /models`：
     - 期望：返回一个 `models` 数组，元素带有 `model_id / source / enabled` 等。
  2. `POST /credentials` 创建凭据：
     - 请求体：`{ "name": "default-openai", "secret": "sk-..." }`
     - 期望：`201 Created`，返回包含 `credential_id` 的对象，不返回明文 `secret`。
  3. `GET /credentials`：
     - 期望：列表中能看到刚创建的凭据元数据。
  4. `POST /credentials/{credentialId}/verify`：
     - 期望：返回 `verified / status / lastValidatedAt`。
  5. `PUT /models/{modelId}/binding`：
     - 请求体：`{ "credential_id": "<上一步的 credential_id>" }`
     - 期望：返回 `bindings` 数组，其中包含该模型与该凭据的绑定。
  6. `GET /models/bindings`：
     - 期望：可以看到模型到凭据的绑定关系。
  7. `GET /usage/summary`：
     - 期望：返回 `user_id` 与 `total_tokens` 等字段。

#### 场景 E：管理后台治理（admin）

- **接口**：
  - `GET /api/v1/admin/users`
  - `GET /api/v1/admin/users/{userId}`
  - `PATCH /api/v1/admin/users/{userId}/status`
  - `GET /api/v1/admin/users/{userId}/runtime`
  - `GET /api/v1/admin/users/{userId}/credentials`
  - `GET /api/v1/admin/models`
  - `GET /api/v1/admin/usage/summary`
- **关键点**：
  - 非 admin 访问 `/api/v1/admin/*` 应返回 `403 ACCESS_DENIED`。
  - admin 访问用户列表/详情应能看到：
    - 用户基础信息（`userId / subjectId / tenantId / role / status / createdAt / updatedAt`）
    - runtime 概况（`desiredState / observedState / browserUrl / internalEndpoint / retentionPolicy / lastError`）。
  - admin 修改 `status` 为 `disabled` 后：
    - binding 的 `desiredState` 应收敛为 `stopped`；
    - runtime manager 的 `stop` 被调用（可在日志或监控中观察）；
    - 前台业务接口（如 `/api/v1/users/me/quota`）应立即返回 `403 USER_DISABLED`。

#### 场景 F：错误码与边界条件

结合错误码表（`API_Spec.md` 第 2 章 & 第 8 章），验证：

- 未登录访问受保护接口返回 `401 UNAUTHENTICATED`。
- disabled 用户访问除 `/auth/me` 外接口返回 `403 USER_DISABLED`。
- 访问不存在的用户 / runtime / 模型 / 凭据：
  - 返回 `404 USER_NOT_FOUND / RUNTIME_NOT_FOUND / MODEL_NOT_FOUND / CREDENTIAL_NOT_FOUND`。
- 在 runtime 正忙或状态冲突时：
  - 返回 `409 RUNTIME_ACTION_CONFLICT`。

---

## 三、现有自动化测试与验收场景的映射

下面是部分关键测试文件与上文场景的对应关系，便于理解当前自动化覆盖面：

- **`tests/api/test_module6_full_smoke_flow.py`**
  - 覆盖：从同步用户、ensure binding、启动 runtime、查询任务、查询 runtime/status 到获取 `/workspace-entry` 的主 happy path。
  - 对应上文：场景 B（runtime 生命周期）+ 场景 C（工作区入口） + 部分场景 A（身份接入）。

- **`tests/api/test_workspace_entry_api.py`**
  - 覆盖：`/workspace-entry` 在无 binding、stopped、creating、running、error 等多种状态组合下的行为与 `reason` 字段。
  - 对应上文：场景 C（工作区入口）。

- **`tests/api/test_runtime_integration.py`**
  - 覆盖：模块 1/2 同步用户与绑定、模块 3 启动 runtime，验证 runtime manager 调用 payload 与 binding 状态回写、runtime 任务查询。
  - 对应上文：场景 B（runtime 生命周期）以及内部编排链路。

- **`tests/api/test_models_credentials_usage_api.py`**
  - 覆盖：获取模型列表、创建凭据、绑定模型、查询用量摘要等完整闭环。
  - 对应上文：场景 D（模型与凭据闭环）。

- **`tests/api/test_admin_module5.py`、`tests/api/test_admin_smoke_governance.py`**
  - 覆盖：admin 权限控制、用户列表/详情、用户状态修改（禁用后前台 `USER_DISABLED`）、禁用时 runtime 收敛与 runtime manager 停止调用。
  - 对应上文：场景 E（管理后台治理）+ 场景 F（部分错误码）。

- **`tests/api/test_disabled_user_access.py`**
  - 覆盖：disabled 用户访问业务接口返回 `403 USER_DISABLED`，验证禁用语义收口。
  - 对应上文：场景 F（错误码与边界条件）。

> 总体上，核心 API 行为和治理语义已经有较完整的自动化覆盖；真实 Traefik/Auth 前置鉴权与浏览器跳转行为目前主要仍依赖部署环境中的人工验收（通过访问 `browserUrl` 实际验证认证流程）。

---

## 四、推荐的“完整测试”执行顺序

1. **启动依赖**
   - 若仅跑当前后端自动化测试：通常无需额外服务，默认 SQLite 即可。
   - 若部署在完整环境下进行 E2E 验收：确保数据库、LiteLLM 网关、runtime manager、Traefik、Authentik 等服务已按部署文档启动。

2. **运行自动化测试（后端）**

   ```bash
   cd backend
   source .venv/bin/activate  # 若使用虚拟环境
   pytest -vv
   ```

3. **执行端到端验收场景**
   - 按“二、端到端验收测试大纲”中的场景 A–F 逐一执行：
     - 使用固定用户身份（通过 `X-Authentik-Subject` 头）模拟不同角色与状态。
     - 记录每个场景的通过/失败情况和备注。

4. **（可选）整理为团队统一 checklist**
   - 可将上述步骤整理为团队通用的 QA checklist，或导出为 Postman Collection / 脚本化的 E2E 测试。

