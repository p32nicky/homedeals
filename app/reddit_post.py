"""
Post new products to Reddit r/AmazonDealsHome via PRAW.
"""
import logging
import os
import time

logger = logging.getLogger(__name__)

CLIENT_ID     = os.environ.get("REDDIT_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
USERNAME      = os.environ.get("REDDIT_USERNAME", "")
PASSWORD      = os.environ.get("REDDIT_PASSWORD", "")
# One or more subreddits (comma-separated). Each deal is posted to all of them.
SUBREDDITS    = [s.strip() for s in os.environ.get("REDDIT_SUBREDDIT", "AmazonHomeDealz").split(",") if s.strip()]


def post_products(products: list[dict]) -> int:
    if not products:
        return 0
    try:
        import praw
    except ImportError:
        logger.error("Run: pip install praw")
        return 0

    try:
        reddit = praw.Reddit(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            username=USERNAME,
            password=PASSWORD,
            user_agent=f"homedeals/1.0 by u/{USERNAME}",
            redirect_uri="http://localhost:8080",
        )
    except Exception as e:
        logger.error(f"Reddit login failed: {e}")
        return 0

    posted = 0
    for i, p in enumerate(products):
        asin = p.get("asin", "")
        title = p.get("title", "")
        price = p.get("price")
        savings_pct = p.get("savings_percent")
        # Link directly to the Amazon affiliate URL (homedeals site is retired).
        url = p.get("url") or (f"https://www.amazon.com/dp/{asin}/?tag=nicdav09-20" if asin else "")

        # Build title: match Slickdeals style
        post_title = title
        if price:
            post_title = f"{title} ${price:.2f} + Free Shipping - Amazon"
            if savings_pct:
                post_title = f"{title} ${price:.2f} ({int(savings_pct)}% off) + Free Shipping - Amazon"
        post_title = post_title[:300]

        any_ok = False
        for sub in SUBREDDITS:
            try:
                print(f"[{i+1}/{len(products)}] r/{sub}: {post_title[:55]}")
                reddit.subreddit(sub).submit(title=post_title, url=url, resubmit=False)
                any_ok = True
                time.sleep(12)  # Reddit rate limit between submissions
            except Exception as e:
                err = str(e)
                if "DUPLICATE" in err or "already been submitted" in err.lower():
                    any_ok = True  # already there = fine
                else:
                    logger.error(f"[{i+1}] r/{sub} failed {asin}: {err}")
        if any_ok:
            posted += 1  # count the deal as done once it landed on >=1 sub

    return posted
