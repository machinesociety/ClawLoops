# Authentik Groups → ClawLoops 应用管理员（§11.4 合并用表格）

将以下内容合并到 **`docs/后端/AUTHENTIK_Implementation_Guide.md`** 的 §11.4「推荐规则」与「### 11.5」之间。

---

**ClawLoops 实现约定（与代码一致）：**

| 配置 / 环境变量 | 说明 |
|----------------|------|
| `CLAWLOOPS_AUTH_ADMIN_GROUP_SLUGS` | 逗号分隔的 Authentik **Group 名称**，须与 `X-Authentik-Groups` / JWT 中字符串完全一致；默认含 `clawloops-admins` 与内置组 **`authentik Admins`**（akadmin 常见） |
| `CLAWLOOPS_AUTH_HEADER_GROUPS` | 读取组列表的请求头名，默认 `X-Authentik-Groups` |

| `X-Authentik-Groups` / JWT | 行为 |
|---------------------------|------|
| **有** `X-Authentik-Groups`（含空字符串 `""`） | 按逗号解析；命中管理员组则 `ADMIN`，否则 `USER`（**会降级**） |
| **无** `X-Authentik-Groups` 头，但有 **`X-authentik-jwt`** 且 payload 含 **`groups`** | 从 JWT 解析组名，规则同上 |
| **无** 组头且 **无** 可解析的 JWT `groups` | **不修改** 已存储的 `role`（直连 API、测试、无 Outpost 场景） |

**Authentik 运维：** 在 Directory 中创建 Group（如 `clawloops-admins`），将用户加入该组；Traefik 已声明透传 `X-authentik-groups` 与 `X-authentik-jwt`（见 `infra/traefik/dynamic/middlewares.yml`）。若线上只出现 JWT、无独立组头，依赖上表 **JWT 回退**。

**代码落点：** `apps/clawloops-api/app/core/auth.py`、`apps/clawloops-api/app/core/authentik_groups.py`
