from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.chat import supervisor


app = FastAPI(
    title='Customer Service Agent',
    description='A multi-agent customer service system.',
    version='0.1.0',
)

app.include_router(chat_router)

@app.get('/health')
def health_check():
    return {'status': 'ok'}


@app.on_event('shutdown')
def shutdown_event():
    # 关闭 Supervisor 持有的 MCP client，避免 stdio 子进程常驻
    supervisor.close()