import asyncio
from playwright.async_api import async_playwright

async def get_url():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://apply.workable.com/cloudfactory/')
        await page.wait_for_load_state('networkidle')
        print(await page.content())
        await browser.close()

asyncio.run(get_url())
