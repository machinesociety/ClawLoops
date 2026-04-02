# CrewClaw 一键启动（Ubuntu）

## 用法

在仓库目录执行：

```bash
bash oneclick/start-crewclaw.sh
```

或指定仓库路径：

```bash
bash /path/to/CrewClaw/oneclick/start-crewclaw.sh /path/to/CrewClaw
```

## 脚本做了什么

- 自动检测并安装 Docker + Docker Compose plugin（Ubuntu）。
- 自动启动 Docker 服务并校验可用。
- 自动识别服务器主 IP，并更新 `infra/compose/.env`：
  - `CLAWLOOPS_DOMAIN=clawloops.<IP>.nip.io`
  - `RUNTIME_MANAGER_DOMAIN=runtime-manager.<IP>.nip.io`
  - `RUNTIME_PUBLIC_HOST=<IP>`
- 尝试更新 `infra/traefik/dynamic/middlewares.yml` 中的旧 IP（若存在）。
- 执行 `docker compose up -d --build` 拉起服务。

## 重要说明

- 你必须在 `infra/compose/.env` 里填好 `DASHSCOPE_API_KEY`，否则 LiteLLM 调用 DashScope 会返回 500。
- OpenClaw 运行时通过“宿主机随机端口”暴露（例如 `:32801`）。若你从公网访问服务器，需要在安全组/防火墙放通对应端口范围，或改造为走 80/443 的反向代理方案。
