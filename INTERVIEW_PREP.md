# 面试准备：Customer Service Agent 项目复盘

这份文档是给自己看的面试速查表，不是项目对外文档（README 是对外的）。目标是把这个项目里做过的技术决策、踩过的坑、量化数据整理成能脱口而出的内容。

## 一句话介绍

基于 FastAPI + LangGraph 的多 Agent 电商客服系统：意图识别路由到订单/退款/工单/记忆等业务 Agent，业务 Agent 不直接访问数据，而是通过一个真实的 MCP（Model Context Protocol）Server 调用工具；知识库问答用 RAG（分块 + 向量检索 + BM25 混合检索），有量化的检索效果评估；记忆分短期 session 滑动窗口和长期跨 session 向量记忆两层，长期记忆由 LLM 每轮抽取、检索后注入回复生成的 Prompt。

## 技术栈速查

- **编排**：LangGraph StateGraph（条件边路由）
- **协议层**：官方 `mcp` SDK（`FastMCP` 建 server，`ClientSession` + stdio 建 client）
- **LLM**：Qwen（`qwen-plus`），OpenAI-compatible 接口
- **Embedding**：Qwen `text-embedding-v4`，OpenAI-compatible 接口
- **向量库**：`chromadb`（PersistentClient，本地持久化，知识库检索和长期记忆各用一个独立 collection）
- **关键词检索**：手写 BM25 + `jieba` 分词
- **测试**：pytest，99 个测试，约 5 秒跑完

## 架构分层（面试官问"讲讲你的架构"）

```
FastAPI /chat
  → Supervisor（图执行入口）
    → LangGraph StateGraph（intent/order/refund/ticket/memory/fallback/memory_recall/response/compliance/memory_extraction 10 个节点）
      → 业务 Agent（OrderAgent/RAGAgent/TicketAgent/LongTermMemoryAgent，只持有一个 mcp_client）
        → MCPToolClient（stdio 子进程 + JSON-RPC，真实协议，不是包装）
          → MCP Server（FastMCP，注册 7 个工具）
            → handlers.py（纯函数业务逻辑，server 和测试用的 FakeMCPToolClient 共用）
              → 订单/工单 mock json、RAG 检索栈、长期记忆向量库、合规审查正则
```

分层动机：**Agent 层不知道工具是怎么实现的，只知道调用 MCP 工具**。这样订单系统、工单系统、知识库以后换成真实后端服务，只需要改 `handlers.py`，Agent 和 Graph 完全不用动。

## MCP 部分（最容易被深挖的地方）

### 为什么真的接 MCP，不是包一层假协议

一开始想过做一个"看起来像 MCP"的内部抽象就算了，但那样面试被问"MCP 具体怎么实现的"会露怯。最终用官方 `mcp` SDK 走完整的 stdio + JSON-RPC 协议：`app/mcp/server.py` 用 `FastMCP` 注册工具，`app/mcp/client.py` 是真的 spawn 一个子进程、走 `stdio_client` + `ClientSession`。可以用 `python -m app.mcp.server` 单独跑，也可以用 `mcp dev app/mcp/server.py` 接 Inspector 可视化调试——这是判断"真的懂协议"还是"只是抄了个 demo"的分水岭。

### 同步桥接的坑（真实踩过的 bug，讲出来加分）

Agent 层和 FastAPI 路由都是同步代码，但 MCP SDK 是 asyncio 原生的。第一版实现里，我在后台线程起了一个 event loop，`_connect()` 里用 `run_coroutine_threadsafe` 进入 `stdio_client`/`ClientSession` 的 `async with`，然后 `close()` 时又单独用一次 `run_coroutine_threadsafe` 去 `stack.aclose()`——结果报错：

```
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
```

原因是 anyio 的 `CancelScope`/`TaskGroup` 有 task 亲和性，**进入和退出必须在同一个 task 里**，而我这两次 `run_coroutine_threadsafe` 各自建了一个新 task。

修复方式：改成一个**长期运行的单一协程**（`_runner`），`async with` 只在这一个协程里进入和退出；调用方通过 `asyncio.Queue` 把 `(name, arguments, result_future)` 丢进去，`_runner` 循环消费，结果通过 `concurrent.futures.Future` 带回调用线程。收到 `None` 哨兵值就退出循环，让 `async with` 自然收尾。

这是一个很好的"我不只是会调 API，还理解 asyncio/anyio 底层机制"的例子。

### 环境变量传递的安全细节

