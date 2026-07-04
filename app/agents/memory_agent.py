from app.memory.session_memory import SessionMemory



class MemoryAgent:
    def __init__(self, memory: SessionMemory) -> None:
        self.memory = memory
    
    def handle(self, session_id: str) -> str:
        messages = self.memory.get_messages(session_id)

        user_messages = [
            message.content
            for message in messages
            if message.role == 'user'
        ]

        if len(user_messages) <= 1:
            return '我暂时还没有足够的历史对话记录。'
        
        previous_user_message = user_messages[-2]
        return f"你刚才问的是：{previous_user_message}"
