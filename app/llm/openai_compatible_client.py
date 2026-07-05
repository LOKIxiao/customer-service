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
    
    def generate_customer_reply(self, user_message: str, intent: str, raw_reply: str) -> str:
        prompt = f"""
你是一个专业、简洁、友好的智能客服助手。

请基于【业务系统返回结果】回答用户问题。
要求：
1. 不要编造业务系统没有提供的信息。
2. 不要改变订单号、工单号、日期、状态等事实。
3. 不要承诺额外赔偿、退款或人工处理结果。
4. 回复要自然、简洁，适合直接发给用户。

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

