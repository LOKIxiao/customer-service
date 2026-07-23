from app.agents.intent_agent import IntentAgent


def test_classifies_order_query():
    agent = IntentAgent()

    result = agent.classify("我的订单什么时候到？")

    assert result.intent == "order_query"


def test_classifies_knowledge_base_query():
    agent = IntentAgent()

    result = agent.classify("怎么退款？")

    assert result.intent == "knowledge_base_query"


def test_classifies_human_handoff():
    agent = IntentAgent()

    result = agent.classify("我要找人工客服")

    assert result.intent == "human_handoff"


def test_extracts_order_id():
    agent = IntentAgent()

    result = agent.classify("帮我查一下订单 A10001")

    assert result.intent == "order_query"
    assert result.slots["order_id"] == "A10001"


def test_classifies_memory_query():
    agent = IntentAgent()

    result = agent.classify("刚才我问了什么？")

    assert result.intent == "memory_query"


def test_classifies_membership_question_as_knowledge_base_query():
    agent = IntentAgent()

    result = agent.classify("会员等级怎么算，积分能抵多少钱？")

    assert result.intent == "knowledge_base_query"


def test_classifies_promotion_question_as_knowledge_base_query():
    agent = IntentAgent()

    result = agent.classify("优惠券能叠加用吗？")

    assert result.intent == "knowledge_base_query"


def test_classifies_warranty_question_as_knowledge_base_query():
    agent = IntentAgent()

    result = agent.classify("耳机保修多久，可以买延保吗？")

    assert result.intent == "knowledge_base_query"


def test_classifies_account_security_question_as_knowledge_base_query():
    agent = IntentAgent()

    result = agent.classify("忘记密码了怎么找回？")

    assert result.intent == "knowledge_base_query"


def test_classifies_invoice_question_as_knowledge_base_query():
    agent = IntentAgent()

    result = agent.classify("怎么开发票？")

    assert result.intent == "knowledge_base_query"


def test_classifies_troubleshooting_question_as_knowledge_base_query():
    agent = IntentAgent()

    result = agent.classify("耳机连不上手机怎么办？")

    assert result.intent == "knowledge_base_query"


def test_order_query_keywords_still_win_over_knowledge_base_keywords():
    # "物流"/"快递"/"发货"/"送达" 这类具体订单状态词仍然归 order_query，
    # 不会被新扩的知识库关键词抢走。
    agent = IntentAgent()

    result = agent.classify("我的快递到哪了？")

    assert result.intent == "order_query"
