"""MVP 1: Step Execution — search google.com using the executor."""

import asyncio
import logging

from playwright.async_api import async_playwright

from websweeper.executor import execute_step

logging.basicConfig(level=logging.DEBUG)


async def proof_search():
    """Use the executor to perform a Google search and read results."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("https://www.google.com")
        print(f"Loaded: {await page.title()}")

        # Fill the search box
        await execute_step(page, {
            "action": "fill",
            "target": {"type": "role", "value": "Search", "role": "combobox", "name": "Search"},
            "input": "websweeper playwright automation",
            "description": "Fill search box",
        })

        # Press Enter to search (simpler than finding the right button)
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("domcontentloaded")

        # Wait for results
        await execute_step(page, {
            "action": "wait_for_selector",
            "target": {"type": "css", "value": "#search"},
            "timeout_seconds": 10,
            "description": "Wait for search results",
        })

        # Extract first 5 result titles
        results = page.locator("#search h3")
        count = min(await results.count(), 5)
        print(f"\nTop {count} results:")
        for i in range(count):
            title = await results.nth(i).text_content()
            print(f"  {i + 1}. {title}")

        # Screenshot the results
        await page.screenshot(path="output/search_results.png", full_page=False)
        print("\nScreenshot saved: output/search_results.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(proof_search())
