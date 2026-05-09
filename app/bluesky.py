"""
Post new products to Bluesky via AT Protocol.
"""
import logging
import time

logger = logging.getLogger(__name__)

HANDLE = "amazondealshome.bsky.social"


def post_products(products: list[dict], app_password: str) -> int:
    if not products or not app_password:
        return 0
    try:
        from atproto import Client
    except ImportError:
        logger.error("atproto not installed. Run: pip install atproto")
        return 0

    client = Client()
    try:
        client.login(HANDLE, app_password)
        print("Bluesky login OK")
    except Exception as e:
        print(f"Bluesky login FAILED: {e}")
        return 0

    posted = 0
    for i, p in enumerate(products):
        try:
            title = p["title"][:120]
            price_info = ""
            if p.get("savings_percent"):
                price_info = f"🔥 {int(p['savings_percent'])}% OFF"
            if p.get("price"):
                price_info += f" — Now ${p['price']:.2f}"

            text = f"🏠 {title}\n{price_info}\n\n{p['url']}"
            if len(text) > 300:
                text = f"🏠 {title[:160]}\n{price_info}\n\n{p['url']}"

            print(f"[{i+1}/{len(products)}] Posting: {title[:50]}")
            client.send_post(text=text)
            posted += 1
            print(f"[{i+1}] OK — total posted={posted}")
            time.sleep(2)

        except Exception as e:
            print(f"[{i+1}] ERROR {p.get('asin')}: {type(e).__name__}: {e}")

    return posted
