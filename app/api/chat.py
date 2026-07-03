from fastapi import APIRouter

from app.agents.supervisor import Supervisor
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])

supervisor = Supervisor()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return supervisor.handle(request)