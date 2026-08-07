from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.hybrid_intent_agent import HybridIntentAgent
from app.agents.long_term_memory_agent import LongTermMemoryAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.memory_extraction_agent import MemoryExtractionAgent
from app.agents.order_agent import OrderAgent
from app.agents.response_agent import ResponseAgent
from app.agents.ticket_agent import TicketAgent
from app.compliance.pii import mask_pii
from app.llm.base import BaseLLMClient
from app.memory.session_memory import SessionMemory
from app.agents.rag_agent import RAGAgent


class CustomerServiceState(TypedDict):
    user_id: str
    session_id: str
    message: str
    intent: str
    slots: dict[str, str]
    raw_reply: str
    long_term_context: str
    conversation_history: str
    final_reply: str
    trace: list[str]


def create_customer_service_graph(
    intent_agent: HybridIntentAgent,
    order_agent: OrderAgent,
    rag_agent: RAGAgent,
    ticket_agent: TicketAgent,
    long_term_memory_agent: LongTermMemoryAgent,
    memory_extraction_agent: MemoryExtractionAgent,
    mcp_client: Any,
    memory: SessionMemory,
    llm_client: BaseLLMClient,
):
    memory_agent = MemoryAgent(memory)
    response_agent = ResponseAgent(llm_client)

    def format_history(session_id: str) -> str:
        role_names = {"user": "用户", "assistant": "客服"}
        return "\n".join(
            f"{role_names.get(message.role, message.role)}：{message.content}"
            for message in memory.get_messages(session_id)
        )

    def sanitize_node(state: CustomerServiceState) -> CustomerServiceState:
        # 输入脱敏前置：在写入会话记忆、调用意图/回复 LLM 之前，
        # 先把用户消息里的手机号、身份证、银行卡、邮箱等 PII 打码。
        # 之后整条链路（memory、LLM、trace）看到的都是脱敏后的文本。
        masked_message = mask_pii(state["message"])
        return {
            **state,
            "message": masked_message,
            "trace": state["trace"] + ["InputSanitizer"],
        }

    def intent_node(state: CustomerServiceState) -> CustomerServiceState:
        conversation_history = format_history(state["session_id"])
        memory.add_message(state["session_id"], "user", state["message"])

        intent_result = intent_agent.classify(
            state["message"],
            conversation_history=conversation_history,
        )
        return {
            **state,
            "intent": intent_result.intent,
            "slots": intent_result.slots,
            "conversation_history": conversation_history,
            "trace": state["trace"] + ["IntentAgent"],
        }

    def order_node(state: CustomerServiceState) -> CustomerServiceState:
        raw_reply = order_agent.handle(state["user_id"], state["slots"])
        return {
            **state,
            "raw_reply": raw_reply,
            "trace": state["trace"] + ["OrderAgent", "MCP:get_order"],
        } # 生成回复

    def knowledge_node(state: CustomerServiceState) -> CustomerServiceState:
        raw_reply = rag_agent.handle(state["message"])
        return {
            **state,
            "raw_reply": raw_reply,
            "trace": state["trace"] + ["RAGAgent", "MCP:search_knowledge_base"],
        }

    def ticket_node(state: CustomerServiceState) -> CustomerServiceState:
        raw_reply = ticket_agent.handle(
            user_id=state["user_id"],
            intent=state["intent"],
            message=state["message"],
        )
        tool_name = "create_ticket" if state["intent"] == "ticket_create" else "query_ticket"
        return {
            **state,
            "raw_reply": raw_reply,
            "trace": state["trace"] + ["TicketAgent", f"MCP:{tool_name}"],
        }

    def memory_node(state: CustomerServiceState) -> CustomerServiceState:
        raw_reply = memory_agent.handle(state["session_id"])
        return {
            **state,
            "raw_reply": raw_reply,
            "trace": state["trace"] + ["MemoryAgent"],
        }

    def fallback_node(state: CustomerServiceState) -> CustomerServiceState:
        raw_reply = f"我识别到你的意图是 {state['intent']}，但这个业务 Agent 还没有接入。"
        return {**state, "raw_reply": raw_reply}

    def memory_recall_node(state: CustomerServiceState) -> CustomerServiceState:
        long_term_context = long_term_memory_agent.recall(state["user_id"], state["message"])
        return {
            **state,
            "long_term_context": long_term_context,
            "trace": state["trace"] + ["LongTermMemoryAgent", "MCP:recall_user_memory"],
        }

    def response_node(state: CustomerServiceState) -> CustomerServiceState:
        reply = response_agent.generate(
            user_message=state["message"],
            intent=state["intent"],
            raw_reply=state["raw_reply"],
            long_term_context=state["long_term_context"],
            conversation_history=state["conversation_history"],
        )
        return {
            **state,
            "raw_reply": reply,
            "trace": state["trace"] + ["ResponseAgent"],
        }

    def compliance_node(state: CustomerServiceState) -> CustomerServiceState:
        result = mcp_client.call_tool("review_compliance", {"text": state["raw_reply"]})
        memory.add_message(state["session_id"], "assistant", result["response"])

        return {
            **state,
            "final_reply": result["response"],
            "trace": state["trace"] + ["ComplianceAgent", "MCP:review_compliance"],
        }

    def memory_extraction_node(state: CustomerServiceState) -> CustomerServiceState:
        facts = memory_extraction_agent.extract(state["message"], state["final_reply"])
        trace = state["trace"] + ["MemoryExtractionAgent"]

        if facts:
            long_term_memory_agent.remember(state["user_id"], facts)
            trace = trace + ["MCP:save_user_memory"]

        return {**state, "trace": trace}

    # 路由器，分配
    def route_by_intent(state: CustomerServiceState) -> str:
        intent = state["intent"]

        if intent == "order_query":
            return "order"
        if intent == "knowledge_base_query":
            return "knowledge"
        if intent in ["ticket_create", "ticket_query"]:
            return "ticket"
        if intent == "memory_query":
            return "memory"

        return "fallback"

    graph = StateGraph(CustomerServiceState)

    graph.add_node("sanitize", sanitize_node)
    graph.add_node("intent", intent_node)
    graph.add_node("order", order_node)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("ticket", ticket_node)
    graph.add_node("memory", memory_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("memory_recall", memory_recall_node)
    graph.add_node("response", response_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("memory_extraction", memory_extraction_node)

    # 首先做输入脱敏，再进入意图识别
    graph.set_entry_point("sanitize")
    graph.add_edge("sanitize", "intent")

    graph.add_conditional_edges(
        "intent",
        route_by_intent,
        {
            "order": "order",
            "knowledge": "knowledge",
            "ticket": "ticket",
            "memory": "memory",
            "fallback": "fallback",
        },
    )

    graph.add_edge("order", "memory_recall")
    graph.add_edge("knowledge", "memory_recall")
    graph.add_edge("ticket", "memory_recall")
    graph.add_edge("memory", "memory_recall")
    graph.add_edge("fallback", "memory_recall")
    graph.add_edge("memory_recall", "response")
    graph.add_edge("response", "compliance")
    # 返回compliance节点，减少幻觉
    graph.add_edge("compliance", "memory_extraction")
    graph.add_edge("memory_extraction", END)


    return graph.compile()
