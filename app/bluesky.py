"""
Post new products to Bluesky via AT Protocol.
"""
import logging
import httpx

logger = logging.getLogger(__name__)

HANDLE = "amazonhomedeals.bsky.social"


def post_products(products: list[dict], app_password: str) -> int:
    if not products or not app_password:
        return 0
    try:
        from atproto import Client, models
    except ImportError:
        logger.error("atproto not installed. Run: pip install atproto")
        return 0

    client = Client()
    try:
        client.login(HANDLE, app_password)
    except Exception as e:
        logger.error(f"Bluesky login failed: {e}")
        return 0

    posted = 0
    for p in products:
        try:
            title = p["title"][:100]
            price_info = ""
            if p.get("savings_percent"):
                price_info = f"🔥 {int(p['savings_percent'])}% OFF"
            if p.get("price"):
                price_info += f" — Now ${p['price']:.2f}"

            text = f"🏠 {title}\n{price_info}\n\n{p['url']}"
            # Bluesky post max 300 chars
            if len(text) > 300:
                text = f"🏠 {title[:180]}\n{price_info}\n\n{p['url']}"

            # Build link card embed
            # Upload image — skip post if it fails
            thumb_blob = None
            if p.get("image_url"):
                try:
                    resp = httpx.get(p["image_url"], timeout=8, follow_redirects=True)
                    if len(resp.content) > 2000:
                        thumb_blob = client.upload_blob(resp.content).blob
                except Exception:
                    pass

            if not thumb_blob:
                # Try fallback image URL format
                try:
                    fallback = f"https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&MarketPlace=US&ASIN={p['asin']}&ServiceVersion=20070822&ID=AsinImage&WS=1&Format=SL500"
                    resp = httpx.get(fallback, timeout=8, follow_redirects=True)
                    if len(resp.content) > 2000:
                        thumb_blob = client.upload_blob(resp.content).blob
                except Exception:
                    pass

            if not thumb_blob:
                logger.info(f"Skipping (no valid image): {title[:50]}")
                continue

            embed = models.AppBskyEmbedExternal.Main(
                external=models.AppBskyEmbedExternal.External(
                    uri=p["url"],
                    title=title,
                    description=p.get("description") or title,
                    thumb=thumb_blob,
                )
            )

            client.send_post(text=text, embed=embed)
            posted += 1
            logger.info(f"Posted to Bluesky: {title[:50]}")

            # Small delay to avoid rate limits
            import time
            time.sleep(2)

        except Exception as e:
            logger.warning(f"Failed to post {p.get('asin')}: {e}")

    return posted
