import re

from app.schemas.intent import IntentResult


class IntentAgent:
    # 覆盖 data/knowledge_base 下全部 8 篇文档的关键词，而不是只有退款政策
    KNOWLEDGE_BASE_KEYWORDS = [
        "退款", "退货", "退换", "售后", "政策",  # refund_policy.md
        "包邮", "运费", "偏远地区",  # shipping_policy.md（订单状态相关的"物流/快递/发货/送达"仍归 order_query）
        "发票", "开票", "报销",  # invoice_policy.md
        "保修", "维修", "延保", "质保",  # warranty_policy.md
        "密码", "账号安全", "绑定", "隐私", "账号被盗", "找回密码",  # account_security.md
        "会员", "积分", "等级权益",  # membership_policy.md
        "优惠券", "满减", "折扣", "大促",  # promotion_policy.md
        "连不上", "没声音", "断连", "进水", "失灵", "没反应", "灯效",  # troubleshooting_faq.md
    ]

    def classify(self, message: str) -> IntentResult:
        normalized_message = message.strip().lower()
        order_id = self._extract_order_id(normalized_message)

        if self._contains_any(normalized_message, ["人工", "真人", "客服", "转人工"]):
            return IntentResult(intent="human_handoff", confidence=0.9)

        if self._contains_any(normalized_message, ["刚才", "之前", "上一句", "上次", "问了什么", "说了什么"]):
            return IntentResult(intent="memory_query", confidence=0.8)

        if self._contains_any(normalized_message, ["工单", "投诉", "反馈", "报修"]):
            if self._contains_any(normalized_message, ["进度", "状态", "查询", "处理到哪"]):
                return IntentResult(intent="ticket_query", confidence=0.86)
            return IntentResult(intent="ticket_create", confidence=0.82)

        if self._contains_any(normalized_message, self.KNOWLEDGE_BASE_KEYWORDS):
            return IntentResult(intent="knowledge_base_query", confidence=0.84)

        if self._contains_any(normalized_message, ["订单", "物流", "快递", "发货", "到哪", "什么时候到", "送达"]):
            slots = {"order_id": order_id} if order_id else {}
            return IntentResult(intent="order_query", confidence=0.88, slots=slots)
        return IntentResult(intent="unknown", confidence=0.35, need_clarification=True)



    def _extract_order_id(self, message: str) -> str | None:
        match = re.search(r"\b[a-z]\d{4,}\b", message, re.IGNORECASE)
        return match.group(0).upper() if match else None
    
    
    def _contains_any(self, message: str, keywords: list[str]) -> bool:
        return any(keyword in message for keyword in keywords)