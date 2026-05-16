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
from app.db import init_db, upsert_products, get_unposted_products, mark_bluesky_posted, get_untumblrd_products, mark_tumblr_posted, reset_bluesky_posted, reset_tumblr_posted, get_unslickdealed_products, mark_slickdeals_posted
from app.scraper import scrape_deals
from app.bluesky import post_products
from app.tumblr_post import post_products as tumblr_post_products


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

    # Post to Tumblr
    if os.environ.get("RESET_TUMBLR"):
        reset_tumblr_posted(settings.db_path)
        print("Reset tumblr_posted_at for all products.")
    tumblr_unposted = get_untumblrd_products(settings.db_path, limit=10)
    print(f"Found {len(tumblr_unposted)} unposted products for Tumblr...")
    if tumblr_unposted:
        t_posted = tumblr_post_products(list(tumblr_unposted))
        posted_asins = [p["asin"] for p in list(tumblr_unposted)[:t_posted]]
        if posted_asins:
            mark_tumblr_posted(settings.db_path, posted_asins)
        print(f"Posted {t_posted} to Tumblr.")

    # Post to Slickdeals (local only — needs saved browser session)
    if os.environ.get("POST_SLICKDEALS"):
        from app.slickdeals import post_products as slickdeals_post
        sd_products = get_unslickdealed_products(settings.db_path, limit=10)
        print(f"Found {len(sd_products)} products for Slickdeals...")
        if sd_products:
            sd_posted = slickdeals_post(list(sd_products))
            posted_asins = [p["asin"] for p in list(sd_products)[:sd_posted]]
            if posted_asins:
                mark_slickdeals_posted(settings.db_path, posted_asins)
            print(f"Posted {sd_posted} to Slickdeals.")

    print("Done.")


if __name__ == "__main__":
    main()
