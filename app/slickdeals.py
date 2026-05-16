"""
Post products to Slickdeals using a persistent browser session.
Run `python -m app.slickdeals --setup` once to log in manually.
Subsequent runs reuse saved cookies automatically.
"""
import asyncio
import logging
import os
import time

logger = logging.getLogger(__name__)

CDP_URL = "http://127.0.0.1:9222"
SUBMIT_URL = "https://slickdeals.net/forums/newthread.php?do=newthread&f=9"
USER = "NickD4446"


async def _post_one(page, p: dict) -> bool:
    asin = p.get("asin", "")
    amazon_url = p.get("url") or f"https://www.amazon.com/dp/{asin}/?tag=nicdav09-20"
    title = p.get("title", "")[:200]
    price = p.get("price")
    original_price = p.get("original_price")
    savings_pct = p.get("savings_percent")
    desc = (p.get("description") or title)[:1000]

    # Build title string
    deal_title = title
    if price:
        deal_title = f"{title} - ${price:.2f}"
        if savings_pct:
            deal_title = f"{title} - ${price:.2f} ({int(savings_pct)}% off)"

    await page.goto(SUBMIT_URL, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)

    # Check still logged in
    if "login" in page.url.lower() or await page.query_selector("input[name='loginname']"):
        logger.error("Not logged in to Slickdeals — log in manually in Chrome first")
        return False

    if "ERR_" in await page.title():
        logger.error(f"Page error: {await page.title()}")
        return False

    # Fill Deal URL field (triggers autofill)
    url_input = await page.query_selector("input[name='dealUrl'], input[placeholder*='URL'], input[id*='dealUrl']")
    if url_input:
        await url_input.fill(amazon_url)
        await page.wait_for_timeout(2000)

    # Fill title
    title_input = await page.query_selector("input[name='subject'], input[name='title'], input[id*='title']")
    if title_input:
        await title_input.fill(deal_title)

    # Fill sale price
    if price:
        price_input = await page.query_selector("input[name='salePrice'], input[id*='salePrice'], input[placeholder*='Sale']")
        if price_input:
            await price_input.fill(str(round(price, 2)))

    # Fill list/original price
    if original_price:
        list_input = await page.query_selector("input[name='listPrice'], input[id*='listPrice'], input[placeholder*='List']")
        if list_input:
            await list_input.fill(str(round(original_price, 2)))

    # Fill description
    desc_area = await page.query_selector("textarea[name='message'], textarea[id*='description'], textarea[id*='message']")
    if desc_area:
        full_desc = f"{desc}\n\nAffiliate link: {amazon_url}"
        await desc_area.fill(full_desc)

    # Submit
    submit_btn = await page.query_selector("input[value*='Submit'], button[type='submit']")
    if submit_btn:
        await submit_btn.click()
        await page.wait_for_timeout(3000)
        # Check for success (URL changes away from newthread)
        if "newthread" not in page.url:
            logger.info(f"Posted: {title[:60]}")
            return True
        else:
            logger.warning(f"May have failed for {asin} — check manually")
            return False

    logger.warning("No submit button found")
    return False


async def _run(products: list[dict], setup: bool = False):
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"Cannot connect to Chrome on port 9222: {e}")
            print("Run this first, then try again:")
            print(r'  & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222')
            return 0

        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        if setup:
            print("Connected to Chrome OK! You're ready to post.")
            print("Run: python sync.py with POST_SLICKDEALS=1")
            return 0

        posted = 0
        for i, p in enumerate(products):
            title = p.get('title', '')[:80]
            price = p.get('price')
            pct = p.get('savings_percent')
            print(f"\n[{i+1}/{len(products)}] {title}")
            if price:
                print(f"    ${price:.2f}" + (f" ({int(pct)}% off)" if pct else ""))
            print(f"    ASIN: {p.get('asin')}")
            choice = input("  Post? [Enter=yes / s=skip / q=quit] > ").strip().lower()
            if choice == 'q':
                print("Stopped.")
                break
            if choice == 's':
                print("Skipped.")
                continue
            try:
                ok = await _post_one(page, p)
                if ok:
                    posted += 1
                time.sleep(10)  # be polite
            except Exception as e:
                logger.error(f"Error on {p.get('asin')}: {e}")

        return posted


def post_products(products: list[dict]) -> int:
    if not products:
        return 0
    return asyncio.run(_run(products))


def setup_session():
    asyncio.run(_run([], setup=True))


if __name__ == "__main__":
    import sys
    if "--setup" in sys.argv:
        setup_session()
    else:
        print("Use: python -m app.slickdeals --setup")
