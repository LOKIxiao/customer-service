# Customer Service Agent

一个基于 FastAPI + LangGraph 的智能客服多 Agent 系统，面向电商客服场景，支持订单查询、退款政策问答、工单创建与查询、分层用户记忆、合规审查等能力。

项目目标是模拟真实客服系统中的 Agent 编排流程：用户消息进入 `/chat` 接口后，由 Supervisor 调用 LangGraph StateGraph 执行多 Agent 编排，通过条件边动态路由到不同业务 Agent；业务 Agent 不直接访问数据，而是通过一个真实的 MCP（Model Context Protocol）Server 调用订单、工单、知识库检索、长期记忆、合规审查等工具，最后返回回复。记忆分两层：短期的 session 滑动窗口负责"这句话是不是在追问上一句"，长期的向量记忆库负责"这个用户一直以来有什么稳定偏好/历史"，两者都会被检索出来注入到最终回复生成的 Prompt 里。

## 功能

- 意图识别：通过 HybridIntentAgent 结合 Qwen 结构化意图识别和规则兜底，识别订单查询、知识库类问题、工单创建、工单查询、人工客服等意图
- 订单查询：根据 `user_id` 查询 mock 订单数据，避免越权查询其他用户订单
- 退款/退货/物流/发票/保修/账号安全/会员积分/优惠券/故障排查等知识库问答：基于 RAG（文档分块 + 向量检索 + BM25 关键词检索 + RRF 混合排序）在 8 篇知识库文档中做检索
- 工单处理：支持创建投诉工单和查询最近工单状态
- 合规审查：支持手机号脱敏和高风险关键词识别
- 短期会话记忆：使用内存版 SessionMemory 保存同一 session 下最近多轮对话
- 记忆查询：支持用户询问“刚才我问了什么？”，系统会基于当前 session 的历史消息回答
- 长期用户记忆：每轮对话结束后由 `MemoryExtractionAgent` 调 LLM 判断有没有值得长期记住的稳定信息（商品偏好、收货/联系偏好、投诉历史、沟通风格），存进按 `user_id` 隔离的向量记忆库；下一轮回复生成前会先检索相关的长期记忆并注入 Prompt
- LLM 回复生成：通过 ResponseAgent 接入 OpenAI-compatible LLM，对业务 Agent 的原始回复结合长期记忆生成更自然、更个性化的客服话术，并在失败时回退到原始回复
- MCP 工具层：订单查询、工单创建/查询、知识库检索、长期记忆读写、合规审查统一收敛到一个真实的 MCP Server 背后，Agent 通过 MCP Client（stdio + JSON-RPC）调用，而不是直接 import 业务函数
- 调用链追踪：通过 `trace` 字段展示一次请求经过的 Agent 和 MCP 工具
- 图编排：基于 LangGraph StateGraph 将意图识别、业务处理、记忆查询和合规审查拆分为独立节点
- 自动化测试：使用 pytest 覆盖 Agent、Memory、RAG、MCP、LangGraph 编排和 Supervisor 主链路

## 架构

```text
User
 ↓
FastAPI /chat
 ↓
Supervisor
 ↓
LangGraph StateGraph
 ├── SessionMemory（短期滑动窗口）
 ├── intent_node -> HybridIntentAgent -> LLMIntentAgent / RuleIntentAgent
 ├── order_node -> OrderAgent ──────────┐
 ├── knowledge_node -> RAGAgent ────────┤
 ├── ticket_node -> TicketAgent ────────┤
 ├── memory_node -> MemoryAgent（短期）  │
 ├── fallback_node                      ├── MCPToolClient (stdio + JSON-RPC)
 ├── memory_recall_node -> LongTermMemoryAgent ┤        ↓
 ├── response_node -> ResponseAgent -> LLMClient  MCP Server (app/mcp/server.py)
 ├── compliance_node ───────────────────┤   ├── get_order                  -> app/tools/order_tools.py
 └── memory_extraction_node             │   ├── create_ticket/query_ticket -> app/tools/ticket_tools.py
      -> MemoryExtractionAgent(LLM) ────┤   ├── search_knowledge_base      -> app/rag (混合检索)
      -> LongTermMemoryAgent（写入）────┘   ├── recall_user_memory/save_user_memory -> app/memory/long_term_store.py
                                          └── review_compliance           -> app/agents/compliance_agent.py
```

