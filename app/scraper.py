"""
Amazon PA-API 5.0 scraper for home decor / DIY / organization deals.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

SEARCH_TERMS = [
    ("home organization storage", "HomeGarden"),
    ("wall art decor", "HomeGarden"),
    ("kitchen organization deals", "Kitchen"),
    ("bathroom accessories decor", "HomeGarden"),
    ("closet organizer storage", "HomeGarden"),
    ("DIY home tools", "Tools"),
    ("decorative storage baskets", "HomeGarden"),
    ("picture frames wall decor", "HomeGarden"),
    ("candles home fragrance", "HomeGarden"),
    ("throw pillows cushions", "HomeGarden"),
    ("shelf organizer home", "HomeGarden"),
    ("laundry storage organization", "HomeGarden"),
]

RESOURCES = [
    "Images.Primary.Large",
    "ItemInfo.Title",
    "ItemInfo.Features",
    "Offers.Listings.Price",
    "Offers.Listings.SavingBasis",
    "Offers.Summaries.LowestPrice",
]


def _safe(obj, *attrs, default=None):
    for attr in attrs:
        if obj is None:
            return default
        obj = getattr(obj, attr, None)
    return obj if obj is not None else default


def scrape_deals(access_key: str, secret_key: str, associate_tag: str) -> list[dict]:
    try:
        from amazon_paapi import AmazonApi
    except ImportError:
        logger.error("python-amazon-paapi not installed. Run: pip install python-amazon-paapi")
        return []

    api = AmazonApi(access_key, secret_key, associate_tag, "US")
    now = datetime.now(timezone.utc).isoformat()
    results = []
    seen_asins = set()

    for keywords, search_index in SEARCH_TERMS:
        try:
            response = api.search_items(
                keywords=keywords,
                search_index=search_index,
                item_count=10,
            )
            items = _safe(response, "search_result", "items") or []
            for item in items:
                asin = _safe(item, "asin")
                if not asin or asin in seen_asins:
                    continue
                seen_asins.add(asin)

                title = _safe(item, "item_info", "title", "display_value") or ""
                if not title:
                    continue

                # Image
                image_url = _safe(item, "images", "primary", "large", "url") or ""

                # Price
                listing = None
                listings = _safe(item, "offers", "listings")
                if listings:
                    listing = listings[0]

                price = _safe(listing, "price", "amount")
                savings = _safe(listing, "price", "savings", "amount")
                savings_pct = _safe(listing, "price", "savings", "percentage")
                original_price = _safe(listing, "saving_basis", "amount")
                if original_price is None and price and savings:
                    original_price = price + savings

                # Affiliate URL
                url = f"https://www.amazon.com/dp/{asin}/?tag={associate_tag}"

                # Description from features
                features = _safe(item, "item_info", "features", "display_values") or []
                description = " | ".join(features[:2]) if features else title

                results.append({
                    "asin": asin,
                    "title": title,
                    "url": url,
                    "image_url": image_url,
                    "price": price,
                    "original_price": original_price,
                    "savings": savings,
                    "savings_percent": savings_pct,
                    "category": search_index,
                    "description": description,
                    "first_seen_at": now,
                    "last_seen_at": now,
                })
            logger.info(f"'{keywords}': {len(items)} items")
        except Exception as e:
            logger.warning(f"'{keywords}' failed: {e}")
            continue

    logger.info(f"Total scraped: {len(results)} unique products")
    return results
