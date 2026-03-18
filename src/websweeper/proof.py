"""MVP 0: Proof of Life — verify Playwright works in this environment."""

import asyncio
from pathlib import Path


async def proof_of_life():
    """Launch headless Chromium, load google.com, capture screenshot."""
    from playwright.async_api import async_playwright

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("https://www.google.com")
        title = await page.title()
        print(f"Page title: {title}")

        screenshot_path = output_dir / "proof.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"Screenshot saved: {screenshot_path}")

        await browser.close()

    return title


if __name__ == "__main__":
    asyncio.run(proof_of_life())
