import asyncio
from app.providers.gemini import GeminiProvider

async def test():
    gp = GeminiProvider()
    print("Testing Gemini model:", gp.model)
    res = await gp.chat([{"role": "user", "content": "请回复'Gemini 3.7 Flash 测试成功'" if True else ""}])
    print("Result from Gemini 3.7 Flash:\n", res)

asyncio.run(test())
