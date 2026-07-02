from pydantic import BaseModel, Field



class ChatRequest(BaseModel):
    user_id: str = Field(..., examples=['u_001'])
    session_id: str = Field(..., examples=['s_001'])
    message: str = Field(...,  examples=['我的订单什么时候到？'])


class ChatResponse(BaseModel):
    reply: str
    intent: str
    trace: list[str]