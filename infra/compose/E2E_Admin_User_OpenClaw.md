# 管理员到用户 OpenClaw 端到端联调（半自动）

## 前置条件

- 已在 `infra/compose/.env` 中配置基础变量。
- 已启动 compose：`docker compose --env-file .env -f docker-compose.yml up -d --build`
- 已完成 Authentik 初始配置（可通过 `http://localhost:9000/if/admin/` 登录）。

## 一键半自动联调

在仓库根目录执行：

```bash
chmod +x scripts/e2e_admin_user_openclaw.sh
./scripts/e2e_admin_user_openclaw.sh
```

脚本会完成：

1. 同步 admin 与 user 用户主体
2. 为 user 确保 runtime binding
3. 触发 runtime/start
4. 轮询任务状态
5. 验证宿主机存在运行中的 `rt-<runtimeId>` 容器

## 浏览器关键验证步骤

1. 管理员登录 Authentik：`http://localhost:9000/if/admin/`
2. 打开 ClawLoops：`http://clawloops.localhost`
3. 使用用户账号登录后，进入工作区入口页面
4. 在工作区入口确认可进入对应 OpenClaw

## 常见问题

- `RUNTIME_START_FAILED`：先检查 `crewclaw-runtime-manager` 日志和 Docker socket 挂载。
- 看不到 `rt-<runtimeId>` 容器：确认 runtime-manager 已挂载 `/var/run/docker.sock` 与 `/var/lib/clawloops`。
- `clawloops.localhost` 无法访问：优先检查 `crewclaw-traefik` 日志与本机 hosts 解析。
