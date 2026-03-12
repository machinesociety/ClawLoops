# CrewClaw
<img width="1328" height="1328" alt="image" src="https://github.com/user-attachments/assets/3baf28c2-53a8-4f79-96c3-527c36631f7b" />

## 项目介绍 

* **CrewClaw** 是一个基于容器化技术的智能员工管理平台。  
* **核心安全：** 为每一位人类员工分配一个专属的、隔离的容器，实现“一人一容器”的极致隔离与安全保障。  
* **全局掌控：** 通过可视化的管理后台，管理者可以像查阅地图一样掌控全局，将原本不可见的 AI 协作过程转化为可监控、可审计、可复用的企业资产。

## 项目亮点

* 🛡️ 一人一容器
    * 每位员工拥有独立的沙箱环境，数据互不干扰，杜绝隐私泄露。  
    * 根据员工负载自动伸缩计算资源，闲时休眠，忙时爆发。  
    * 员工的“数字分身”状态实时保存，随时唤醒，无缝接续工作。  

* 透明管理后台  
告别黑盒操作，CrewClaw 提供全链路可视化管理控制台  

  *  🗺️ 实时监控地图  
        像查看交通地图一样，直观看到所有“龙虾”的在线状态（绿色/红色）。  
        实时显示 CPU、内存及网络资源占用率，快速定位性能瓶颈。
     
  * 📜 全量审计日志
        记录每一次关键操作：文件修改、代码提交、外部 API 调用、Prompt 输入输出。  
        满足企业级合规要求（GDPR/SOC2），让每一次 AI 决策都有据可查。
     
  * 📦 技能市场  
        标准化封装：将通用业务逻辑（如“查询 CRM”、“生成周报”、“竞品分析”）封装为标准“技能包”。  
        一键分发：管理员可将技能包一键推送至全员或特定部门，实现知识的高效复用与沉淀。  
        版本管理：支持技能包的迭代更新与回滚，确保业务逻辑的一致性。  

## 项目架构
- 统一入口：Traefik，采用子域名路由，把浏览器入口和内部服务地址分开管理。
- 统一认证：Authentik，平台负责会话鉴权与身份上下文注入。
- 平台层：控制面 API + 极简 Web UI，负责用户、状态、资源真相与管理后台。
- 运行时：每用户一个 OpenClaw runtime 容器。
- 生命周期管理：独立 runtime manager /provisioner，负责容器创建、停止、删除、挂载与状态查询。
- 模型网关：LiteLLM + PostgreSQL，统一接公司模型、本地模型和用户自有凭据。
- 本地模型：vLLM 为主，Ollama 作为补充。
- 密钥管理：MVP 使用 secret file 注入；后续可接 OpenBao。

| 层级     | 核心组件                               | 职责                                                         |
| -------- | -------------------------------------- | ------------------------------------------------------------ |
| 入口层   | Traefik + Authentik                    | 统一外部访问、登录、会话识别与转发。                         |
| 平台层   | CrewClaw 控制面                        | 用户同步、UserRuntimeBinding 管理、管理后台、工作台。        |
| 编排层   | Runtime Orchestrator + Runtime Manager | 将 desiredState 落为容器实际状态。                           |
| 运行时层 | Per-user OpenClaw runtime              | 用户自己的 workspace、state、auth profiles 与 agent runtime。 |
| 模型层   | LiteLLM + PostgreSQL + vLLM/Ollama     | 统一模型出口、默认模型、凭据代理与 usage 归集。              |

<img width="1039" height="1079" alt="image" src="https://github.com/user-attachments/assets/809b74a9-fb36-4c79-814f-5a405d5b18e0" />

## 快速开始
```markdown
```bash
# 1. 克隆仓库
git clone https://github.com/your-org/crewclaw.git
cd crewclaw

# 2. 启动核心服务
docker-compose up -d

# 3. 初始化管理员账户
./bin/crewclaw init-admin --username admin --password <your_secure_password>
