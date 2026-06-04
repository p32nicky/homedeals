"""
Post new products to Reddit r/AmazonDealsHome via PRAW.
"""
import logging
import time

logger = logging.getLogger(__name__)

CLIENT_ID     = "weFtQwJPb1wsdq2IXexp7Q"
CLIENT_SECRET = "a-mqkbBtpHICVo--xQWIAPENM_bSUw"
USERNAME      = "Basic-Strain-6922"
PASSWORD      = "Nd2354zx!!??"
SUBREDDIT     = "AmazonDealsHome"


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
        subreddit = reddit.subreddit(SUBREDDIT)
    except Exception as e:
        logger.error(f"Reddit login failed: {e}")
        return 0

    posted = 0
    for i, p in enumerate(products):
        try:
            asin = p.get("asin", "")
            title = p.get("title", "")
            price = p.get("price")
            savings_pct = p.get("savings_percent")
            url = f"https://homedeals-beta.vercel.app/product/{asin}" if asin else p.get("url", "")

            # Build title: match Slickdeals style
            post_title = title
            if price:
                post_title = f"{title} ${price:.2f} + Free Shipping - Amazon"
                if savings_pct:
                    post_title = f"{title} ${price:.2f} ({int(savings_pct)}% off) + Free Shipping - Amazon"
            post_title = post_title[:300]

            print(f"[{i+1}/{len(products)}] Posting to Reddit: {post_title[:60]}")
            subreddit.submit(title=post_title, url=url, resubmit=False)
            posted += 1
            print(f"[{i+1}] OK")
            time.sleep(12)  # Reddit rate limit

        except Exception as e:
            err = str(e)
            if "DUPLICATE" in err or "already been submitted" in err.lower():
                posted += 1  # already posted = fine
            else:
                logger.error(f"[{i+1}] Failed {p.get('asin')}: {err}")

    return posted
