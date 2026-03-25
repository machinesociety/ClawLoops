# Authentik Integration Notes

This folder stores local integration config for official Authentik images.

**Full setup (wizard, Proxy Provider, Outpost, token, verification):** [AUTHENTIK_SETUP.zh-CN.md](./AUTHENTIK_SETUP.zh-CN.md)（中文）。

**Authentik Groups → ClawLoops 应用管理员（方案 C，合并主文档 §11.4 用）：** [AUTHENTIK_Group_Mapping.zh-CN.md](./AUTHENTIK_Group_Mapping.zh-CN.md)。

## Version pinning

- Authentik server/worker/proxy image tag is pinned by `AUTHENTIK_VERSION` in `.env`.
- Do not use `latest` in production.

## Bootstrap flow

1. Copy `.env.example` to `infra/compose/.env` and fill secure values.
2. Run `docker compose --env-file .env -f docker-compose.yml up -d authentik-postgresql authentik-redis authentik-server authentik-worker`.
3. Open Authentik initial setup and create admin account.
4. Create Proxy Provider + Outpost, then put token into `AUTHENTIK_OUTPOST_TOKEN`.
5. Start `authentik-proxy-outpost` and Traefik.
