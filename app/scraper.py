"""
Scrape home deals directly from Amazon Product Advertising API 5.0.
Searches Home & Kitchen category for deals with savings.
"""
import logging
import os
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ASIN_RE = re.compile(r'/dp/([A-Z0-9]{10})')

SEARCH_TERMS = [
    "home organization",
    "home decor",
    "kitchen storage",
    "wall decor",
    "closet organizer",
    "bathroom accessories",
    "bedding",
    "home office",
    "garden tools",
    "smart home",
]


def _extract_asin(url: str):
    m = ASIN_RE.search(url or "")
    return m.group(1) if m else None


def scrape_deals(access_key: str, secret_key: str, associate_tag: str) -> list[dict]:
    try:
        from amazon_paapi import AmazonApi
    except ImportError:
        logger.error("Run: pip install python-amazon-paapi")
        return []

    if not access_key or not secret_key:
        logger.error("Missing AMAZON_ACCESS_KEY or AMAZON_SECRET_KEY")
        return []

    amazon = AmazonApi(access_key, secret_key, associate_tag, "US")
    now = datetime.now(timezone.utc).isoformat()
    results = []
    seen_asins: set = set()

    for term in SEARCH_TERMS:
        try:
            resp = amazon.search_items(
                keywords=term,
                search_index="HomeAndKitchen",
                item_count=10,
                resources=[
                    "Images.Primary.Large",
                    "ItemInfo.Title",
                    "Offers.Listings.Price",
                    "Offers.Listings.SavingBasis",
                    "Offers.Listings.DeliveryInfo.IsFreeShippingEligible",
                    "Offers.Listings.Promotions",
                ],
            )

            items = resp.items if resp and resp.items else []
            count = 0
            for item in items:
                try:
                    asin = item.asin
                    if not asin or asin in seen_asins:
                        continue

                    title = (item.item_info.title.display_value
                             if item.item_info and item.item_info.title else None)
                    if not title:
                        continue

                    # Get price info
                    price = None
                    original_price = None
                    listing = (item.offers.listings[0]
                               if item.offers and item.offers.listings else None)
                    if listing and listing.price:
                        price = listing.price.amount
                    if listing and listing.saving_basis:
                        original_price = listing.saving_basis.amount

                    # Skip if no discount
                    if not price or not original_price or original_price <= price:
                        continue

                    savings = round(original_price - price, 2)
                    savings_pct = round((savings / original_price) * 100, 1)

                    # Skip tiny discounts
                    if savings_pct < 10:
                        continue

                    image_url = ""
                    if item.images and item.images.primary and item.images.primary.large:
                        image_url = item.images.primary.large.url

                    affiliate_url = f"https://www.amazon.com/dp/{asin}/?tag={associate_tag}"

                    seen_asins.add(asin)
                    results.append({
                        "asin": asin,
                        "title": title,
                        "url": affiliate_url,
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
                    count += 1

                except Exception as e:
                    logger.debug(f"Item parse error: {e}")
                    continue

            logger.info(f"'{term}': {count} deals found")

        except Exception as e:
            logger.warning(f"Search failed for '{term}': {e}")

    logger.info(f"Total: {len(results)} unique deals from Amazon PA API")
    return results
