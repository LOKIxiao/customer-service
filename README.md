# Customer Service Agent

一个基于 FastAPI + LangGraph 的智能客服多 Agent 系统，面向电商客服场景，支持订单查询、退款政策问答、工单创建与查询、短期会话记忆、合规审查等能力。

项目目标是模拟真实客服系统中的 Agent 编排流程：用户消息进入 `/chat` 接口后，由 Supervisor 调用 LangGraph StateGraph 执行多 Agent 编排，通过条件边动态路由到不同业务 Agent，并通过工具层访问 mock 业务数据，最后经过合规审查后返回回复。

## 功能

- 意图识别：识别订单查询、退款政策、工单创建、工单查询、人工客服等意图
- 订单查询：根据 `user_id` 查询 mock 订单数据，避免越权查询其他用户订单
- 退款政策问答：基于本地知识库文件回答退款、退货、到账时效等问题
- 工单处理：支持创建投诉工单和查询最近工单状态
- 合规审查：支持手机号脱敏和高风险关键词识别
- 短期会话记忆：使用内存版 SessionMemory 保存同一 session 下最近多轮对话
- 记忆查询：支持用户询问“刚才我问了什么？”，系统会基于当前 session 的历史消息回答
- LLM 回复生成：通过 ResponseAgent 接入 OpenAI-compatible LLM，对业务 Agent 的原始回复生成更自然的客服话术，并在失败时回退到原始回复
- 调用链追踪：通过 `trace` 字段展示一次请求经过的 Agent 和工具
- 图编排：基于 LangGraph StateGraph 将意图识别、业务处理、记忆查询和合规审查拆分为独立节点
- 自动化测试：使用 pytest 覆盖 Agent、Memory、LangGraph 编排和 Supervisor 主链路

## 架构

```text
User
 ↓
FastAPI /chat
 ↓
Supervisor
 ↓
LangGraph StateGraph
 ├── SessionMemory
 ├── intent_node -> IntentAgent
 ├── order_node -> OrderAgent -> OrderTools
 ├── refund_node -> RefundPolicyAgent -> KnowledgeBase
 ├── ticket_node -> TicketAgent -> TicketTools
 ├── memory_node -> MemoryAgent
 ├── fallback_node
 ├── response_node -> ResponseAgent -> LLMClient
 └── compliance_node -> ComplianceAgent
```

LangGraph 节点流转：

```text
START
 ↓
intent_node
 ↓
route_by_intent
 ├── order_node
 ├── refund_node
 ├── ticket_node
 ├── memory_node
 └── fallback_node
 ↓
response_node
 ↓
compliance_node
 ↓
END
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
LangGraph intent_node -> order_query
 ↓
order_node -> OrderAgent
 ↓
OrderTools -> data/mock_orders.json
 ↓
response_node -> ResponseAgent
 ↓
compliance_node -> ComplianceAgent
 ↓
返回订单状态和预计送达时间
```

退款政策流程：

```text
用户：怎么退款？
 ↓
LangGraph intent_node -> refund_policy
 ↓
refund_node -> RefundPolicyAgent
 ↓
KnowledgeBase -> data/knowledge_base/refund_policy.md
 ↓
response_node -> ResponseAgent
 ↓
compliance_node -> ComplianceAgent
 ↓
返回退款政策说明
```

工单流程：

```text
用户：我要投诉，商品坏了
 ↓
LangGraph intent_node -> ticket_create
 ↓
ticket_node -> TicketAgent
 ↓
TicketTools -> data/mock_tickets.json
 ↓
response_node -> ResponseAgent
 ↓
compliance_node -> ComplianceAgent
 ↓
返回工单编号和处理状态
```

记忆查询流程：

```text
用户：刚才我问了什么？
 ↓
LangGraph intent_node -> memory_query
 ↓
memory_node -> MemoryAgent
 ↓
SessionMemory -> 当前 session 历史消息
 ↓
response_node -> ResponseAgent
 ↓
compliance_node -> ComplianceAgent
 ↓
返回上一轮用户问题
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
│   │   ├── memory_agent.py
│   │   ├── response_agent.py
│   │   └── compliance_agent.py
│   ├── llm/
│   │   ├── base.py
│   │   ├── fake_client.py
│   │   └── openai_compatible_client.py
│   ├── graphs/
│   │   └── customer_service_graph.py
│   ├── memory/
│   │   └── session_memory.py
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

可选：配置真实 LLM。

```bash
cp .env.example .env
```

`.env` 示例：

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

默认测试和本地开发使用 `FakeLLMClient`，不会请求真实模型服务。接入真实模型时可使用 `OpenAICompatibleClient`。

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
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "OrderAgent", "OrderTools", "ResponseAgent", "ComplianceAgent"]
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
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "RefundPolicyAgent", "KnowledgeBase", "ResponseAgent", "ComplianceAgent"]
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
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "TicketAgent", "TicketTools", "ResponseAgent", "ComplianceAgent"]
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
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "TicketAgent", "TicketTools", "ResponseAgent", "ComplianceAgent"]
}
```

### 记忆查询

先发送第一轮消息：

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u_001","session_id":"s_memory_demo","message":"我的订单什么时候到？"}'
```

再使用相同的 `session_id` 查询历史：

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u_001","session_id":"s_memory_demo","message":"刚才我问了什么？"}'
```

示例返回：

```json
{
  "reply": "你刚才问的是：我的订单什么时候到？",
  "intent": "memory_query",
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "MemoryAgent", "ResponseAgent", "ComplianceAgent"]
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
- `SessionMemory` 短期会话记忆
- `MemoryAgent` 基于 SessionMemory 回答历史问题
- `ResponseAgent` 基于 LLMClient 生成客服回复，并在 LLM 异常时回退到原始回复
- `LangGraph StateGraph` 多 Agent 图编排
- `Supervisor` 图执行入口和 API 适配

## 当前亮点

- 使用 LangGraph StateGraph 实现多 Agent 编排，API 层只负责接收请求和返回响应
- 通过条件边根据 `intent` 动态路由到订单、退款、工单、记忆或兜底节点
- Agent 层与工具层分离，便于后续替换真实订单系统、工单系统和知识库服务
- 订单查询按 `user_id` 做权限校验，避免越权访问其他用户订单
- 工单测试通过 pytest `tmp_path` 隔离测试数据，避免污染 `data/mock_tickets.json`
- 使用内存版 `SessionMemory` 保存同一 session 下的用户消息和助手回复
- 通过 `MemoryAgent` 支持基于 session 的历史问题查询
- 通过 `ResponseAgent` 接入 OpenAI-compatible LLM，让模型参与客服回复生成，但业务事实仍来自工具层
- 所有最终回复都会经过 `ComplianceAgent`，具备基础脱敏和风险识别能力
- `trace` 字段展示 LangGraph 节点和 Agent 调用链，方便调试、演示和后续接入 OpenTelemetry

## 后续规划

- 将内存版 SessionMemory 替换为 Redis，实现可持久化的短期会话记忆
- 使用向量数据库将退款政策问答升级为 RAG
- 接入真实 LLM，实现更灵活的意图识别和回复生成
- 引入 OpenTelemetry 记录 Agent 调用链和工具耗时
- 增加前端聊天页面，展示用户对话和 Agent 执行过程
- 接入真实 MCP 工具层，统一订单、工单、风控、知识库等工具调用协议
