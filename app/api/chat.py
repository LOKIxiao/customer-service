from fastapi import APIRouter

from app.agents.intent_agent import IntentAgent
from app.schemas.chat import ChatRequest, ChatResponse



router = APIRouter(prefix='/chat', tags=['chat'])
intent_agent = IntentAgent()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    intent_result = intent_agent.classify(request.message)

    return ChatResponse(
        reply=f"我识别到你的意图是{intent_result.intent},下一步会把它交给对应的业务Agent处理",
        intent=intent_result.intent,
        trace=["ChatAPI", 'IntentAgent'],
    )
