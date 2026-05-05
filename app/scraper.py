"""
Scrape home deals from Slickdeals & DealNews RSS feeds.
Extracts Amazon ASINs and rewrites with affiliate tag.
No API key required. Works from any IP.
"""
import logging
import re
from datetime import datetime, timezone

import feedparser
import httpx

logger = logging.getLogger(__name__)

ASIN_RE = re.compile(r'/dp/([A-Z0-9]{10})')
PRICE_RE = re.compile(r'\$\s*([\d,]+\.?\d{0,2})')
SAVE_RE  = re.compile(r'(\d+)%\s*off', re.IGNORECASE)

FEEDS = [
    # Slickdeals - home & kitchen searches
    "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&forumid[]=9&q=home+organization&rss=1",
    "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&forumid[]=9&q=home+decor&rss=1",
    "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&forumid[]=9&q=kitchen+storage&rss=1",
    "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&forumid[]=9&q=wall+decor&rss=1",
    "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&forumid[]=9&q=closet+organizer&rss=1",
    "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&forumid[]=9&q=bathroom+accessories&rss=1",
    # DealNews home & garden
    "https://www.dealnews.com/l-Home-Garden.html?rss=1",
    # Reddit deals
    "https://www.reddit.com/r/deals/.rss?limit=50",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; homedeals/1.0; +https://homedeals-beta.vercel.app)",
}


def _extract_asin(url: str):
    m = ASIN_RE.search(url or "")
    return m.group(1) if m else None


def _extract_image(entry) -> str:
    # Try media_thumbnail
    for t in getattr(entry, "media_thumbnail", []):
        if t.get("url"):
            return t["url"]
    # Try enclosures
    for enc in getattr(entry, "enclosures", []):
        if "image" in enc.get("type", ""):
            return enc.get("href", "")
    # Try media_content
    for mc in getattr(entry, "media_content", []):
        if mc.get("url"):
            return mc["url"]
    # Try summary img tag
    summary = getattr(entry, "summary", "") or ""
    m = re.search(r'<img[^>]+src="([^"]+)"', summary)
    if m:
        return m.group(1)
    return ""


def _extract_price(text: str):
    prices = PRICE_RE.findall(text)
    if len(prices) >= 1:
        try:
            return float(prices[0].replace(",", ""))
        except Exception:
            pass
    return None


def _extract_savings_pct(text: str):
    m = SAVE_RE.search(text)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    return None


def _follow_redirect(url: str) -> str:
    """Follow redirect to get final Amazon URL."""
    try:
        r = httpx.get(url, follow_redirects=True, timeout=8, headers=HEADERS)
        return str(r.url)
    except Exception:
        return url


def scrape_deals(access_key: str, secret_key: str, associate_tag: str) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    results = []
    seen_asins: set = set()

    for feed_url in FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            count = 0
            for entry in feed.entries:
                title = (getattr(entry, "title", "") or "").strip()
                if not title:
                    continue

                # Get link - may need to follow redirect
                link = getattr(entry, "link", "") or ""

                # Try to find ASIN in link or summary
                summary = getattr(entry, "summary", "") or ""
                full_text = link + " " + summary

                asin = _extract_asin(full_text)
                if not asin:
                    # Follow redirect to see if it resolves to Amazon
                    final = _follow_redirect(link)
                    asin = _extract_asin(final)

                if not asin or asin in seen_asins:
                    continue
                seen_asins.add(asin)

                image_url = _extract_image(entry)
                full_text_for_price = title + " " + summary
                price = _extract_price(full_text_for_price)
                savings_pct = _extract_savings_pct(full_text_for_price)

                original_price = None
                if price and savings_pct:
                    original_price = round(price / (1 - savings_pct / 100), 2)

                affiliate_url = f"https://www.amazon.com/dp/{asin}/?tag={associate_tag}"

                results.append({
                    "asin": asin,
                    "title": title,
                    "url": affiliate_url,
                    "image_url": image_url,
                    "price": price,
                    "original_price": original_price,
                    "savings": round(original_price - price, 2) if price and original_price else None,
                    "savings_percent": savings_pct,
                    "category": "HomeGarden",
                    "description": re.sub(r'<[^>]+>', '', summary)[:300].strip() or title,
                    "first_seen_at": now,
                    "last_seen_at": now,
                })
                count += 1

            logger.info(f"{feed_url.split('?')[0]}: {count} Amazon products found")
        except Exception as e:
            logger.warning(f"Feed failed {feed_url}: {e}")

    logger.info(f"Total: {len(results)} unique products")
    return results