MCP SDK 的 `stdio_client` 默认**不会**把父进程完整的环境变量传给子进程，只传一个白名单（POSIX 下是 `HOME/LOGNAME/PATH/SHELL/TERM/USER`）——这是官方 SDK 出于安全考虑的设计（防止意外泄露密钥给不受信的子进程）。因为这里的子进程是我自己写的、受信的本地服务，所以我显式把完整 `os.environ` 传过去，再叠加 `TICKETS_FILE`/`CHROMA_PERSIST_DIR` 这类测试专用的覆盖值。如果面试官问"你了解 MCP 的安全模型吗"，这是一个具体例子。

### 返回值 schema 的坑

FastMCP 的 `structuredContent` 字段：如果工具返回类型标注是裸 `dict`/`list`/`X | None`，SDK 会自动包一层 `{"result": ...}`（因为协议要求 structured content 必须是 JSON object，非 object 类型就包一层）；只有标注成 `dict[str, Any]`（非 Optional）时才会直接给干净的 dict。所以我把每个工具的返回值都设计成"永远是一个有意义字段名的 object"，比如 `{"found": bool, "order": ...}`、`{"chunks": [...]}`，而不是依赖 SDK 的自动包装行为——更自解释，也避免了"这个 key 到底是 result 还是业务字段"的歧义。

### Fake / Real 分层测试

仓库里 LLM 和 Embedding 都是这个模式（`FakeLLMClient`/`FakeEmbeddingClient` vs 真实 client），MCP 客户端延续了同样的约定：

- `FakeMCPToolClient`：同进程直接调用 `handlers.py`，无子进程开销，单测秒级跑完
- `MCPToolClient`：真实 stdio 子进程，只在 `tests/test_mcp_integration.py` 里用，证明协议真的通

一开始把测试都切到 `FakeMCPToolClient` 之后忘了给 RAG 检索也传 Fake embedding，结果单测意外命中了 `.env` 里配置的真实 Qwen embedding API，一条单测跑到 40+ 秒；知识库目前已扩到 12 篇（126 个 chunk），冷启动真实 embedding 更慢。这个经历可以用来回答"你怎么保证测试速度和真实性两不误"——答案是显式传 Fake 依赖，而不是依赖全局配置/环境变量的默认值。

加长期记忆的时候踩了同一个坑：`UserMemoryStore` 没有纯内存实现（底层是 chromadb），Supervisor 层的测试如果不显式传一个 `tmp_path`/临时目录隔离的 store，就会落到 `data/user_memory_db` 这个真实目录、用真实 embedding——所以 `create_test_supervisor` 里专门写了个 `_fake_memory_store()`，每次用 `tempfile.mkdtemp()` 生成一个全新的临时目录，避免测试之间互相污染，也避免打真实 API。

## RAG 部分

### 分块策略：标题面包屑

最早的分块逻辑是纯按空行切段落，如果段落是 Markdown 标题（`# xxx`），会被切成单独一个 chunk——检索出来经常是光秃秃的标题，没有正文。扩充知识库、引入多级标题结构后这个问题变得更明显。修复方式：维护一个按标题层级（`#`/`##`/...）的 heading_stack，正文 chunk 会带上"面包屑"前缀（比如 `# 退款退货政策 > ## 无理由退货`），标题本身不再单独成 chunk。

### 检索策略：向量 + BM25，RRF 融合

- 向量检索：`ChromaVectorStore`（真实持久化 ANN 索引，cosine 距离），替换掉最初暴力线性扫描的 `InMemoryVectorStore`（后者保留作为评估 baseline，没删）
- 关键词检索：手写 `BM25Index`（标准 Okapi BM25 公式，k1=1.5, b=0.75），用 `jieba.cut_for_search` 做中文分词，没有引入 `rank_bm25` 依赖
- 融合：Reciprocal Rank Fusion（RRF），`score = Σ 1/(rrf_k + rank + 1)`，rrf_k 默认 60。选 RRF 而不是加权求和的原因：两路分数量纲完全不同（cosine 相似度 vs BM25 分数），RRF 只看排名不看绝对分数，不需要做归一化调参

### 评估：不是拍脑袋判断效果

重构了 `data/eval/retrieval_qa.json`：140 条样本包含 103 条单证据、20 条严格多证据和 17 条无答案，覆盖 103 个独立证据 Chunk。多证据题必须把所需 Chunk 全部召回才算命中；无答案不混进 Recall，而是单算拒答准确率。标签先以 `draft_pending_human_review` 保存，逐条人工复核后才可对外称人工标注。

