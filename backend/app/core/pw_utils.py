import sys
import asyncio
import anyio

def _sync_run_playwright(coro_fn, *args):
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_fn(*args))
    finally:
        loop.close()

async def run_playwright_in_thread(coro_fn, *args):
    return await anyio.to_thread.run_sync(_sync_run_playwright, coro_fn, *args)