LangGraph 节点流转：

```text
START
 ↓
intent_node
 ↓
route_by_intent
 ├── order_node
 ├── knowledge_node
 ├── ticket_node
 ├── memory_node
 └── fallback_node
 ↓
memory_recall_node（检索长期记忆，注入 Prompt）
 ↓
response_node
 ↓
compliance_node
 ↓
memory_extraction_node（抽取本轮值得记住的信息，非空才写入）
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
LangGraph intent_node -> HybridIntentAgent -> order_query
 ↓
order_node -> OrderAgent
 ↓
MCPToolClient.call_tool("get_order") -> MCP Server -> data/mock_orders.json
 ↓
memory_recall_node -> LongTermMemoryAgent -> MCPToolClient.call_tool("recall_user_memory")
 ↓
response_node -> ResponseAgent
 ↓
compliance_node -> MCPToolClient.call_tool("review_compliance")
 ↓
memory_extraction_node -> MemoryExtractionAgent（LLM 判断有没有值得记住的信息）
 ↓
返回订单状态和预计送达时间
```

知识库问答流程（RAG，覆盖退款/物流/发票/保修/账号安全/会员积分/优惠券/故障排查全部 8 篇文档）：

```text
用户：会员等级怎么算，积分能抵多少钱？
 ↓
LangGraph intent_node -> HybridIntentAgent -> knowledge_base_query
 ↓
knowledge_node -> RAGAgent
 ↓
MCPToolClient.call_tool("search_knowledge_base") -> MCP Server
 ↓
DocumentLoader/TextSplitter -> EmbeddingClient -> ChromaVectorStore + BM25Index (RRF 融合) -> data/knowledge_base/*.md
 ↓
memory_recall_node -> LongTermMemoryAgent -> MCPToolClient.call_tool("recall_user_memory")
 ↓
response_node -> ResponseAgent
 ↓
compliance_node -> MCPToolClient.call_tool("review_compliance")
 ↓
memory_extraction_node -> MemoryExtractionAgent（LLM 判断有没有值得记住的信息）
 ↓
返回检索到的知识库片段生成的回复
```

工单流程：

```text
用户：我要投诉，商品坏了
 ↓
LangGraph intent_node -> HybridIntentAgent -> ticket_create
 ↓
ticket_node -> TicketAgent
 ↓
MCPToolClient.call_tool("create_ticket") -> MCP Server -> data/mock_tickets.json
 ↓
memory_recall_node -> LongTermMemoryAgent -> MCPToolClient.call_tool("recall_user_memory")
 ↓
response_node -> ResponseAgent
 ↓
compliance_node -> MCPToolClient.call_tool("review_compliance")
 ↓
memory_extraction_node -> MemoryExtractionAgent（LLM 判断有没有值得记住的信息）
 ↓
返回工单编号和处理状态
```

记忆查询流程：

```text
用户：刚才我问了什么？
 ↓
LangGraph intent_node -> HybridIntentAgent -> memory_query
 ↓
memory_node -> MemoryAgent
 ↓
SessionMemory -> 当前 session 历史消息
 ↓
memory_recall_node -> LongTermMemoryAgent -> MCPToolClient.call_tool("recall_user_memory")
 ↓
response_node -> ResponseAgent
 ↓
compliance_node -> MCPToolClient.call_tool("review_compliance")
 ↓
memory_extraction_node -> MemoryExtractionAgent（LLM 判断有没有值得记住的信息）
 ↓
返回上一轮用户问题
```

长期记忆流程（跨轮次生效）：

