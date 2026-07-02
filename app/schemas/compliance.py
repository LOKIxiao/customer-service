from pydantic import BaseModel, Field


class ComplianceResult(BaseModel):
    passed: bool
    risk_level: str = Field(..., examples=['Low'])
    response: str
    need_human: bool = False