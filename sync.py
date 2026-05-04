"""
Daily sync — run via GitHub Actions.
Scrapes Amazon PA-API and upserts to database.
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
from app.db import init_db, upsert_products
from app.scraper import scrape_deals


def main():
    settings = get_settings()
    if not settings.amazon_access_key or not settings.amazon_secret_key:
        print("ERROR: AMAZON_ACCESS_KEY and AMAZON_SECRET_KEY required")
        sys.exit(1)

    print("Initialising DB...")
    init_db(settings.db_path)

    print("Scraping Amazon deals...")
    items = scrape_deals(
        settings.amazon_access_key,
        settings.amazon_secret_key,
        settings.amazon_associate_tag,
    )
    print(f"Scraped {len(items)} products")

    if items:
        inserted = upsert_products(settings.db_path, items)
        print(f"Inserted {inserted} new products. Done.")
    else:
        print("No products scraped.")


if __name__ == "__main__":
    main()
