# CrewClaw 本地开发：Authentik 配置指南（中文）

完整架构与冻结边界另见仓库内 **`docs/后端/AUTHENTIK_Implementation_Guide.md`**（若该文件为 root 所有且无法直接编辑，可将 `infra/authentik/AUTHENTIK_Group_Mapping.zh-CN.md` 中表格合并进主文档 §11.4）。

---

## 1. 与本项目相关的变量（节选）

在 `infra/compose/.env` 中（示例见 `infra/compose/.env.example`）：

| 变量 | 典型值 | 说明 |
|------|--------|------|
| `CLAWLOOPS_DOMAIN` | `clawloops.localhost` | 主站与 API 的 Host |
| `AUTHENTIK_OUTPOST_TOKEN` | 在 Authentik 管理界面生成 | 与 `authentik-proxy-outpost` 的 `AUTHENTIK_TOKEN` 一致 |
| `AUTHENTIK_PUBLIC_URL` | `http://localhost:9000` | 浏览器访问 Authentik 的根 URL，写入 Outpost 的 `AUTHENTIK_HOST_BROWSER` |
| **`CLAWLOOPS_AUTH_ADMIN_GROUP_SLUGS`** | `clawloops-admins,authentik Admins` | 与 IdP 组名字符串**完全一致**（逗号分隔）；默认含内置 **`authentik Admins`** 与业务组 **`clawloops-admins`** |

本机 `/etc/hosts` 至少包含：`127.0.0.1 clawloops.localhost runtime-manager.clawloops.localhost`。

---

## 2. 推荐启动顺序（摘要）

1. 启动 `authentik-postgresql`、`authentik-redis`、`authentik-server`、`authentik-worker`
2. 完成 Authentik 向导与 **Proxy Provider + Outpost**，将 **Outpost Token** 写入 `AUTHENTIK_OUTPOST_TOKEN`
3. 启动 `authentik-proxy-outpost`、`traefik`、`clawloops-api`、`clawloops-web`、`runtime-manager`

Traefik ForwardAuth、`/outpost.goauthentik.io/` 路由与 `middlewares.yml` 说明见主仓库 `infra/authentik/README.md` 与 `infra/traefik/dynamic/middlewares.yml`。

---

## 9. 用户与应用内角色（管理员）— Authentik Groups 映射（推荐）

**ClawLoops 应用内 `role=admin` / `isAdmin=true`** 由后端根据 **Authentik 经 Traefik 下发的 `X-Authentik-Groups`** 与 `CLAWLOOPS_AUTH_ADMIN_GROUP_SLUGS` 决定，**不是**「Authentik 安装向导里的超级用户」自动等价。

### 9.1 Authentik 侧

1. 若使用 **仅内置** 管理员：用户只需在 **`authentik Admins`** 组内（与默认 `CLAWLOOPS_AUTH_ADMIN_GROUP_SLUGS` 中的名称一致即可）。
2. 若使用 **业务组**：在 Authentik 中创建 Group（如 **`clawloops-admins`**），名称与 `CLAWLOOPS_AUTH_ADMIN_GROUP_SLUGS` 中某项**完全一致**，并将用户加入该组。

### 9.2 ClawLoops 侧

在 `infra/compose/.env` 中设置（`clawloops-api` 容器已透传该变量）：

```env
CLAWLOOPS_AUTH_ADMIN_GROUP_SLUGS=clawloops-admins,authentik Admins
```

### 9.3 同步规则（与实现一致）

| 请求是否带 `X-Authentik-Groups` | 行为 |
|----------------------------------|------|
| **未带**（头不存在） | **不修改** 用户已持久化的 `role`（便于直连 API、测试、无 Outpost 场景） |
| **已带**（含空字符串） | 按组同步：组名命中任一管理员组 → `admin`；否则 → `user`（**可能降级**） |

### 9.4 验证

已登录时访问：`GET http://clawloops.localhost/api/v1/auth/me`，用户加入 `clawloops-admins` 后应返回 `role=admin`、`isAdmin=true`。

---

## 附：`docs/后端` 主文档合并说明

若需更新 **`docs/后端/AUTHENTIK_Implementation_Guide.md`** §11.4，请手动将 **`infra/authentik/AUTHENTIK_Group_Mapping.zh-CN.md`** 中的表格并入 §11.4「推荐规则」之后（当前仓库中该路径下部分文件可能为 root 所有，自动化工具可能无法直接写入）。