| 配置 | Fake 来源R@3 | Fake 证据R@3 | Qwen 来源R@3 | Qwen 证据R@3 |
| --- | ---: | ---: | ---: | ---: |
| naive（InMemory，纯向量） | 35.8% | 10.6% | **94.3%** | **88.6%** |
| chroma（纯向量） | 35.8% | 10.6% | **94.3%** | **88.6%** |
| chroma + BM25（混合） | **73.2%** | **49.6%** | **94.3%** | 87.0% |
| RRF Top 20 + qwen3-rerank | — | — | **95.9%** | **94.3%** |

将知识段落改成同时包含主规则、例外条件和关联流程后，真实 Qwen 纯向量的证据 R@3/MRR 为 88.6%/0.770，加入 BM25 + RRF 后为 87.0%/0.755。混合检索没有提高严格证据召回，说明强 embedding 下 BM25 仍会引入排序噪声。三种无阈值 Retriever 都会返回候选，所以无答案拒答准确率是 0%；这正是 `EvidenceGate` 需要单独校准和评估的原因。

进一步把混合检索候选池扩大到 Top 20 后，真实 Qwen 的证据 Recall@20 为 99.2%，明显高于最终 Recall@3 的 87.0%。这说明当前主要问题是排序而不是召回，因此接入 `qwen3-rerank`：RRF 先融合 Top 20，再由独立排序模型精排为 Top 3。真实消融后证据 Recall@3 从 87.0% 提升到 94.3%，MRR 从 0.755 提升到 0.850；140 条冷启动端到端耗时 188.7 秒，平均每条约 1.35 秒。开启生产开关后一度导致 Fake Embedding 测试误调真实 API，最终在工厂层规定 Fake 依赖自动禁用外部 Reranker，恢复为完全离线测试。

### 最终回答评测

另建了 `data/eval/answer_qa.json`，包含 60 条人工标注样本：48 条可回答、12 条无答案，按 40/20 划分开发集和测试集。标注不做字符串全等，而是记录 `reference_answer`、`required_facts`、`forbidden_facts`、正确来源和拒答标签。

`python -m app.rag.answer_evaluation --split test` 会实际执行 Retriever → ResponseAgent → ComplianceAgent，输出来源命中、必要事实规则通过率和无答案拒答准确率；加 `--llm-judge` 后再由独立裁判模型输出 correctness、faithfulness、completeness 和 pass/fail。裁判默认关闭，避免自动产生费用。

检索后增加了 `EvidenceGate`，不使用只反映相对名次的 RRF 分数做阈值，而是组合原始向量相似度、BM25 分数和查询词项覆盖率；证据不足时返回空候选并拒答。Fake LLM/Fake embedding 的 20 条测试集上，加入 Gate 前后来源命中率均为 75%，规则回答准确率从 30% 提升到 45%，无答案拒答准确率从 0% 提升到 75%；40 条开发集拒答准确率为 87.5%。当前阈值只针对 Fake embedding 开发集校准，换真实 Qwen 后必须按新的分数分布重新校准。

真实 Qwen embedding + Fake LLM 的 20 条测试集诊断结果：可回答问题来源 Hit@3 为 93.75%（15/16），无答案拒答准确率为 50%（2/4），规则覆盖率为 80%。80% 不能叫最终回答准确率，因为 Fake LLM 直接返回检索上下文；这组结果主要证明 Fake embedding 上校准的 Gate 阈值无法直接迁移到 Qwen。

## 长期记忆部分

### 为什么是"分层"，而不是把窗口开大点

短期记忆已经从进程内 `SessionMemory` 升级为可插拔的 `RedisSessionMemory`：使用 List 按 `session_id` 保存最近 10 条消息，追加后裁剪窗口并刷新 24 小时 TTL，服务重启和多实例之间可以共享；Redis连接失败时自动降级为内存实现。每轮在写入当前消息前读取历史，分别注入 LLM 意图识别和 `ResponseAgent` Prompt，因此不再只是回答“刚才问了什么”，也能帮助理解“那多久”“这个呢”等多轮省略。

分层的思路（参考 MemGPT/Letta 的 core memory + archival memory）：短期负责"这句话是不是在追问上一句"，长期负责"这个用户一直以来有什么稳定的偏好/历史"，两者解决的是不同的问题，不能互相替代。

### 抽取：为什么是"LLM 判断该不该记"，不是"每轮都记"

