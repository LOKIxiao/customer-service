from app.compliance.pii import mask_pii
from app.schemas.compliance import ComplianceResult


class ComplianceAgent:
    def review(self, response: str) -> ComplianceResult:
        redacted_response = mask_pii(response)
        need_human = self._need_human_handoff(redacted_response)

        return ComplianceResult(
            passed=True,
            risk_level="medium" if need_human else "low",
            response=redacted_response,
            need_human=need_human,
        )

    def _need_human_handoff(self, text: str) -> bool:
        risk_keywords = ["投诉", "赔偿", "威胁", "报警", "律师", "起诉"]
        return any(keyword in text for keyword in risk_keywords)