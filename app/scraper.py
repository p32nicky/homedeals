"""
Scrape Amazon search results directly for home & kitchen deals sorted by discount.
"""
import logging
import random
import re
import time
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

def _headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
    }

# Amazon browse nodes + search index for home categories sorted by discount
SEARCH_URLS = [
    "https://www.amazon.com/s?k=home+organization&i=garden&s=discount-rank",
    "https://www.amazon.com/s?k=kitchen+storage&i=kitchen&s=discount-rank",
    "https://www.amazon.com/s?k=home+decor&i=garden&s=discount-rank",
    "https://www.amazon.com/s?k=closet+organizer&i=garden&s=discount-rank",
    "https://www.amazon.com/s?k=bathroom+accessories&i=garden&s=discount-rank",
    "https://www.amazon.com/s?k=bedding+sheets&i=bed-bath&s=discount-rank",
    "https://www.amazon.com/s?k=wall+art+decor&i=garden&s=discount-rank",
    "https://www.amazon.com/s?k=garden+tools&i=lawngarden&s=discount-rank",
    "https://www.amazon.com/s?k=smart+home+devices&i=hi&s=discount-rank",
    "https://www.amazon.com/s?k=furniture+home&i=furniture&s=discount-rank",
    "https://www.amazon.com/s?k=kitchen+gadgets&i=kitchen&s=discount-rank",
    "https://www.amazon.com/s?k=rugs+home&i=garden&s=discount-rank",
    "https://www.amazon.com/s?k=lighting+home&i=hi&s=discount-rank",
    "https://www.amazon.com/s?k=outdoor+furniture&i=lawngarden&s=discount-rank",
    "https://www.amazon.com/s?k=vacuum+cleaner&i=garden&s=discount-rank",
    "https://www.amazon.com/s?k=curtains+blinds&i=garden&s=discount-rank",
    "https://www.amazon.com/s?k=storage+containers&i=kitchen&s=discount-rank",
    "https://www.amazon.com/s?k=throw+pillows+blankets&i=bed-bath&s=discount-rank",
    "https://www.amazon.com/s?k=air+purifier&i=garden&s=discount-rank",
    "https://www.amazon.com/s?k=kitchen+appliances&i=kitchen&s=discount-rank",
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
        r = httpx.get(url, headers=_headers(), timeout=15, follow_redirects=True)
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
            # Use large image — replace small thumbnail size with SL1500
            raw_img = img_el.get("src", "") if img_el else ""
            if raw_img:
                image_url = re.sub(r'\._[A-Z0-9_,]+_\.', "._SL1500_.", raw_img)
            else:
                image_url = f"https://m.media-amazon.com/images/P/{asin}.01._SL1500_.jpg"

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
        time.sleep(random.uniform(4, 9))  # random delay to avoid bot detection

    logger.info(f"Total: {len(results)} unique deals")
    return results
