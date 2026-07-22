from pydantic import BaseModel, Field

ALLOWED_MEMORY_CATEGORIES = {
    "preference",           # 商品偏好，比如更看重续航还是外观
    "contact",              # 收货地址、联系方式偏好
    "complaint_history",    # 历史工单/投诉摘要
    "communication_style",  # 沟通风格偏好，比如喜欢简短直接的回复
}


class UserMemoryRecord(BaseModel):
    memory_id: str
    user_id: str
    category: str
    content: str
    metadata: dict = Field(default_factory=dict)


class RetrievedMemory(UserMemoryRecord):
    score: float


class ExtractedFact(BaseModel):
    category: str
    content: str