```text
第一轮 用户：我平时更喜欢无线降噪耳机，续航要长
 ↓
... 正常业务流程 ...
 ↓
compliance_node 结束后 -> memory_extraction_node
 ↓
MemoryExtractionAgent（LLM）判断这轮有稳定信息值得记住
 ↓
LongTermMemoryAgent.remember -> MCPToolClient.call_tool("save_user_memory")
 ↓
UserMemoryStore（chromadb，按 user_id 隔离）写入一条 preference 记忆

第二轮（同一 user_id，任意 session）用户：我要投诉，商品坏了
 ↓
memory_recall_node -> LongTermMemoryAgent.recall -> MCPToolClient.call_tool("recall_user_memory")
 ↓
UserMemoryStore 按 user_id 检索出"用户偏好无线降噪耳机，续航要长"
 ↓
response_node -> ResponseAgent 把这条长期记忆作为【已知用户信息】注入 Prompt
 ↓
LLM 在合适的地方自然体现这条信息（不生硬复述）
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
│   │   ├── llm_intent_agent.py
│   │   ├── hybrid_intent_agent.py
│   │   ├── order_agent.py
│   │   ├── rag_agent.py
│   │   ├── ticket_agent.py
│   │   ├── memory_agent.py            # 短期记忆：回答"你刚才问了什么"
│   │   ├── long_term_memory_agent.py  # 长期记忆的 recall/remember，走 MCP
│   │   ├── memory_extraction_agent.py # LLM 抽取本轮值得记住的信息
│   │   ├── response_agent.py
│   │   └── compliance_agent.py
│   ├── llm/
│   │   ├── base.py
│   │   ├── fake_client.py
│   │   └── openai_compatible_client.py
│   ├── mcp/
│   │   ├── handlers.py       # server 和 FakeMCPToolClient 共用的业务逻辑
│   │   ├── server.py         # FastMCP server，注册 7 个工具，stdio 运行
│   │   ├── client.py         # 真实 MCPToolClient（stdio 子进程 + JSON-RPC）
│   │   ├── fake_client.py    # FakeMCPToolClient，同进程直连 handlers，供单测使用
│   │   └── factory.py
│   ├── rag/
│   │   ├── document_loader.py
│   │   ├── text_splitter.py
│   │   ├── embedding.py
│   │   ├── embedding_factory.py
│   │   ├── vector_store.py       # InMemoryVectorStore，现在是评估用的 baseline
│   │   ├── chroma_vector_store.py # ChromaVectorStore，生产默认向量存储
│   │   ├── bm25.py               # 手写 BM25 关键词检索
│   │   ├── retriever.py          # KnowledgeRetriever，纯向量检索
│   │   ├── hybrid_retriever.py   # HybridKnowledgeRetriever，向量+BM25 RRF 融合，生产默认
│   │   ├── evaluation.py         # recall@k / MRR 评估脚本
│   │   └── factory.py
│   ├── graphs/
│   │   └── customer_service_graph.py
│   ├── memory/
│   │   ├── session_memory.py     # 短期滑动窗口（最近 10 条消息）
│   │   ├── long_term_store.py    # UserMemoryStore，chromadb + 按 user_id 隔离
│   │   └── factory.py
│   ├── tools/
│   │   ├── order_tools.py
│   │   └── ticket_tools.py
│   ├── schemas/
│   │   ├── chat.py
│   │   ├── intent.py
│   │   ├── compliance.py
│   │   ├── rag.py
│   │   └── memory.py
│   └── main.py
├── data/
│   ├── mock_orders.json
│   ├── mock_tickets.json
│   ├── knowledge_base/
│   │   ├── refund_policy.md
│   │   ├── shipping_policy.md
│   │   ├── invoice_policy.md
│   │   ├── warranty_policy.md
│   │   ├── account_security.md
│   │   ├── membership_policy.md
│   │   ├── promotion_policy.md
│   │   └── troubleshooting_faq.md
│   ├── eval/
│   │   └── retrieval_qa.json     # 检索评估用的 QA 数据集
│   ├── chroma_db/                # 知识库向量索引，已 gitignore，不进版本库
│   └── user_memory_db/           # 长期用户记忆索引，已 gitignore，不进版本库
├── tests/
├── requirements.txt
├── pytest.ini
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
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

可选：配置真实 LLM 和 embedding。

```bash
cp .env.example .env
```

`.env` 示例：

```env
LLM_ENABLED=true
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

