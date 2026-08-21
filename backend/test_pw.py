import asyncio
from playwright.async_api import async_playwright

async def main():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
            print("Playwright launched successfully")
    except Exception as e:
        print(f"Playwright error: {e}")

asyncio.run(main())
