"""
Scrape Amazon search results for home decor / DIY / organization deals.
Uses curl_cffi to bypass bot detection. No API key required.
"""
import logging
import re
from datetime import datetime, timezone

from curl_cffi.requests import Session

logger = logging.getLogger(__name__)

SEARCH_TERMS = [
    "home organization storage deals",
    "wall art decor sale",
    "kitchen organizer deals",
    "bathroom accessories storage",
    "closet organizer sale",
    "decorative baskets storage",
    "picture frames wall decor",
    "candles home decor sale",
    "throw pillows cushions deals",
    "shelf organizer home sale",
    "laundry storage organization",
    "DIY home improvement tools",
]

HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

ASIN_RE = re.compile(r'data-asin="([A-Z0-9]{10})"')
TITLE_RE = re.compile(r'<span class="a-text-normal"[^>]*>([^<]{10,200})</span>')
IMG_RE   = re.compile(r'<img[^>]+class="[^"]*s-image[^"]*"[^>]+src="([^"]+)"')
PRICE_RE = re.compile(r'<span class="a-price-whole">(\d+)</span><span class="a-price-decimal">\.</span><span class="a-price-fraction">(\d+)</span>')
ORIG_RE  = re.compile(r'<span class="a-price a-text-price"[^>]*>.*?<span[^>]*>\$?([\d,]+\.?\d*)</span>', re.DOTALL)
SAVE_RE  = re.compile(r'\((\d+)%\)')


def _search_url(keywords: str, page: int = 1) -> str:
    q = keywords.replace(" ", "+")
    return (
        f"https://www.amazon.com/s?k={q}"
        f"&s=discount-rate-high-to-low"
        f"&page={page}"
        f"&rh=n%3A1055398"  # Home & Kitchen browse node
    )


def _parse_page(html: str, associate_tag: str, now: str) -> list[dict]:
    items = []
    asins = ASIN_RE.findall(html)
    titles = TITLE_RE.findall(html)
    imgs = IMG_RE.findall(html)
    prices_raw = PRICE_RE.findall(html)
    origs_raw = ORIG_RE.findall(html)
    saves_raw = SAVE_RE.findall(html)

    seen = set()
    for i, asin in enumerate(asins):
        if not asin or asin in seen:
            continue
        seen.add(asin)

        title = titles[i] if i < len(titles) else None
        if not title:
            continue
        title = title.strip()

        image_url = imgs[i] if i < len(imgs) else ""
        # Use higher res image
        image_url = re.sub(r'\._[^.]+_\.', '._AC_SL500_.', image_url)

        price = None
        if i < len(prices_raw):
            try:
                price = float(f"{prices_raw[i][0]}.{prices_raw[i][1]}")
            except Exception:
                pass

        original_price = None
        if i < len(origs_raw):
            try:
                original_price = float(origs_raw[i].replace(",", ""))
            except Exception:
                pass

        savings = None
        savings_pct = None
        if i < len(saves_raw):
            try:
                savings_pct = float(saves_raw[i])
            except Exception:
                pass
        if price and original_price and original_price > price:
            savings = round(original_price - price, 2)

        url = f"https://www.amazon.com/dp/{asin}/?tag={associate_tag}"

        items.append({
            "asin": asin,
            "title": title,
            "url": url,
            "image_url": image_url,
            "price": price,
            "original_price": original_price,
            "savings": savings,
            "savings_percent": savings_pct,
            "category": "HomeGarden",
            "description": title,
            "first_seen_at": now,
            "last_seen_at": now,
        })
    return items


def scrape_deals(access_key: str, secret_key: str, associate_tag: str) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    results = []
    seen_asins: set = set()

    with Session(impersonate="chrome124") as s:
        for keywords in SEARCH_TERMS:
            try:
                url = _search_url(keywords)
                resp = s.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"'{keywords}': HTTP {resp.status_code}")
                    continue
                items = _parse_page(resp.text, associate_tag, now)
                new = [it for it in items if it["asin"] not in seen_asins]
                for it in new:
                    seen_asins.add(it["asin"])
                results.extend(new)
                logger.info(f"'{keywords}': {len(new)} products")
            except Exception as e:
                logger.warning(f"'{keywords}' failed: {e}")

    logger.info(f"Total scraped: {len(results)} unique products")
    return results