EMBEDDING_ENABLED=true
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4
```

默认测试和本地开发使用 `FakeLLMClient` / `FakeEmbeddingClient`，不会请求真实模型服务；`LLM_ENABLED`/`EMBEDDING_ENABLED` 都设为 `true` 时才会分别接入 `OpenAICompatibleClient` 和 `QwenEmbeddingClient`。MCP Server 是独立子进程，只会继承显式传给它的环境变量（`MCPToolClient` 会把当前进程的环境变量转发过去），所以这两个开关、以及知识库检索用的 `CHROMA_PERSIST_DIR`（chroma 持久化目录，默认 `data/chroma_db`）、长期记忆用的 `USER_MEMORY_DB_DIR`（默认 `data/user_memory_db`）对 MCP 侧的工具调用同样生效。

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

### Docker 部署

也可以用 Docker 跑，不需要本地装 Python/依赖：

```bash
cp .env.example .env  # 按需修改，默认 LLM/EMBEDDING 都是关闭状态，走 Fake client
docker compose up --build
```

健康检查和接口调用方式不变（默认映射到 `http://127.0.0.1:8000`）。`docker-compose.yml` 给 chromadb 的三个持久化目录（`data/chroma_db`、`data/chroma_db_eval`、`data/user_memory_db`）挂了具名 volume，容器重建不会丢检索索引和长期记忆数据。

也可以不用 compose，手动 build/run：

```bash
docker build -t customer-service-agent .
docker run -p 8000:8000 --env-file .env customer-service-agent
```

镜像里 MCP Server 是通过 `sys.executable -m app.mcp.server` 在容器内部拉起的子进程，不需要额外配置；已经实测容器内订单查询、知识库检索（chromadb + BM25 + jieba）、长期记忆读写全链路走通。

### 单独调试 MCP Server

订单/工单/知识库检索/长期记忆/合规审查这五类工具都通过 `app/mcp/server.py` 暴露的 MCP Server 提供，可以脱离 FastAPI 单独跑：

```bash
.venv/bin/python -m app.mcp.server
```

以 stdio 方式启动，可以配合 `mcp[cli]` 提供的 Inspector 可视化调试（需要额外 `pip install "mcp[cli]"`）：

```bash
mcp dev app/mcp/server.py
```

打开 Inspector 页面后可以直接点开 `get_order`、`create_ticket`、`query_ticket`、`search_knowledge_base`、`recall_user_memory`、`save_user_memory`、`review_compliance` 七个工具，手动传参调用，直观看到 MCP 协议层的 tool schema 和调用结果。

### 检索效果评估

`data/eval/retrieval_qa.json` 是一份覆盖全部 8 篇知识库文档、混合了直给关键词和换一种问法的 30 条 QA 数据集。跑评估脚本可以量化对比三种检索配置：

```bash
.venv/bin/python -m app.rag.evaluation
```

实测结果（`k=3`）：

| 配置 | Fake embedding | 真实 Qwen embedding |
| --- | --- | --- |
| naive（InMemoryVectorStore，纯向量） | recall@3 53.3%，MRR 0.472 | recall@3 100%，MRR 0.983 |
| chroma（纯向量） | recall@3 53.3%，MRR 0.472 | recall@3 100%，MRR 0.983 |
| chroma + BM25（混合检索） | recall@3 **76.7%**，MRR **0.650** | recall@3 100%，MRR 0.978 |

结论：embedding 质量弱的时候（比如自建的简单 embedding），混合检索能把 recall@3 从 53% 拉到 77%，收益明显；但换成真实 Qwen embedding，纯向量检索已经接近满分，混合检索的边际收益很小，甚至因为 BM25 引入的排序噪声让 MRR 略微下降。混合检索更像是对弱/不稳定 embedding 的一层兜底，不是"永远更好"的银弹。

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
  "reply": "您的订单A10001（蓝牙耳机）已发货，预计2026年7月5日送达。",
  "intent": "order_query",
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "OrderAgent", "MCP:get_order", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
}
```

### 知识库问答（RAG）

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u_001","session_id":"s_001","message":"怎么退款？"}'
```

示例返回：

