import asyncio
from pydantic import BaseModel
from app.core.llm.client import LLMClient
from app.config.settings import get_settings

class Dummy(BaseModel):
    name: str

async def test():
    llm = LLMClient()
    try:
        res = await llm.complete_with_structured_output('My name is Saed', Dummy, model='openrouter/google/gemini-2.0-pro-exp-02-05:free')
        print(res)
        return
    except Exception as e:
        print('Error:', type(e), e)

asyncio.run(test())
