# Customer Service Agent

一个基于 FastAPI 的智能客服多 Agent 系统，面向电商客服场景，支持订单查询、退款政策问答、工单创建与查询、合规审查等能力。

项目目标是模拟真实客服系统中的 Agent 编排流程：用户消息进入 `/chat` 接口后，由 Supervisor 统一调度多个业务 Agent，并通过工具层访问 mock 业务数据，最后经过合规审查后返回回复。

## 功能

- 意图识别：识别订单查询、退款政策、工单创建、工单查询、人工客服等意图
- 订单查询：根据 `user_id` 查询 mock 订单数据，避免越权查询其他用户订单
- 退款政策问答：基于本地知识库文件回答退款、退货、到账时效等问题
- 工单处理：支持创建投诉工单和查询最近工单状态
- 合规审查：支持手机号脱敏和高风险关键词识别
- 调用链追踪：通过 `trace` 字段展示一次请求经过的 Agent 和工具
- 自动化测试：使用 pytest 覆盖 Agent 和 Supervisor 主链路

## 架构

```text
User
 ↓
FastAPI /chat
 ↓
Supervisor
 ├── IntentAgent
 ├── OrderAgent
 │   └── OrderTools
 ├── RefundPolicyAgent
 │   └── KnowledgeBase
 ├── TicketAgent
 │   └── TicketTools
 └── ComplianceAgent
```

## 请求流程

订单查询流程：

```text
用户：我的订单什么时候到？
 ↓
ChatAPI
 ↓
Supervisor
 ↓
IntentAgent -> order_query
 ↓
OrderAgent
 ↓
OrderTools -> data/mock_orders.json
 ↓
ComplianceAgent
 ↓
返回订单状态和预计送达时间
```

退款政策流程：

```text
用户：怎么退款？
 ↓
IntentAgent -> refund_policy
 ↓
RefundPolicyAgent
 ↓
KnowledgeBase -> data/knowledge_base/refund_policy.md
 ↓
ComplianceAgent
 ↓
返回退款政策说明
```

工单流程：

```text
用户：我要投诉，商品坏了
 ↓
IntentAgent -> ticket_create
 ↓
TicketAgent
 ↓
TicketTools -> data/mock_tickets.json
 ↓
ComplianceAgent
 ↓
返回工单编号和处理状态
```

## 项目结构

```text
customer-service-agent/
├── app/
│   ├── api/
│   │   └── chat.py
│   ├── agents/
│   │   ├── supervisor.py
│   │   ├── intent_agent.py
│   │   ├── order_agent.py
│   │   ├── refund_policy_agent.py
│   │   ├── ticket_agent.py
│   │   └── compliance_agent.py
│   ├── tools/
│   │   ├── order_tools.py
│   │   ├── ticket_tools.py
│   │   └── kb_tools.py
│   ├── schemas/
│   │   ├── chat.py
│   │   ├── intent.py
│   │   └── compliance.py
│   └── main.py
├── data/
│   ├── mock_orders.json
│   ├── mock_tickets.json
│   └── knowledge_base/
│       └── refund_policy.md
├── tests/
├── requirements.txt
├── pytest.ini
└── README.md
```

## 快速开始

创建虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动服务：

```bash
uvicorn app.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok"}
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

## 接口示例

### 订单查询

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u_001","session_id":"s_001","message":"我的订单什么时候到？"}'
```

示例返回：

```json
{
  "reply": "你的订单A10001 (蓝牙耳机) 当前状态是已发货,预计送达时间为2026-07-05",
  "intent": "order_query",
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "OrderAgent", "OrderTools", "ComplianceAgent"]
}
```

### 退款政策

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u_001","session_id":"s_001","message":"怎么退款？"}'
```

示例返回：

```json
{
  "reply": "普通商品支持签收后 7 天内无理由退货；商品需要保持完好，不影响二次销售，并包含完整配件、包装和发票；退款会在仓库验收通过后 1-3 个工作日内原路退回。",
  "intent": "refund_policy",
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "RefundPolicyAgent", "KnowledgeBase", "ComplianceAgent"]
}
```

### 创建工单

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u_001","session_id":"s_001","message":"我要投诉，商品坏了"}'
```

示例返回：

```json
{
  "reply": "已为你创建工单 T10001,当前状态是待处理， 我们会尽快安排客服跟进。",
  "intent": "ticket_create",
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "TicketAgent", "TicketTools", "ComplianceAgent"]
}
```

### 查询工单

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u_001","session_id":"s_001","message":"查询我的工单状态"}'
```

示例返回：

```json
{
  "reply": "你的工单 T10001 当前状态是待处理。",
  "intent": "ticket_query",
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "TicketAgent", "TicketTools", "ComplianceAgent"]
}
```

## 测试

运行全部测试：

```bash
.venv/bin/python -m pytest
```

当前测试覆盖：

- `IntentAgent` 意图识别
- `OrderAgent` 订单查询和越权查询拦截
- `RefundPolicyAgent` 退款政策回复
- `TicketAgent` 工单创建和查询
- `ComplianceAgent` 脱敏和人工转接风险识别
- `Supervisor` 多 Agent 编排主链路

## 当前亮点

- 使用 Supervisor 统一编排多个 Agent，API 层只负责接收请求和返回响应
- Agent 层与工具层分离，便于后续替换真实订单系统、工单系统和知识库服务
- 订单查询按 `user_id` 做权限校验，避免越权访问其他用户订单
- 工单测试通过 pytest `tmp_path` 隔离测试数据，避免污染 `data/mock_tickets.json`
- 所有最终回复都会经过 `ComplianceAgent`，具备基础脱敏和风险识别能力
- `trace` 字段展示 Agent 调用链，方便调试、演示和后续接入 OpenTelemetry

## 后续规划

- 接入 Redis 保存短期会话记忆，支持多轮上下文
- 使用向量数据库将退款政策问答升级为 RAG
- 接入真实 LLM，实现更灵活的意图识别和回复生成
- 引入 OpenTelemetry 记录 Agent 调用链和工具耗时
- 增加前端聊天页面，展示用户对话和 Agent 执行过程
- 接入真实 MCP 工具层，统一订单、工单、风控、知识库等工具调用协议
