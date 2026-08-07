# Customer Service Agent

一个基于 FastAPI + LangGraph 的智能客服多 Agent 系统，面向电商客服场景，支持订单查询、退款政策问答、工单创建与查询、分层用户记忆、合规审查等能力。

项目目标是模拟真实客服系统中的 Agent 编排流程：用户消息进入 `/chat` 接口后，由 Supervisor 调用 LangGraph StateGraph 执行多 Agent 编排，通过条件边动态路由到不同业务 Agent；业务 Agent 不直接访问数据，而是通过一个真实的 MCP（Model Context Protocol）Server 调用订单、工单、知识库检索、长期记忆、合规审查等工具，最后返回回复。记忆分两层：短期的 session 滑动窗口负责"这句话是不是在追问上一句"，长期的向量记忆库负责"这个用户一直以来有什么稳定偏好/历史"，两者都会被检索出来注入到最终回复生成的 Prompt 里。

## 功能

- 意图识别：通过 HybridIntentAgent 结合 Qwen 结构化意图识别和规则兜底，识别订单查询、知识库类问题、工单创建、工单查询、人工客服等意图
- 订单查询：根据 `user_id` 查询 mock 订单数据，避免越权查询其他用户订单
- 退款/物流/发票/保修/账号、订单、支付、换货、客服工单等知识库问答：基于 RAG（文档分块 + 向量检索 + BM25 关键词检索 + RRF 混合排序）在 12 篇知识库文档中做检索
- 工单处理：支持创建投诉工单和查询最近工单状态
- 输入脱敏前置：用户消息在写入会话记忆、进入意图/回复 LLM 及 trace 日志之前，先由图入口的 `sanitize` 节点对手机号、身份证、银行卡、邮箱等 PII 打码
- 合规审查：对最终回复做输出侧脱敏（复用同一套 PII 规则）和高风险关键词识别
- 短期会话记忆：使用 Redis List 按 session 保存最近 10 条消息并设置 TTL，服务重启或多实例部署后仍可恢复；Redis 不可用时自动降级为进程内滑动窗口
- 多轮上下文：每轮在写入当前消息前读取最近历史，分别注入 LLM 意图识别与 ResponseAgent Prompt，用于理解“那多久”“这个呢”等指代和省略
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
 ├── RedisSessionMemory（短期窗口 + TTL，失败降级到内存）
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
sanitize_node（输入 PII 脱敏前置）
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

知识库问答流程（RAG，检索目录覆盖退款、物流、发票、保修、账号、会员、优惠、故障、订单、支付、换货和客服工单 12 篇文档）：

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
RedisSessionMemory -> 当前 session 历史消息（重启可恢复）
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
│   │   └── compliance_agent.py       # 输出侧合规审查（复用 app/compliance/pii）
│   ├── compliance/
│   │   └── pii.py                    # 可复用 PII 脱敏规则，输入/输出侧共用
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
│   │   ├── reranker.py           # qwen3-rerank 精排层（可选）
│   │   ├── evidence_gate.py      # 证据充分性判断，不足则拒答
│   │   ├── evaluation.py         # 检索评估：recall@k / MRR
│   │   ├── answer_evaluation.py  # 最终回答评估：来源命中/规则通过/拒答/LLM Judge
│   │   └── factory.py
│   ├── graphs/
│   │   └── customer_service_graph.py
│   ├── memory/
│   │   ├── session_memory.py     # 内存/Redis短期窗口（最近 10 条消息 + TTL）
│   │   ├── session_factory.py    # 根据环境开关创建Redis或内存实现
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
│   │   ├── troubleshooting_faq.md
│   │   ├── order_management.md
│   │   ├── payment_policy.md
│   │   ├── exchange_policy.md
│   │   └── customer_service_policy.md
│   ├── eval/
│   │   ├── retrieval_qa.json     # 检索评估用的 QA 数据集（140 条挑战集）
│   │   ├── answer_qa.json        # 最终回答评估集（60 条）
│   │   └── ANNOTATION_GUIDE.md   # 评估集人工标注规范
│   ├── chroma_db/                # 知识库向量索引，已 gitignore，不进版本库
│   └── user_memory_db/           # 长期用户记忆索引，已 gitignore，不进版本库
├── tests/
├── scripts/
│   └── build_retrieval_eval.py   # 生成/维护检索评估集的脚本
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

REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
SESSION_MAX_MESSAGES=10
SESSION_TTL_SECONDS=86400
```

默认测试和本地开发使用 `FakeLLMClient` / `FakeEmbeddingClient`，不会请求真实模型服务；`LLM_ENABLED`/`EMBEDDING_ENABLED` 都设为 `true` 时才会分别接入 `OpenAICompatibleClient` 和 `QwenEmbeddingClient`。`REDIS_ENABLED=true` 时短期消息使用 Redis；连接或依赖不可用时自动降级到内存，保证客服主流程可用。`docker compose up --build` 会自动启动带 AOF 数据卷的 Redis，并给应用注入容器内地址。MCP Server 是独立子进程，只会继承显式传给它的环境变量。

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

`data/eval/retrieval_qa.json` 是一份 140 条的检索挑战集：103 条单证据问题、20 条严格多证据问题和 17 条知识库无答案问题，共覆盖 103 个独立证据 Chunk。问题以边界条件、否定前提、跨规则比较和口语化场景为主，不再用大量关键词直给题抬高指标。当前标签状态为 `draft_pending_human_review`，完成逐条人工复核后才能改成 `human_verified`。

```bash
.venv/bin/python -m app.rag.evaluation
```

实测结果（`k=3`）：

| 配置 | Fake 来源R@3 | Fake 证据R@3 | Qwen 来源R@3 | Qwen 证据R@3 |
| --- | ---: | ---: | ---: | ---: |
| naive（InMemoryVectorStore，纯向量） | 35.8% | 10.6% | **94.3%** | **88.6%** |
| chroma（纯向量） | 35.8% | 10.6% | **94.3%** | **88.6%** |
| chroma + BM25（混合检索） | **73.2%** | **49.6%** | **94.3%** | 87.0% |
| RRF Top 20 + qwen3-rerank | — | — | **95.9%** | **94.3%** |

每条正例同时标注 `expected_sources`、`expected_chunk_ids` 和 `match_mode`。多证据问题要求全部证据进入 Top 3 才算命中；无答案问题不混进 Recall 分母，而是单独计算拒答准确率。知识段落改为“主规则＋例外＋关联流程”的复合内容后，真实 Qwen 纯向量的证据 Recall@3/MRR 为 88.6%/0.770，混合检索为 87.0%/0.755；BM25 没有提高严格证据召回，仍会带来少量排序噪声。上表三种无阈值 Retriever 都必然返回 Top K，因此无答案拒答准确率为 0%，需要另行评估 `EvidenceGate`，不能把无答案样本混入 Recall 人为压分。

### Reranker（可选）

混合检索的 RRF 候选池证据 Recall@20 为 99.2%，而最终证据 Recall@3 为 87.0%，说明多数正确证据已经召回但排序仍有优化空间。项目因此增加了可配置的 `qwen3-rerank` 精排层：向量和 BM25 各取候选，经 RRF 合并为 Top 20，再由真正的排序模型选出 Top 3。真实消融中，证据 Recall@3 从 87.0% 提升到 94.3%，证据 MRR 从 0.755 提升到 0.850；140 条冷启动端到端评测耗时 188.7 秒，平均每条约 1.35 秒。原始 RRF 分数和 rerank relevance score 都会保留在结果元数据中，便于 trace 和消融分析。

```env
RERANK_ENABLED=true
RERANK_API_KEY=your-api-key
RERANK_BASE_URL=https://your-workspace.cn-beijing.maas.aliyuncs.com/compatible-api/v1/reranks
RERANK_MODEL=qwen3-rerank
RERANK_CANDIDATE_K=20
```

`qwen3-rerank` 使用地域与业务空间相关的完整 `/reranks` 地址，不能直接复用旧的无 Workspace ID Embedding Base URL。未配置时保持 `RERANK_ENABLED=false`，原 RRF 链路不受影响。启用后运行同一个评估命令，结果表会自动增加 `RRF Top20 + qwen3-rerank` 行。使用 `FakeEmbeddingClient` 时工厂会强制禁用外部 Reranker，避免离线测试继承生产开关后误调真实 API。

### 最终回答效果评估

`data/eval/answer_qa.json` 是独立于检索集的最终回答评测集，共 60 条：48 条可回答问题和 12 条知识库无答案问题，按 40 条开发集、20 条测试集划分。每条样本包含标准答案、正确来源、必要事实组、禁止事实、难度和是否应该拒答。

离线运行（Fake LLM/Fake embedding，不产生外部 API 费用）：

```bash
LLM_ENABLED=false EMBEDDING_ENABLED=false \
  .venv/bin/python -m app.rag.answer_evaluation --split test
