from app.rag.answer_evaluation import score_answer


def _case(answerable: bool = True):
    return {
        "answerable": answerable,
        "required_facts": [["1-3个工作日", "一到三个工作日"], ["原路退回"]],
        "forbidden_facts": ["立即到账"],
    }


def test_score_answer_passes_when_all_required_facts_are_present():
    result = score_answer(_case(), "退款将在1-3个工作日内原路退回。")

    assert result["completeness"] == 1.0
    assert result["rule_passed"] is True


def test_score_answer_reports_missing_required_fact():
    result = score_answer(_case(), "退款将在1-3个工作日内到账。")

    assert result["completeness"] == 0.5
    assert result["rule_passed"] is False


def test_score_answer_rejects_forbidden_fact():
    result = score_answer(_case(), "退款会立即到账，之后原路退回，通常需要1-3个工作日。")

    assert result["forbidden_hits"] == ["立即到账"]
    assert result["rule_passed"] is False


def test_score_answer_accepts_correct_refusal_for_unanswerable_question():
    result = score_answer(_case(answerable=False), "知识库没有相关信息，建议联系人工客服。")

    assert result["refused"] is True
    assert result["rule_passed"] is True


def test_score_answer_rejects_hallucination_for_unanswerable_question():
    result = score_answer(_case(answerable=False), "悉尼门店每天晚上九点关门。")

    assert result["refused"] is False
    assert result["rule_passed"] is False
