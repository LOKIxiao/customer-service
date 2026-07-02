from fastapi import APIRouter


from app.agents.compliance_agent import ComplianceAgent
from app.agents.intent_agent import IntentAgent
from app.agents.order_agent import OrderAgent
from app.schemas.chat import ChatRequest, ChatResponse




router = APIRouter(prefix='/chat', tags=['chat'])


intent_agent = IntentAgent()
order_agent = OrderAgent()
compliance_agent = ComplianceAgent()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    intent_result = intent_agent.classify(request.message)

    if intent_result.intent == 'order_query':
        raw_reply = order_agent.handle(
            user_id=request.user_id,
            slots=intent_result.slots,
        )

        compliance_result = compliance_agent.review(raw_reply)

        return ChatResponse(
            reply=compliance_result.response,
            intent=intent_result.intent,
            trace=[
                "ChatAPI",
                "IntentAgent",
                "OrderAgent",
                "OrderTools",
                "ComplianceAgent",
            ],
        )

    raw_reply = f"我识别到你的意图是 {intent_result.intent}，但这个业务 Agent 还没有接入。"
    compliance_result = compliance_agent.review(raw_reply)

    return ChatResponse(
        reply=compliance_result.response,
        intent=intent_result.intent,
        trace=["ChatAPI", "IntentAgent", "ComplianceAgent"],
    )