```

真实模型评测：

```bash
LLM_ENABLED=true EMBEDDING_ENABLED=true \
  .venv/bin/python -m app.rag.answer_evaluation --split test --llm-judge
```

评测报告同时给出来源命中率、必要事实规则通过率、无答案拒答准确率，以及可选 LLM Judge 的 correctness、faithfulness、completeness 和 pass rate。LLM Judge 默认关闭，避免脚本在未明确配置时自动产生费用；可以通过 `EVAL_JUDGE_MODEL` 等环境变量使用与生成模型不同的裁判模型。

Retriever 之后增加了 `EvidenceGate`：RRF 继续负责融合排序，Gate 使用原始向量相似度、BM25 分数和查询词项覆盖率判断证据是否充分；不充分时返回空候选，由 RAGAgent 输出“知识库未找到相关信息”。阈值通过环境变量配置，可用 `RAG_EVIDENCE_GATE_ENABLED=false` 临时关闭。

在 Fake LLM/Fake embedding 的 20 条测试集上，加入 Gate 前后对比为：来源命中率均为 75%，规则回答准确率从 30% 提升到 45%，无答案拒答准确率从 0% 提升到 75%。40 条开发集上的拒答准确率为 87.5%。这些阈值只在 Fake embedding 开发集上校准，真实 Qwen embedding 的分数分布不同，必须重新校准后再作为线上配置，不能直接把当前阈值当成通用常数。

在真实 Qwen embedding + Fake LLM 的 20 条测试集诊断中，可回答问题的来源 Hit@3 为 93.75%（15/16），无答案拒答准确率为 50%（2/4），规则通过率为 80%。这里的 80% 只是 Fake LLM 直接返回检索上下文后的规则覆盖率，不是最终生成回答准确率；结果同时证明基于 Fake embedding 校准的 Gate 阈值不能直接迁移到 Qwen，需要在 Qwen 开发集上重新校准。

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
  "trace": ["ChatAPI", "Supervisor", "InputSanitizer", "IntentAgent", "OrderAgent", "MCP:get_order", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
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
  "trace": ["ChatAPI", "Supervisor", "InputSanitizer", "IntentAgent", "RAGAgent", "MCP:search_knowledge_base", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
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
  "trace": ["ChatAPI", "Supervisor", "InputSanitizer", "IntentAgent", "RAGAgent", "MCP:search_knowledge_base", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
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
  "trace": ["ChatAPI", "Supervisor", "InputSanitizer", "IntentAgent", "TicketAgent", "MCP:create_ticket", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
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
  "trace": ["ChatAPI", "Supervisor", "InputSanitizer", "IntentAgent", "TicketAgent", "MCP:query_ticket", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
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
  "trace": ["ChatAPI", "Supervisor", "InputSanitizer", "IntentAgent", "MemoryAgent", "LongTermMemoryAgent", "MCP:recall_user_memory", "ResponseAgent", "ComplianceAgent", "MCP:review_compliance", "MemoryExtractionAgent"]
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
- `SessionMemory` / `RedisSessionMemory` 的窗口裁剪、TTL刷新、跨实例恢复和不可用降级
- 最近历史注入 LLM 意图识别与 ResponseAgent，多轮省略和指代不再只依赖当前消息
- `MemoryAgent` 基于短期会话历史回答“刚才问了什么”
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
- `knowledge_base_query` 意图已覆盖原有退款、物流、发票、保修、账号、会员、优惠和故障文档；本轮新增的订单、支付、换货和客服规则主要用于检索挑战集，后续还需补齐它们与业务型意图之间的路由边界回归测试
- 订单、工单、知识库检索、合规审查统一收敛到真实的 MCP Server（`app/mcp/server.py`，基于官方 `mcp` SDK 的 `FastMCP`），Agent 通过 `MCPToolClient`（stdio 子进程 + JSON-RPC，非模拟协议）调用工具，`python -m app.mcp.server` 可脱离主服务单独运行和调试
- MCP 单测走 `FakeMCPToolClient`（同进程直连业务逻辑，无子进程开销），真实协议路径由独立的 `tests/test_mcp_integration.py` 覆盖，兼顾测试速度和协议可信度
- RAG 知识库覆盖退款、物流、发票、保修、账号安全、会员积分、优惠券、故障排查、订单管理、支付、换货、客服工单 12 个场景，文档故意用不同结构（表格、FAQ、规则条款）覆盖分块和检索的多样性；`TextSplitter` 按 Markdown 标题维护面包屑上下文，避免只召回到孤立标题
- 检索层用 `ChromaVectorStore`（真实持久化向量库）+ 手写 `BM25Index`（`jieba` 分词）做 RRF 混合排序，并配了一份覆盖 103 个证据 Chunk 的 140 条挑战集和评估脚本（`app/rag/evaluation.py`），能分别量化证据 Recall/MRR 与无答案拒答能力
- 订单查询按 `user_id` 做权限校验，避免越权访问其他用户订单
- 工单测试通过 pytest `tmp_path` 隔离测试数据，避免污染 `data/mock_tickets.json`
- 使用 Redis List 按 `session_id` 保存最近 10 条用户/助手消息，`LTRIM` 控制窗口、`EXPIRE` 刷新 24 小时 TTL，Redis异常时自动降级为内存窗口
- 在写入当前消息前读取最近历史，同时注入 LLM 意图识别与 ResponseAgent Prompt；`MemoryAgent` 继续支持显式的历史问题查询
- 分层记忆：短期 Redis 保存有序、短生命周期的原始对话；长期 `UserMemoryStore` 保存跨 session、按 `user_id` 隔离的稳定事实。`MemoryExtractionAgent` 每轮结束后判断有没有信息值得记住，不会把超窗消息或一次性订单查询直接搬入长期向量库
- 长期记忆的读写也统一走 MCP 工具（`recall_user_memory`/`save_user_memory`），和订单/工单/知识库保持同样的架构，不是单独开的后门
- 通过 `ResponseAgent` 接入 OpenAI-compatible LLM，让模型参与客服回复生成，业务事实来自 MCP 工具层、个性化信息来自长期记忆，两者都不是模型编造的
- 输入脱敏前置：图入口 `sanitize` 节点在任何 memory 写入和 LLM 调用之前完成 PII 打码（手机号/身份证/银行卡/邮箱），下游链路只看到脱敏后的文本；输出侧 `review_compliance` 复用同一套规则（`app/compliance/pii.py`），保证前后端脱敏口径一致
- `trace` 字段展示 LangGraph 节点和 MCP 工具调用链，方便调试、演示和后续接入 OpenTelemetry
- 提供 `Dockerfile`/`docker-compose.yml`，一条命令即可跑起来，不需要本地装 Python 环境；已实测容器内 MCP 子进程拉起、chromadb 向量检索、BM25 分词（jieba）全链路正常

## 已知局限

- `ChromaVectorStore` 每次懒加载都会整体删除重建 collection，没有增量同步/去重机制；知识库规模小的时候没问题，规模变大后需要改成基于内容 hash 的增量更新。
- 首次触发检索时会对全部 chunk（目前 126 个）依次调用 embedding 接口，没有做批量请求，真实 Qwen embedding 下冷启动有明显延迟。
- RRF 混合检索在真实高质量 embedding 下收益很小（见上面的评估结果），价值主要体现在 embedding 较弱的场景。
- 长期记忆的抽取是每轮对话结束后都同步调一次 LLM，会给每轮请求增加一次额外的 LLM 调用延迟；生产环境更合理的做法是异步/批量抽取，不阻塞当轮响应。
- `UserMemoryStore` 没有去重/合并机制：用户反复表达同一个偏好会存成多条相似记录，没有做"更新已有记忆"而是每次都新增。
- 长期记忆没有过期/衰减机制，理论上会无限增长；也没有让用户查看或删除自己被记住了什么信息的接口。
- Redis保存的是最近原始对话，目前只做TTL与固定窗口控制；生产环境还需要补充传输加密、访问权限、敏感输入前置脱敏和会话撤销策略。

## 后续规划

- 引入 LLM 深度合规审查，补充当前规则合规审查
- 引入 OpenTelemetry 记录 Agent 调用链和 MCP 工具耗时
- 增加前端聊天页面，展示用户对话和 Agent 执行过程
- 知识库检索改成增量同步 + 批量 embedding，去掉每次全量重建的开销
- 将逐条 Embedding 改为批量请求并缓存评测向量，降低 Reranker 消融实验的冷启动耗时
- 长期记忆抽取改成异步/批量，避免每轮对话都同步增加一次 LLM 调用延迟
- 长期记忆加去重/合并逻辑（比如同一 category 下语义相似的记忆合并更新），并加一个"查看/删除我的记忆"的接口
