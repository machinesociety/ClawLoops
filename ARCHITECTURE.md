# Architecture

## Goal

OpenClaw is a self-hosted team platform for running OpenClaw with multi-user access, per-user isolated runtimes, a unified model gateway, private workspaces, and future shared spaces.


## System overview

At a high level, ClawLoops separates browser access, platform control, runtime orchestration, and model access.

```text
Browser
  |
  v
Traefik -> Authentik -> ClawLoops Control Plane -> Runtime Orchestrator -> Runtime Manager -> Per-user OpenClaw Runtime
                                      |
                                      +-> Model Service / Credential Proxy -> LiteLLM -> vLLM / Ollama / upstream providers
                                      |
                                      +-> PostgreSQL
```

### Core layers

| Layer               | Components                              | Responsibilities                                             |
| ------------------- | --------------------------------------- | ------------------------------------------------------------ |
| Entry layer         | Traefik + Authentik                     | External routing, login, session verification, subdomain protection |
| Platform layer      | ClawLoops control plane + minimal web UI | User sync, runtime truth, admin governance, workspace entry  |
| Orchestration layer | Runtime orchestrator + runtime manager  | Desired state reconciliation, config rendering, container lifecycle |
| Runtime layer       | Per-user OpenClaw runtime               | User workspace, local profiles, state, agent runtime         |
| Model layer         | LiteLLM + PostgreSQL + vLLM/Ollama      | Unified model access, default models, credential proxying, usage aggregation |

## Key design decisions

### One runtime per user

In MVP, each user can have at most one runtime. This keeps lifecycle management, routing, storage mapping, and quota enforcement simple.

### Container-level isolation, not a hardened sandbox

ClawLoops uses one runtime container per user. This is a practical isolation boundary for MVP, but it should not be described as a hardened security sandbox.

### Separate browser and internal addresses

ClawLoops intentionally splits user-facing and internal runtime addresses:

- `browserUrl`: the browser entry point exposed through Traefik
- `internalEndpoint`: the internal service address used by the platform and runtime manager

These must never be collapsed back into a single generic `endpoint` field.

### Workspace URLs are still authenticated

Knowing a workspace URL does not grant access.

All workspace subdomains go through Traefik and Authentik before traffic reaches a runtime. A valid session, an active user state, and a valid user-to-runtime binding are all required before forwarding is allowed.

### Runtime configuration is injected at startup

The platform renders the runtime model configuration file and gateway secret file before container startup. The runtime manager then mounts them read-only into the runtime container.

This means:

- the runtime does not fetch raw platform secrets by itself
- the browser does not receive gateway configuration
- upstream provider API keys are not exposed directly to the browser

### Platform service does not directly own Docker socket operations

In production architecture, the main platform service does not directly create, stop, or delete containers. Those responsibilities belong to the runtime manager.

## Design Principles
- Keep the platform simple to deploy.
- Keep user runtimes isolated.
- Keep model access unified.
- Keep private space and shared space separated.
- Add new capabilities without weakening the security boundary.
