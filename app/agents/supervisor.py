from pathlib import Path
from typing import Any

from app.agents.intent_agent import IntentAgent
from app.agents.long_term_memory_agent import LongTermMemoryAgent
from app.agents.memory_extraction_agent import MemoryExtractionAgent
from app.agents.order_agent import OrderAgent
from app.agents.ticket_agent import TicketAgent
from app.graphs.customer_service_graph import create_customer_service_graph
from app.llm.base import BaseLLMClient
from app.llm.factory import create_llm_client
from app.mcp.factory import create_mcp_client
from app.memory.session_memory import SessionMemory
from app.memory.session_factory import create_session_memory
from app.schemas.chat import ChatRequest, ChatResponse
from app.agents.hybrid_intent_agent import HybridIntentAgent
from app.agents.llm_intent_agent import LLMIntentAgent
from app.agents.rag_agent import RAGAgent

class Supervisor:
    def __init__(
        self,
        tickets_file: Path | None = None,
        memory: SessionMemory | None = None,
        llm_client: BaseLLMClient | None = None,
        mcp_client: Any | None = None,
    ) -> None:
        self.memory = memory or create_session_memory()
        llm = llm_client or create_llm_client()
        self.mcp_client = mcp_client or create_mcp_client(tickets_file=tickets_file)

        self.graph = create_customer_service_graph(
            intent_agent=HybridIntentAgent(
                llm_intent_agent=LLMIntentAgent(llm),
                rule_intent_agent=IntentAgent(),
            ),
            order_agent=OrderAgent(mcp_client=self.mcp_client),
            rag_agent=RAGAgent(mcp_client=self.mcp_client),
            ticket_agent=TicketAgent(mcp_client=self.mcp_client),
            long_term_memory_agent=LongTermMemoryAgent(mcp_client=self.mcp_client),
            memory_extraction_agent=MemoryExtractionAgent(llm_client=llm),
            mcp_client=self.mcp_client,
            memory=self.memory,
            llm_client=llm,
        )

    def close(self) -> None:
        self.mcp_client.close()
        self.memory.close()

    def handle(self, request: ChatRequest) -> ChatResponse:
        result = self.graph.invoke(
            {
                "user_id": request.user_id,
                "session_id": request.session_id,
                "message": request.message,
                "intent": "",
                "slots": {},
                "raw_reply": "",
                "long_term_context": "",
                "conversation_history": "",
                "final_reply": "",
                "trace": ["ChatAPI", "Supervisor"],
            }
        )

        return ChatResponse(
            reply=result["final_reply"],
            intent=result["intent"],
            trace=result["trace"],
        )
