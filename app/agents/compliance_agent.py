import re

from app.schemas.compliance import ComplianceResult


class ComplianceAgent:
    def review(self, response: str) -> ComplianceResult:
        redacted_response = self._redact_sensitive_info(response)
        need_human = self._need_human_handoff(redacted_response)

        return ComplianceResult(
            passed=True,
            risk_level="medium" if need_human else "low",
            response=redacted_response,
            need_human=need_human,
        )

    def _redact_sensitive_info(self, text: str) -> str:
        text = self._redact_phone(text)
        return text

    def _redact_phone(self, text: str) -> str:
        return re.sub(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)", r"\1****\2", text)

    def _need_human_handoff(self, text: str) -> bool:
        risk_keywords = ["投诉", "赔偿", "威胁", "报警", "律师", "起诉"]
        return any(keyword in text for keyword in risk_keywords)