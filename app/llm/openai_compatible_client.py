import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.llm.base import BaseLLMClient




class OpenAICompatibleClient(BaseLLMClient):
    def __init__(self) -> None:
        load_dotenv()

        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")

        if not api_key:
            raise ValueError("LLM_API_KEY is required when using OpenAICompatibleClient")

        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=0.2,
        )
    
    def generate_customer_reply(
        self,
        user_message: str,
        intent: str,
        raw_reply: str,
        long_term_context: str = "",
    ) -> str:
        known_user_info_section = (
            f"\n【已知用户信息】\n{long_term_context}\n" if long_term_context else ""
        )

        prompt = f"""
你是一个专业、简洁、友好的智能客服助手。

请基于【业务系统返回结果】回答用户问题。
要求：
1. 不要编造业务系统没有提供的信息。
2. 不要改变订单号、工单号、日期、状态等事实。
3. 不要承诺额外赔偿、退款或人工处理结果。
4. 回复要自然、简洁，适合直接发给用户。
5. 如果提供了【已知用户信息】，在合适的地方自然地体现出来，但不要生硬地复述。
{known_user_info_section}
【用户问题】
{user_message}

【识别意图】
{intent}

【业务系统返回结果】
{raw_reply}

请输出最终客服回复：
""".strip()

        response = self.llm.invoke(prompt)
        return response.content.strip()

    def classify_intent(self, message: str) -> str:
        prompt = f"""
你是一个智能客服意图识别助手 Agent，

请根据用户消息识别意图，并且只返回 JSON，不要输出任何解释。

允许的 intent 只有：
- order_query：查询某个具体订单的状态、物流进度、预计送达时间
- knowledge_base_query：知识库类问题，包括退款退货、物流配送政策（不是具体某个订单的状态）、发票开具、售后保修、账号安全、会员积分、优惠券满减、故障排查（耳机/键盘等产品的使用问题）等
- ticket_create：创建投诉/工单
- ticket_query：查询已有工单的处理状态
- memory_query：询问自己刚才/之前说过什么
- human_handoff：明确要求转人工客服
- unknown：无法判断


判断 order_query 还是 knowledge_base_query 的关键：问的是"我这个订单/包裹怎么样了"就是 order_query；问的是"贵公司的政策/规则是什么、遇到某类问题该怎么办"就是 knowledge_base_query，即使两者都提到了物流、订单等词。

字段要求：
— intent: 字符串
- confidence: 0 到 1 之间的小数
- slots: 对象，提取订单号等关键信息，没有则为空对象
- need_clarification: 布尔值

示例：
{{
  "intent": "order_query",
  "confidence": 0.92,
  "slots": {{
    "order_id": "A10001"
  }},
  "need_clarification": false
}}

用户消息：
{message}
""".strip()

        response = self.llm.invoke(prompt)
        return response.content.strip()

    def extract_user_facts(self, user_message: str, assistant_reply: str) -> str:
        prompt = f"""
你是一个客服对话的信息抽取助手，负责判断这一轮对话里有没有值得长期记住的、关于这个用户的稳定信息。

只在真正有稳定信息时才抽取，允许的 category 只有：
- preference：商品偏好（比如更看重续航还是外观、喜欢无线还是有线）
- contact：收货地址、联系方式偏好
- complaint_history：投诉/工单相关的背景信息摘要
- communication_style：沟通风格偏好（比如喜欢简短直接的回复）

不要抽取一次性的、和具体这笔订单绑定的信息（比如某个订单号、某次的物流状态），只抽取以后还有参考价值的稳定信息。
大多数轮次（比如查物流、查工单状态）应该没有可抽取的信息，直接返回空列表，不要为了有输出而编造。

只返回 JSON，不要输出任何解释，格式如下：
{{
  "facts": [
    {{"category": "preference", "content": "用户偏好无线降噪耳机，更看重续航"}}
  ]
}}

没有可抽取信息时返回：
{{"facts": []}}

【用户消息】
{user_message}

【客服回复】
{assistant_reply}
""".strip()

        response = self.llm.invoke(prompt)
        return response.content.strip()
