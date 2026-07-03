from app.agents.compliance_agent import ComplianceAgent


def test_redacts_phone_number():
    agent = ComplianceAgent()

    result = agent.review("收件手机号是 13812345678。")

    assert result.response == "收件手机号是 138****5678。"


def test_detects_human_handoff_keywords():
    agent = ComplianceAgent()

    result = agent.review("用户要求赔偿并表示要起诉。")

    assert result.need_human is True
    assert result.risk_level == "medium"