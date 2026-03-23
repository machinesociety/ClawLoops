# ClawLoops

> 🧠 The Control Plane for Team-based OpenClaw Workspaces

ClawLoops is an open-source platform that enables teams to **securely provision, manage, and scale OpenClaw workspaces per user**, with a clean separation between control plane, runtime orchestration, and runtime environments.

Built for teams—not just individuals.

---

## ✨ Why ClawLoops?

OpenClaw is powerful, but running it for a **team** introduces real challenges:

* How do you manage **multiple users and workspaces**?
* How do you isolate environments per user?
* How do you handle **invitation flows, roles, and permissions**?
* How do you securely expose runtime UIs?
* How do you scale runtime lifecycle (start/stop/recover)?

ClawLoops solves all of this.

---

## 🧩 Architecture Overview

ClawLoops follows a **boundary-first architecture**: browser ingress, identity, control plane, runtime orchestration, per-user runtimes, and a unified model layer are kept distinct.

At a high level:

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

### Layers

| Layer | Components | Role |
| ----- | ---------- | ---- |
| Entry | Traefik + Authentik | Routing, login, session verification, subdomain protection |
| Platform | ClawLoops control plane + web UI | User sync, runtime truth, admin governance, workspace entry |
| Orchestration | Runtime orchestrator + runtime manager | Desired-state reconciliation, config rendering, container lifecycle |
| Runtime | Per-user OpenClaw runtime | User workspace, profiles, agent runtime |
| Model | LiteLLM + PostgreSQL + vLLM/Ollama | Unified model access, credential proxying, usage aggregation |

**Key design notes** (MVP): one runtime per user; `browserUrl` (user-facing) and `internalEndpoint` (platform/internal) stay separate; workspace URLs remain authenticated via Traefik/Authentik; the control plane does not directly operate the Docker socket—container lifecycle belongs to the runtime manager.

For the full picture, see [ARCHITECTURE.md](ARCHITECTURE.md).

### 1. Control Plane (ClawLoops)

* User / Workspace / Role management
* Invitation system
* Runtime lifecycle as *business truth*
* Integration with Authentik (identity)
* Admin + User dashboard

### 2. Runtime Orchestration (RuntimeManager)

* Create / start / stop / delete runtimes
* Container lifecycle management
* Health checks & state reporting
* Stateless execution layer

### 3. Runtime Environment (OpenClaw Docker)

* Per-user isolated runtime
* Mounted workspace
* Browser-accessible UI

```
User → ClawLoops → RuntimeManager → Runtime (OpenClaw)
```

---

## 🚀 Key Features

### 🏢 Team-first Design

* Multi-user, multi-workspace support
* Role-based access control
* Invitation-driven onboarding

### 🔐 Secure by Default

* Authentik integration
* Traefik + Outpost routing
* Per-runtime isolation

### ⚙️ Runtime Lifecycle Control

* Declarative runtime state
* Auto-recovery & status sync
* Retention policies

### 🌐 Browser-based Access

* Each runtime exposes a secure UI
* External & internal endpoints

### 🧱 Clean Architecture

* Control plane ≠ runtime ≠ orchestration
* Fully decoupled layers

---

## 📦 Repositories

This project is composed of multiple repos:

### 🧠 clawloops (this repo)

> The control plane

* API server
* Admin / user dashboard
* Business logic (users, workspaces, invitations)
* Runtime lifecycle truth

---

### ⚙️ runtimemanager

> Runtime orchestration engine

* Handles runtime creation and lifecycle
* Reports runtime status back to ClawLoops
* Can run standalone or via Docker

---

### 🐳 openclaw-docker

> Reference runtime image

* Standard OpenClaw runtime environment
* Preconfigured for ClawLoops integration

---

## 📚 Documentation

| Document | Description |
| -------- | ----------- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System layers, MVP design decisions, security boundaries |
| [ROADMAP.md](ROADMAP.md) | Versioned milestones (v0.1–v0.5) and long-term direction |
| [MVP_Contract.md](MVP_Contract.md) | MVP module boundaries, field enums, and integration contract (Chinese) |

---

## 🛠️ Quick Start

> ⚠️ Full setup docs coming soon

### Prerequisites

* Docker
* Authentik
* Traefik (recommended)

### Run (conceptual)

```bash
# 1. Start ClawLoops
# 2. Start RuntimeManager
# 3. Deploy openclaw runtime image
```

More detailed setup guide coming soon.

---

## 🧪 Current Status

🚧 This project is under active development.

What’s stable:

* Core architecture boundaries
* Runtime lifecycle model
* Invitation system design

What’s evolving:

* RuntimeManager API
* Deployment tooling
* UI polish

---

## 🗺️ Roadmap

The detailed, milestone-based roadmap lives in **[ROADMAP.md](ROADMAP.md)**. Summary:

### v0.1 Foundation

* Multi-user login
* Per-user runtime containers
* Unified model gateway
* Minimal Web UI & admin view
* Private user workspace

### v0.2 Shared Space

* Team shared space model & permissions
* Shared space mounting in runtimes
* Basic shared space management UI

### v0.3 Local Model Support

* Stronger vLLM integration; Ollama as supplemental backend
* Admin-managed model availability & routing policies

### v0.4 Admin and Governance

* Richer admin console, user lifecycle, runtime inspection
* Usage visibility, basic audit, quotas & policy

### v0.5 Local Folder Connector

* Desktop connector; authorized local folder access with read/write controls
* Cross-platform (Windows, Linux, macOS)

### Long-term

* Stronger governance & auditability
* More deployment options & observability
* Flexible runtime backends & enterprise controls

---

## 💡 Design Principles

* **Separation of concerns first**
* **Control plane owns truth**
* **Runtime is disposable**
* **Stateless orchestration layer**
* **Security by default**

---

## 🤝 Contributing

We’re building this in the open.

If you are interested in:

* platform engineering
* runtime orchestration
* developer infra

Feel free to open issues or PRs.

---

## ⭐ Support the Project

If this project is useful to you:

* ⭐ Star the repo
* 🐦 Share it
* 🧪 Try it out and give feedback

---

## 📄 License

This project is licensed under the **Apache License, Version 2.0**.

See the [LICENSE](LICENSE) file in this repository. A copy of the license is also available at [https://www.apache.org/licenses/LICENSE-2.0](https://www.apache.org/licenses/LICENSE-2.0).

---

## 🔥 Vision

ClawLoops aims to become the **standard control plane for team-based AI workspaces**, starting with OpenClaw.

We are not just building a tool.

We are defining a **new way to run collaborative AI environments at scale**.

---

**中文说明**：简体中文 README 见 [README.zh-CN.md](README.zh-CN.md)。
