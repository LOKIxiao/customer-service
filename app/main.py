from fastapi import FastAPI

from app.api.chat import router as chat_router


app = FastAPI(
    title='Customer Service Agent',
    description='A multi-agent customer service system.',
    version='0.1.0',
)

app.include_router(chat_router)

@app.get('/health')
def health_check():
    return {'status': 'ok'}