```json
{
  "reply": "您好，退款将原路退回：审核通过后1-3个工作日内发起，具体到账时间以支付渠道为准——微信/支付宝通常1个工作日内到账，银行卡需1-7个工作日（节假日可能延长）。退款金额按您实际支付金额计算，优惠券及分期手续费不予退还。",
  "intent": "knowledge_base_query",
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "RAGAgent", "MCP:search_knowledge_base", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
}
```

知识库覆盖的不只是退款——以前"钻石会员有什么权益？""耳机连不上手机怎么办"这类问题会被分类成 `unknown`/`human_handoff`，根本走不到 `RAGAgent`；意图分类扩展到 `knowledge_base_query` 之后，这些问题也能正确命中知识库并生成回复（真实调用验证）：

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u_001","session_id":"s_002","message":"钻石会员有什么权益？"}'
```

```json
{
  "reply": "钻石会员权益包括：✅ 消费积分2倍累积 ✅ 专属生日礼包 ✅ 专属客服优先接入（需累计消费满5000元升级，等级有效期12个月）",
  "intent": "knowledge_base_query",
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "RAGAgent", "MCP:search_knowledge_base", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
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
  "reply": "已为您创建投诉工单 T10001，当前状态为“待处理”，我们将尽快安排客服跟进。",
  "intent": "ticket_create",
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "TicketAgent", "MCP:create_ticket", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
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
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "TicketAgent", "MCP:query_ticket", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
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
  "trace": ["ChatAPI", "Supervisor", "IntentAgent", "MemoryAgent", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
}
```

## 测试

运行全部测试：

```bash
.venv/bin/python -m pytest
```

当前测试覆盖：

- `IntentAgent` 意图识别
- `LLMIntentAgent` 结构化 JSON 意图识别
- `HybridIntentAgent` LLM 意图识别与规则兜底
- `OrderAgent` 订单查询和越权查询拦截
- `TicketAgent` 工单创建和查询
- `ComplianceAgent` 脱敏和人工转接风险识别
- `SessionMemory` 短期会话记忆
- `MemoryAgent` 基于 SessionMemory 回答历史问题
- `UserMemoryStore` 长期记忆的存取和按 `user_id` 隔离、`MemoryExtractionAgent` 抽取逻辑（合法 JSON/非法 category/解析失败三种情况）
- `ResponseAgent` 基于 LLMClient 生成客服回复，并在 LLM 异常时回退到原始回复
- RAG：`DocumentLoader`/`TextSplitter`（含标题面包屑分块）/`EmbeddingClient`/`InMemoryVectorStore`/`ChromaVectorStore`/`BM25Index`/`HybridKnowledgeRetriever`
- MCP：`handlers.py` 纯业务逻辑单测、`MCPToolClient` 真实 stdio + JSON-RPC 集成测试（`tests/test_mcp_integration.py`）
- `LangGraph StateGraph` 多 Agent 图编排
- `Supervisor` 图执行入口和 API 适配

## 当前亮点

- 使用 LangGraph StateGraph 实现多 Agent 编排，API 层只负责接收请求和返回响应
- 通过条件边根据 `intent` 动态路由到订单、知识库、工单、记忆或兜底节点
- 采用 `HybridIntentAgent` 将 Qwen 结构化意图识别与规则意图识别结合，通过合法 intent 白名单、置信度阈值和 fallback 策略降低模型输出不稳定影响
- `knowledge_base_query` 意图覆盖全部 8 篇知识库文档（不再只有退款场景能触发 RAG），规则兜底和 LLM 分类的 Prompt 都同步扩展了对应关键词/描述，并有专门的回归测试和真实端到端验证（之前"钻石会员有什么权益""耳机连不上手机怎么办"这类问题会被误分类成 `unknown`/`human_handoff`，现在能正确命中知识库）
- 订单、工单、知识库检索、合规审查统一收敛到真实的 MCP Server（`app/mcp/server.py`，基于官方 `mcp` SDK 的 `FastMCP`），Agent 通过 `MCPToolClient`（stdio 子进程 + JSON-RPC，非模拟协议）调用工具，`python -m app.mcp.server` 可脱离主服务单独运行和调试
- MCP 单测走 `FakeMCPToolClient`（同进程直连业务逻辑，无子进程开销），真实协议路径由独立的 `tests/test_mcp_integration.py` 覆盖，兼顾测试速度和协议可信度
- RAG 知识库覆盖退款、物流、发票、保修、账号安全、会员积分、优惠券、故障排查八个场景，文档故意用不同结构（表格、FAQ、规则条款）覆盖分块和检索的多样性；`TextSplitter` 按 Markdown 标题维护面包屑上下文，避免只召回到孤立标题
- 检索层用 `ChromaVectorStore`（真实持久化向量库）+ 手写 `BM25Index`（`jieba` 分词）做 RRF 混合排序，并配了一份 30 条 QA 的评估数据集和评估脚本（`app/rag/evaluation.py`），能跑出 recall@k / MRR 量化对比，而不是只凭感觉判断检索效果好不好
- 订单查询按 `user_id` 做权限校验，避免越权访问其他用户订单
- 工单测试通过 pytest `tmp_path` 隔离测试数据，避免污染 `data/mock_tickets.json`
- 使用内存版 `SessionMemory` 保存同一 session 下的用户消息和助手回复
- 通过 `MemoryAgent` 支持基于 session 的历史问题查询
- 分层记忆：短期 `SessionMemory`（session 内滑动窗口）+ 长期 `UserMemoryStore`（跨 session、按 `user_id` 隔离的向量记忆库，复用已有的 chromadb 技术栈），`MemoryExtractionAgent` 每轮结束后判断有没有稳定信息值得记住，大多数轮次（查物流、查工单状态）应该抽不出东西，不是每轮都硬造一条记忆
- 长期记忆的读写也统一走 MCP 工具（`recall_user_memory`/`save_user_memory`），和订单/工单/知识库保持同样的架构，不是单独开的后门
- 通过 `ResponseAgent` 接入 OpenAI-compatible LLM，让模型参与客服回复生成，业务事实来自 MCP 工具层、个性化信息来自长期记忆，两者都不是模型编造的
- 所有最终回复都会经过 MCP `review_compliance` 工具，具备基础脱敏和风险识别能力
- `trace` 字段展示 LangGraph 节点和 MCP 工具调用链，方便调试、演示和后续接入 OpenTelemetry
- 提供 `Dockerfile`/`docker-compose.yml`，一条命令即可跑起来，不需要本地装 Python 环境；已实测容器内 MCP 子进程拉起、chromadb 向量检索、BM25 分词（jieba）全链路正常

## 已知局限

- `ChromaVectorStore` 每次懒加载都会整体删除重建 collection，没有增量同步/去重机制；知识库规模小的时候没问题，规模变大后需要改成基于内容 hash 的增量更新。
- 首次触发检索时会对全部 chunk（目前 82 个）依次调用 embedding 接口，没有做批量请求，真实 Qwen embedding 下冷启动有几十秒延迟。
- RRF 混合检索在真实高质量 embedding 下收益很小（见上面的评估结果），价值主要体现在 embedding 较弱的场景。
- 长期记忆的抽取是每轮对话结束后都同步调一次 LLM，会给每轮请求增加一次额外的 LLM 调用延迟；生产环境更合理的做法是异步/批量抽取，不阻塞当轮响应。
- `UserMemoryStore` 没有去重/合并机制：用户反复表达同一个偏好会存成多条相似记录，没有做"更新已有记忆"而是每次都新增。
- 长期记忆没有过期/衰减机制，理论上会无限增长；也没有让用户查看或删除自己被记住了什么信息的接口。

## 后续规划

- 将内存版 SessionMemory 替换为 Redis，实现可持久化的短期会话记忆
- 引入 LLM 深度合规审查，补充当前规则合规审查
- 引入 OpenTelemetry 记录 Agent 调用链和 MCP 工具耗时
- 增加前端聊天页面，展示用户对话和 Agent 执行过程
- 知识库检索改成增量同步 + 批量 embedding，去掉每次全量重建的开销
- 给检索结果加一层真正的 cross-encoder rerank，替代目前基于排名的 RRF 融合
- 长期记忆抽取改成异步/批量，避免每轮对话都同步增加一次 LLM 调用延迟
- 长期记忆加去重/合并逻辑（比如同一 category 下语义相似的记忆合并更新），并加一个"查看/删除我的记忆"的接口
