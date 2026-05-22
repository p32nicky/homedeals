"""
Daily sync — run via GitHub Actions.
Scrapes deals, upserts to DB, posts unposted items to Bluesky.
"""
import os

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
from app.db import init_db, upsert_products, get_unposted_products, mark_bluesky_posted, reset_bluesky_posted, get_unreddited_products, mark_reddit_posted
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

    if items:
        inserted = upsert_products(settings.db_path, items)
        print(f"Inserted {inserted} new products.")
    else:
        print("No products scraped.")

    # Reset bluesky_posted_at if switching accounts
    if os.environ.get("RESET_BLUESKY"):
        reset_bluesky_posted(settings.db_path)
        print("Reset bluesky_posted_at for all products.")

    # Post unposted products to Bluesky (up to 10/day)
    print(f"Bluesky password set: {bool(bluesky_password)}")
    if bluesky_password:
        unposted = get_unposted_products(settings.db_path, limit=5)
        print(f"Found {len(unposted)} unposted products with images for Bluesky...")
        if unposted:
            posted = post_products(list(unposted), bluesky_password)
            posted_asins = [p["asin"] for p in list(unposted)[:posted]]
            if posted_asins:
                mark_bluesky_posted(settings.db_path, posted_asins)
            print(f"Posted {posted} to Bluesky.")
        else:
            print("All products already posted to Bluesky.")
    else:
        print("BLUESKY_APP_PASSWORD not set — skipping Bluesky.")

    # Post to Reddit
    from app.reddit_post import post_products as reddit_post
    reddit_products = get_unreddited_products(settings.db_path, limit=25)
    print(f"Found {len(reddit_products)} unposted products for Reddit...")
    if reddit_products:
        r_posted = reddit_post(list(reddit_products))
        posted_asins = [p["asin"] for p in list(reddit_products)[:r_posted]]
        if posted_asins:
            mark_reddit_posted(settings.db_path, posted_asins)
        print(f"Posted {r_posted} to Reddit.")

    print("Done.")


if __name__ == "__main__":
    main()
