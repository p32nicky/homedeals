"""
Scrape Amazon search results directly for home & kitchen deals sorted by discount.
"""
import logging
import re
import time
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
}

# Amazon browse nodes + search index for home categories sorted by discount
SEARCH_URLS = [
    "https://www.amazon.com/s?i=garden&rh=n%3A1055398&s=discount-rank&low-price=5",        # Home & Garden
    "https://www.amazon.com/s?i=kitchen&rh=n%3A284507&s=discount-rank&low-price=5",         # Kitchen & Dining
    "https://www.amazon.com/s?i=furniture&rh=n%3A1063306&s=discount-rank&low-price=5",      # Furniture
    "https://www.amazon.com/s?i=hi&rh=n%3A228013&s=discount-rank&low-price=5",              # Home Improvement
    "https://www.amazon.com/s?i=bed-bath&rh=n%3A1136223&s=discount-rank&low-price=5",      # Bed & Bath
    "https://www.amazon.com/s?i=lawngarden&rh=n%3A2972638011&s=discount-rank&low-price=5", # Lawn & Garden
    "https://www.amazon.com/s?i=tools&rh=n%3A468240&s=discount-rank&low-price=5",          # Tools & Home Improvement
]


def _parse_price(text: str):
    if not text:
        return None
    m = re.search(r'[\d,]+\.?\d{0,2}', text.replace(',', ''))
    try:
        return float(m.group()) if m else None
    except Exception:
        return None


def _scrape_page(url: str, associate_tag: str, seen_asins: set, now: str) -> list[dict]:
    results = []
    try:
        r = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        if r.status_code != 200:
            logger.warning(f"HTTP {r.status_code} for {url}")
            return results

        soup = BeautifulSoup(r.text, "html.parser")
        products = soup.select("[data-asin]")

        for el in products:
            asin = el.get("data-asin", "").strip()
            if not asin or len(asin) != 10 or asin in seen_asins:
                continue

            # Title
            title_el = el.select_one("h2 a span, h2 span")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            # Sale price
            price_el = el.select_one(".a-price[data-a-color='base'] .a-offscreen, .a-price .a-offscreen")
            price = _parse_price(price_el.get_text() if price_el else "")

            # Original price (struck through)
            orig_el = el.select_one(".a-price[data-a-color='secondary'] .a-offscreen, .a-text-strike")
            original_price = _parse_price(orig_el.get_text() if orig_el else "")

            if not price or not original_price or original_price <= price:
                continue

            savings = round(original_price - price, 2)
            savings_pct = round((savings / original_price) * 100, 1)
            if savings_pct < 10:
                continue

            # Image
            img_el = el.select_one("img.s-image, img[data-image-latency]")
            image_url = img_el.get("src", "") if img_el else f"https://m.media-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_.jpg"

            seen_asins.add(asin)
            results.append({
                "asin": asin,
                "title": title,
                "url": f"https://www.amazon.com/dp/{asin}/?tag={associate_tag}",
                "image_url": image_url,
                "price": price,
                "original_price": original_price,
                "savings": savings,
                "savings_percent": savings_pct,
                "category": "HomeAndKitchen",
                "description": title,
                "first_seen_at": now,
                "last_seen_at": now,
            })

    except Exception as e:
        logger.warning(f"Scrape failed {url}: {e}")

    return results


def scrape_deals(access_key: str, secret_key: str, associate_tag: str) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    results = []
    seen_asins: set = set()

    for url in SEARCH_URLS:
        items = _scrape_page(url, associate_tag, seen_asins, now)
        logger.info(f"{url.split('?')[0]}: {len(items)} deals")
        results.extend(items)
        time.sleep(2)  # be polite

    logger.info(f"Total: {len(results)} unique deals")
    return results
