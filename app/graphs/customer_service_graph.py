from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents.compliance_agent import ComplianceAgent
from app.agents.intent_agent import IntentAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.order_agent import OrderAgent
from app.agents.refund_policy_agent import RefundPolicyAgent
from app.agents.ticket_agent import TicketAgent
from app.memory.session_memory import SessionMemory


class CustomerServiceState(TypedDict):
    user_id: str
    session_id: str
    message: str
    intent: str
    slots: dict[str, str]
    raw_reply: str
    final_reply: str
    trace: list[str]


def create_customer_service_graph(
    intent_agent: IntentAgent,
    order_agent: OrderAgent,
    refund_policy_agent: RefundPolicyAgent,
    ticket_agent: TicketAgent,
    compliance_agent: ComplianceAgent,
    memory: SessionMemory,
):
    memory_agent = MemoryAgent(memory)

    def intent_node(state: CustomerServiceState) -> CustomerServiceState:
        memory.add_message(state["session_id"], "user", state["message"])

        intent_result = intent_agent.classify(state["message"])
        return {
            **state,
            "intent": intent_result.intent,
            "slots": intent_result.slots,
            "trace": state["trace"] + ["IntentAgent"],
        }
    
    def order_node(state: CustomerServiceState) -> CustomerServiceState:
        raw_reply = order_agent.handle(state["user_id"], state["slots"])
        return {
            **state,
            "raw_reply": raw_reply,
            "trace": state["trace"] + ["OrderAgent", "OrderTools"],
        } # 生成回复
    
    def refund_node(state: CustomerServiceState) -> CustomerServiceState:
        raw_reply = refund_policy_agent.handle(state["message"])
        return {
            **state,
            "raw_reply": raw_reply,
            "trace": state["trace"] + ["RefundPolicyAgent", "KnowledgeBase"],
        }

    def ticket_node(state: CustomerServiceState) -> CustomerServiceState:
        raw_reply = ticket_agent.handle(
            user_id=state["user_id"],
            intent=state["intent"],
            message=state["message"],
        )
        return {
            **state,
            "raw_reply": raw_reply,
            "trace": state["trace"] + ["TicketAgent", "TicketTools"],
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

    def compliance_node(state: CustomerServiceState) -> CustomerServiceState:
        result = compliance_agent.review(state["raw_reply"])
        memory.add_message(state["session_id"], "assistant", result.response)

        return {
            **state,
            "final_reply": result.response,
            "trace": state["trace"] + ["ComplianceAgent"],
        }
    
    # 路由器，分配
    def route_by_intent(state: CustomerServiceState) -> str:
        intent = state["intent"]

        if intent == "order_query":
            return "order"
        if intent == "refund_policy":
            return "refund"
        if intent in ["ticket_create", "ticket_query"]:
            return "ticket"
        if intent == "memory_query":
            return "memory"

        return "fallback"
    
    graph = StateGraph(CustomerServiceState)

    graph.add_node("intent", intent_node)
    graph.add_node("order", order_node)
    graph.add_node("refund", refund_node)
    graph.add_node("ticket", ticket_node)
    graph.add_node("memory", memory_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("compliance", compliance_node)

    #首先intent节点处理
    graph.set_entry_point("intent")

    graph.add_conditional_edges(
        "intent",
        route_by_intent,
        {
            "order": "order",
            "refund": "refund",
            "ticket": "ticket",
            "memory": "memory",
            "fallback": "fallback",
        },
    )

    graph.add_edge("order", "compliance")
    graph.add_edge("refund", "compliance")
    graph.add_edge("ticket", "compliance")
    graph.add_edge("memory", "compliance")
    graph.add_edge("fallback", "compliance")
    # 返回compliance节点，减少幻觉
    graph.add_edge("compliance", END)
    

    return graph.compile()
