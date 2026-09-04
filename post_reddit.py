"""Post N unposted Amazon deals to r/AmazonHomeDealz.

Runs daily via GitHub Actions. With DATABASE_URL set it reads/writes the cloud
Postgres DB (persistent, computer-off); locally it falls back to the sqlite DB.

Usage: python post_reddit.py [limit]   (default 8)
"""
import os
import sys

# Load .env for local runs (Actions injects env directly)
_env = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env):
    for line in open(_env):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from app.config import get_settings
from app.db import init_db, get_unreddited_products, mark_reddit_posted
from app.reddit_post import post_products


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("REDDIT_DAILY_LIMIT", "8"))
    settings = get_settings()
    init_db(settings.db_path)

    products = list(get_unreddited_products(settings.db_path, limit=limit))
    print(f"Found {len(products)} unposted deals for r/{os.environ.get('REDDIT_SUBREDDIT','AmazonHomeDealz')} "
          f"(limit {limit})")
    if not products:
        print("Nothing to post.")
        return 0

    posted = post_products(products)
    if posted:
        mark_reddit_posted(settings.db_path, [p["asin"] for p in products[:posted]])
    print(f"Posted {posted} deal(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
