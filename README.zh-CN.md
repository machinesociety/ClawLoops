# ClawLoops

> 🧠 面向团队的 OpenClaw 工作区控制平面

ClawLoops 是一个开源平台，帮助团队**按用户安全地开通、管理与扩展 OpenClaw 工作区**，并在控制平面、运行时编排与运行时环境之间保持清晰边界。

为团队而生——而非仅限个人使用。

---

## ✨ 为什么选择 ClawLoops？

OpenClaw 能力强大，但面向**团队**落地时会遇到现实问题：

* 如何管理**多用户与多工作区**？
* 如何按用户隔离环境？
* 如何实现**邀请流程、角色与权限**？
* 如何安全暴露运行时 UI？
* 如何扩展运行时的生命周期（启停、恢复）？

ClawLoops 针对上述问题提供一体化方案。

---

## 🧩 架构概览

ClawLoops 采用**边界优先**的架构：浏览器入口、身份、控制平面、运行时编排、每用户运行时，以及统一模型层彼此分离。

高层数据流如下：

```text
Browser
  |
  v
Traefik -> Authentik -> ClawLoops 控制平面 -> 运行时编排器 -> Runtime Manager -> 每用户 OpenClaw 运行时
                                      |
                                      +-> 模型服务 / 凭据代理 -> LiteLLM -> vLLM / Ollama / 上游提供商
                                      |
                                      +-> PostgreSQL
```

### 分层说明

| 层级 | 组件 | 职责 |
| ---- | ---- | ---- |
| 入口层 | Traefik + Authentik | 路由、登录、会话校验、子域名保护 |
| 平台层 | ClawLoops 控制平面 + Web UI | 用户同步、运行时真相、管理治理、工作区入口 |
| 编排层 | 运行时编排器 + runtime manager | 期望状态对齐、配置渲染、容器生命周期 |
| 运行时层 | 每用户 OpenClaw 运行时 | 用户工作区、配置、智能体运行时 |
| 模型层 | LiteLLM + PostgreSQL + vLLM/Ollama | 统一模型访问、凭据代理、用量汇总 |

**MVP 设计要点**：每用户一个运行时；`browserUrl`（面向浏览器）与 `internalEndpoint`（平台/内部）字段分离、不可混用；工作区子域名仍须经 Traefik/Authentik 鉴权；控制平面不直接操作 Docker——容器生命周期由 runtime manager 负责。

完整说明见 [ARCHITECTURE.md](ARCHITECTURE.md)（英文）。

### 经典三段式理解

### 1. 控制平面（ClawLoops）

* 用户 / 工作区 / 角色管理
* 邀请体系
* 运行时生命周期作为**业务真相**
* 与 Authentik（身份）集成
* 管理端与用户端控制台

### 2. 运行时编排（RuntimeManager）

* 创建 / 启动 / 停止 / 删除运行时
* 容器生命周期管理
* 健康检查与状态上报
* 无状态执行层

### 3. 运行时环境（OpenClaw Docker）

* 每用户隔离的运行时
* 挂载工作区
* 浏览器可访问的 UI

```
用户 → ClawLoops → RuntimeManager → 运行时（OpenClaw）
```

---

## 🚀 主要特性

### 🏢 团队优先

* 多用户、多工作区
* 基于角色的访问控制
* 以邀请驱动的入驻流程

### 🔐 默认安全

* Authentik 集成
* Traefik + Outpost 路由
* 每运行时隔离

### ⚙️ 运行时生命周期

* 声明式运行时状态
* 自动恢复与状态同步
* 保留策略（retention）

### 🌐 浏览器访问

* 每个运行时暴露安全 UI
* 外网与内网端点分离

### 🧱 清晰架构

* 控制平面 ≠ 运行时 ≠ 编排层
* 各层解耦

---

## 📦 代码仓库

本项目由多个仓库组成：

### 🧠 clawloops（本仓库）

> 控制平面

* API 服务
* 管理端 / 用户端控制台
* 业务逻辑（用户、工作区、邀请）
* 运行时生命周期真相源

---

### ⚙️ runtimemanager

> 运行时编排引擎

* 负责运行时创建与全生命周期
* 向 ClawLoops 回传运行时状态
* 可独立运行或通过 Docker 部署

---

### 🐳 openclaw-docker

> 参考运行时镜像

* 标准 OpenClaw 运行时环境
* 预配置以对接 ClawLoops

---

## 📚 文档索引

| 文档 | 说明 |
| ---- | ---- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统分层、MVP 设计决策与安全边界（英文） |
| [ROADMAP.md](ROADMAP.md) | 版本里程碑（v0.1–v0.5）与长期方向（英文） |
| [MVP_Contract.md](MVP_Contract.md) | MVP 模块边界、字段枚举与联调契约（中文） |

英文总览见 [README.md](README.md)。

---

## 🛠️ 快速开始

> ⚠️ 完整部署文档即将补充

### 前置条件

* Docker
* Authentik
* Traefik（推荐）

### 运行（概念步骤）

```bash
# 1. 启动 ClawLoops
# 2. 启动 RuntimeManager
# 3. 部署 openclaw 运行时镜像
```

更细的部署指南即将发布。

---

## 🧪 当前状态

🚧 项目积极开发中。

相对稳定的部分：

* 核心架构边界
* 运行时生命周期模型
* 邀请体系设计

仍在演进的部分：

* RuntimeManager API
* 部署工具链
* UI 打磨

---

## 🗺️ 路线图

以 **[ROADMAP.md](ROADMAP.md)** 为准；此处为摘要：

### v0.1 基础能力

* 多用户登录
* 每用户运行时容器
* 统一模型网关
* 最小 Web UI 与管理视图
* 用户私有工作区

### v0.2 共享空间

* 团队共享空间模型与权限
* 运行时挂载共享空间
* 基础共享空间管理 UI

### v0.3 本地模型

* 与 vLLM 更深集成；Ollama 作为补充后端
* 管理员管理模型可用性与路由策略

### v0.4 管理与治理

* 更完善的管理台与用户生命周期
* 运行时排查与用量可见性、基础审计
* 配额与策略增强

### v0.5 本地文件夹连接器

* 桌面连接器设计与首版实现
* 用户授权下的本地目录读写控制
* 跨平台（Windows / Linux / macOS）

### 长期

* 更强的治理与可审计性
* 更多部署形态与可观测性
* 更灵活的运行时后端与企业级控制

---

## 💡 设计原则

* **优先分离关注点**
* **控制平面持有真相**
* **运行时可丢弃、可重建**
* **编排层无状态**
* **默认安全**

---

## 🤝 参与贡献

我们在开放协作中建设本项目。

若你关注：

* 平台工程
* 运行时编排
* 开发者基础设施

欢迎提交 Issue 与 Pull Request。

---

## ⭐ 支持项目

如果本项目对你有帮助：

* ⭐ 给仓库点 Star
* 🐦 转发分享
* 🧪 试用并反馈

---

## 📄 开源协议

本项目采用 **Apache License, Version 2.0**。

完整条款见仓库根目录下的 [LICENSE](LICENSE) 文件，亦可查阅 [https://www.apache.org/licenses/LICENSE-2.0](https://www.apache.org/licenses/LICENSE-2.0)。

---

## 🔥 愿景

ClawLoops 希望成为**团队级 AI 工作区的标准控制平面**，并从 OpenClaw 场景起步。

我们不仅在做一个工具，

更是在定义一种**规模化协作 AI 环境**的新方式。