`MemoryExtractionAgent` 每轮对话结束后调 LLM，让模型自己判断这轮里有没有稳定的、以后还有参考价值的信息，允许的 category 只有四类：`preference`（商品偏好）、`contact`（收货/联系偏好）、`complaint_history`（投诉历史摘要）、`communication_style`（沟通风格）。Prompt 里明确要求"大多数轮次应该输出空列表，不要为了有输出而编造"——这是为了避免把"查个物流"这种一次性信息也当成"记忆"存下来，造成长期记忆库被大量无意义信息淹没。解析逻辑复用了 `LLMIntentAgent` 那套风格：`json.loads` 失败、或者 category 不在白名单里，都直接丢弃返回空列表，不抛异常影响主流程。

### 为什么长期记忆的读写也走 MCP，不直接调 Python 对象

订单、工单、知识库检索都已经通过 MCP 统一了工具调用协议，如果长期记忆单独走一条"Agent 直接持有 Store 对象"的路径，架构上就不一致了——面试官很容易追问"为什么这个不走 MCP"。新增 `recall_user_memory`/`save_user_memory` 两个工具后，MCP Server 现在一共暴露 7 个工具，所有工具调用都经过同一层协议，没有例外。

### 存储设计：复用 chromadb，但是独立的 collection

`UserMemoryStore`（`app/memory/long_term_store.py`）和知识库检索用的 `ChromaVectorStore` 是同一个库（chromadb），但持久化目录和 collection 完全独立（`data/user_memory_db` vs `data/chroma_db`），语义也不同：知识库是"全局共享、按内容检索"，长期记忆是"per-user 隔离、按 `user_id` 过滤 + 语义检索"（用 chroma 的 `where={"user_id": ...}` 做隔离）。复用同一个库而不是重新选型，是因为这两个场景对向量存储的需求（持久化、cosine 相似度检索）本质上是一样的，没必要引入第二套技术栈。

### 注入：格式化成一段文本塞进 Prompt

`LongTermMemoryAgent.recall()` 把检索到的记忆格式化成"已知用户信息：\n- xxx\n- yyy"这样一段纯文本，`ResponseAgent.generate()` 透传给 `OpenAICompatibleClient`，在 prompt 里加一段【已知用户信息】。这里故意没有做更复杂的结构化注入（比如按 category 分组、加权），因为对于生成客服回复这个场景，一段自然语言的上下文足够让 LLM"自然地体现出来，但不生硬复述"（prompt 里也是这么明确要求的）。

## 已知局限（诚实清单，主动暴露比被问到答不上来强）

1. **意图路由要跟着知识库扩充**：第一轮从单一退款扩到会员、优惠和故障文档时，`HybridIntentAgent` 没同步更新，问题会被分到 `unknown`；修完第一轮后，本次又新增订单、支付、换货和客服规则，同样需要继续补业务意图与知识问答意图的边界回归。这说明检索层指标好不代表端到端一定能走到 RAG。
2. `ChromaVectorStore` 每次懒加载都整体删除重建 collection，没有增量同步；这个规模下（126 个 chunk）尚可，规模变大需要改成基于内容 hash 的增量更新。
3. 首次检索会对全部 chunk 顺序调用 embedding 接口，没有批量请求，真实 embedding 下冷启动有几十秒延迟。
4. RRF 混合检索不是万能药，见上面评估结果的结论。
5. qwen3-rerank 已证明能提高证据排序，但当前评测会逐条调用 Embedding/Rerank，尚未实现批量请求、结果缓存和生产级限流降级。
6. **长期记忆抽取是每轮同步调 LLM**：每轮对话都多一次 LLM 调用延迟，没有做异步/批量处理——这是在"简单可测试"和"低延迟"之间做的取舍，已知但没优化。
7. **长期记忆没有去重/合并**：用户反复表达同一个偏好会存成好几条相似记录，没有"发现已有相似记忆就更新"的逻辑，长期记忆库会有冗余。
8. **长期记忆没有过期机制**：理论上会无限增长，也没有给用户提供"查看/删除我被记住的信息"的接口（这一点也涉及数据合规，值得在面试里主动提一句）。

## 高频追问预案

**Q: 为什么用 LangGraph，不自己写个 if-else 状态机？**
A: StateGraph 把节点和路由分开，新增一个业务分支只需要加一个节点 + 一条条件边，不用改已有节点的代码；`trace` 字段能直接从图执行过程里拿到调用链，不需要额外埋点。规模小的时候手写 if-else 也能做，但这个项目本来就是想练边界清晰的多 Agent 编排。

