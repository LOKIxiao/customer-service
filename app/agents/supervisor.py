from pathlib import Path

from app.agents.compliance_agent import ComplianceAgent
from app.agents.intent_agent import IntentAgent
from app.agents.order_agent import OrderAgent
from app.agents.refund_policy_agent import RefundPolicyAgent
from app.agents.ticket_agent import TicketAgent
from app.graphs.customer_service_graph import create_customer_service_graph
from app.llm.base import BaseLLMClient
from app.llm.factory import create_llm_client
from app.memory.session_memory import SessionMemory
from app.schemas.chat import ChatRequest, ChatResponse


class Supervisor:
    def __init__(
        self,
        tickets_file: Path | None = None,
        memory: SessionMemory | None = None,
        llm_client: BaseLLMClient | None = None,
    ) -> None:
        self.memory = memory or SessionMemory()

        self.graph = create_customer_service_graph(
            intent_agent=IntentAgent(),
            order_agent=OrderAgent(),
            refund_policy_agent=RefundPolicyAgent(),
            ticket_agent=TicketAgent(tickets_file=tickets_file) if tickets_file else TicketAgent(),
            compliance_agent=ComplianceAgent(),
            memory=self.memory,
            llm_client=llm_client or create_llm_client(),
        )

    def handle(self, request: ChatRequest) -> ChatResponse:
        result = self.graph.invoke(
            {
                "user_id": request.user_id,
                "session_id": request.session_id,
                "message": request.message,
                "intent": "",
                "slots": {},
                "raw_reply": "",
                "final_reply": "",
                "trace": ["ChatAPI", "Supervisor"],
            }
        )

        return ChatResponse(
            reply=result["final_reply"],
            intent=result["intent"],
            trace=result["trace"],
        )
