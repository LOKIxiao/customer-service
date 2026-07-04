from pathlib import Path

from app.agents.compliance_agent import ComplianceAgent
from app.agents.intent_agent import IntentAgent
from app.agents.order_agent import OrderAgent
from app.agents.refund_policy_agent import RefundPolicyAgent
from app.agents.ticket_agent import TicketAgent
from app.schemas.chat import ChatRequest, ChatResponse




class Supervisor:
    def __init__(self, tickets_file: Path | None = None) -> None:
        self.intent_agent = IntentAgent()
        self.order_agent = OrderAgent()
        self.compliance_agent = ComplianceAgent()
        self.refund_policy_agent = RefundPolicyAgent()
        self.ticket_agent = TicketAgent(tickets_file=tickets_file) if tickets_file else TicketAgent()

    def handle(self, request: ChatRequest) -> ChatResponse:
        trace = ['ChatAPI', 'Supervisor']

        intent_result = self.intent_agent.classify(request.message)
        trace.append('IntentAgent')

        if intent_result.intent == 'order_query':
            raw_reply = self.order_agent.handle(
                user_id=request.user_id,
                slots=intent_result.slots,
            )
            trace.extend(["OrderAgent", "OrderTools"])
        
        elif intent_result.intent == 'refund_policy':
            raw_reply = self.refund_policy_agent.handle(request.message)
            trace.extend(['RefundPolicyAgent', 'KnowledgeBase'])
        
        elif intent_result.intent in ['ticket_create', 'ticket_query']:
            raw_reply = self.ticket_agent.handle(
                user_id=request.user_id,
                intent=intent_result.intent,
                message=request.message,
            )
            trace.extend(["TicketAgent", "TicketTools"])

        
        else:
            raw_reply = f"我识别到你的意图是 {intent_result.intent}，但这个业务 Agent 还没有接入。"

        compliance_result = self.compliance_agent.review(raw_reply)
        trace.append("ComplianceAgent")

        return ChatResponse(
            reply=compliance_result.response,
            intent=intent_result.intent,
            trace=trace,
        )
