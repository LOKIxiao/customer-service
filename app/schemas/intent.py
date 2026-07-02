from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    intent: str = Field(..., examples=["order_query"])
    confidence: float = Field(..., ge=0, le=1, examples=[0.9])
    slots: dict[str, str] = Field(default_factory=dict)
    need_clarification: bool = False