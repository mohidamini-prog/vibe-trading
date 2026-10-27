"""Echter Playwright-Screenshot des Orchestra Trading Desk."""
import asyncio
from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8643/"
OUT = "/root/forschung/orchestra/visualizer/trading_desk.png"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        await page.goto(URL, wait_until="domcontentloaded")
        # Polling abwarten (3s-Intervall) — domcontentloaded statt networkidle,
        # weil das 3s-Polling die Seite nie "idle" werden lässt
        await page.wait_for_timeout(4000)
        # Zustand prüfen (echte Daten aus State-DB)
        decision = await page.text_content("#decision")
        symbol = await page.text_content("#symbol")
        n_robots = await page.locator(".robot-card").count()
        conn = await page.text_content("#connText")
        print(f"decision={decision} symbol={symbol} robots={n_robots} conn={conn}")
        await page.screenshot(path=OUT, full_page=True)
        print(f"SCREENSHOT: {OUT}")
        await browser.close()


asyncio.run(main())
