"""
Daily sync — run via GitHub Actions.
Scrapes deals, upserts to DB, posts new items to Bluesky.
"""
import os
import sys

# Load .env for local runs
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from app.config import get_settings
from app.db import init_db, upsert_products, get_products_by_asins
from app.scraper import scrape_deals
from app.bluesky import post_products


def main():
    settings = get_settings()
    bluesky_password = os.environ.get("BLUESKY_APP_PASSWORD", "")

    print("Initialising DB...")
    init_db(settings.db_path)

    print("Scraping deals...")
    items = scrape_deals(
        settings.amazon_access_key,
        settings.amazon_secret_key,
        settings.amazon_associate_tag,
    )
    print(f"Scraped {len(items)} products")

    if not items:
        print("No products scraped.")
        return

    inserted = upsert_products(settings.db_path, items)
    print(f"Inserted {inserted} new products.")

    # Post new products to Bluesky
    if bluesky_password and inserted > 0:
        # Get the newly inserted items
        new_asins = [it["asin"] for it in items][-inserted:] if inserted else []
        new_items = [it for it in items if it["asin"] in new_asins and it.get("image_url")][:10]  # max 10/run, images only
        print(f"Posting {len(new_items)} new items to Bluesky...")
        posted = post_products(new_items, bluesky_password)
        print(f"Posted {posted} to Bluesky.")
    else:
        print("No new products to post to Bluesky." if inserted == 0 else "BLUESKY_APP_PASSWORD not set.")

    print("Done.")


if __name__ == "__main__":
    main()