**Q: MCP 和你直接封装一层 HTTP/RPC 接口有什么区别？**
A: MCP 是标准化协议（工具 schema、session 生命周期都有规范），生态上可以直接被 Claude Desktop、MCP Inspector 这类通用客户端消费，不需要为每个工具写专属的调用约定。我自己写的 client/server 之间也是走的标准 JSON-RPC，不是私有格式。

**Q: 混合检索的 RRF 怎么实现的，为什么不用加权求和？**
A: 分别拿向量检索和 BM25 的 top-N 候选，按各自排名算 `1/(k+rank+1)` 再累加。RRF 的好处是不需要对两路分数做归一化——cosine 相似度和 BM25 分数量纲完全不一样，加权求和得先解决怎么归一化、权重怎么调的问题，RRF 绕开了这个麻烦。

**Q: 你怎么评估 RAG 效果的？**
A: 做了 140 条检索挑战集，覆盖 103 个独立证据 Chunk，其中有 20 条必须同时召回多个证据，另有 17 条知识库无答案问题。真实 Qwen 混合检索证据 Recall@3 为 87.0%，但候选 Recall@20 有 99.2%，所以瓶颈是排序；接入 qwen3-rerank 后 Recall@3 提升到 94.3%，MRR 从 0.755 提升到 0.850。当前标签仍待人工复核，所以面试时不会把 AI 草拟标签冒充成已完成人工标注。

**Q: 项目最大的短板是什么？**
A: 意图路由的分类体系没有跟着知识库扩充同步升级，导致新增的 7 篇文档在真实对话链路里基本触发不到，这是手动做端到端测试时才发现的——说明只做检索层的单元测试和评估脚本是不够的，还得走一遍真实的意图分类→路由链路。

**Q: 生产环境这套设计有什么风险？**
A: chroma 每次懒加载都全量重建 collection，数据量大了之后重建成本会变高；MCP 走 stdio 子进程，每个 Supervisor 实例对应一个子进程，高并发场景需要考虑连接池化而不是一对一起子进程；长期记忆每轮同步调 LLM 抽取会拖慢响应延迟。

**Q: 短期记忆和长期记忆分别解决什么问题，为什么不能只要一个？**
A: 短期记忆使用 Redis List 保存同一 session 最近 10 条原始消息并设置 TTL，按时间顺序注入意图识别和回复生成，解决“刚才说了什么”和多轮指代；长期记忆使用 Chroma 按 `user_id` 保存LLM筛选后的稳定用户事实，通过语义检索解决跨会话偏好召回。超窗消息不会自动写入长期库，两层的生命周期、数据形态和访问方式完全不同。

**Q: 怎么避免长期记忆把没用的信息也存进去？**
A: 靠 `MemoryExtractionAgent` 的 LLM 抽取做"过滤"：Prompt 里限定只有商品偏好/联系偏好/投诉历史/沟通风格四类允许存，并且明确告诉模型大多数轮次应该输出空列表。当然这不是完美方案，没有做去重，模型偶尔也可能误判，这是已知局限，后续可以加规则兜底或者定期做记忆合并清理。

**Q: 长期记忆的读写为什么也要走 MCP，不嫌麻烦吗？**
A: 是为了架构一致性——项目里订单、工单、知识库全部都通过 MCP 统一了工具调用，如果长期记忆单独开一条近路，会破坏"所有外部能力都是 MCP 工具"这个统一抽象，以后也不好维护。多两个工具的成本（`recall_user_memory`/`save_user_memory`）远小于架构不一致带来的维护成本。

## 关键数字速查

- 知识库：12 篇文档，126 个 chunk
- MCP 工具：7 个（`get_order`/`create_ticket`/`query_ticket`/`search_knowledge_base`/`recall_user_memory`/`save_user_memory`/`review_compliance`）
- LangGraph 节点：10 个（intent/order/refund/ticket/memory/fallback/memory_recall/response/compliance/memory_extraction）
- 长期记忆类别：4 类（preference/contact/complaint_history/communication_style）
- 测试：99 个，约 5 秒跑完
- 检索评估集：140 条，覆盖 103 个独立证据 Chunk（103 单证据、20 多证据、17 无答案）
- 弱 embedding 来源级：纯向量 Recall@3 35.8%，混合检索 73.2%
- 真实 Qwen 纯向量证据级指标：Recall@3 88.6%，MRR 0.770
- 真实 Qwen 混合候选池：证据 Recall@20 99.2%；qwen3-rerank 后 Recall@3 94.3%、MRR 0.850
