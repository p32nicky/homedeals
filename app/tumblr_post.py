"""
Post new products to Tumblr via OAuth1.
"""
import logging
import httpx
from requests_oauthlib import OAuth1

logger = logging.getLogger(__name__)

BLOG = "amzonhomedeals.tumblr.com"
API_URL = f"https://api.tumblr.com/v2/blog/{BLOG}/post"

CONSUMER_KEY    = "TxHYOvd4AVFPBTiKy3AAAbpr9ztCJdFLa8fzTvSiJ9TV3vR1zx"
CONSUMER_SECRET = "p9rAvpJVp9CakR1XwN08jtXs797HHJumYO4MSRKdCqV14Kuh2x"
TOKEN           = "M18FBknEUfj5MtSzARSTy5FEoJLUReb2UxkccqyUqJ9CyJUkkj"
TOKEN_SECRET    = "XVscoOV1zTOx4xrJfL88ZzBksJPOrt06prA46ZhNi7yo8kMrvW"


def _auth():
    return OAuth1(CONSUMER_KEY, CONSUMER_SECRET, TOKEN, TOKEN_SECRET)


def post_products(products: list[dict]) -> int:
    import requests
    posted = 0
    for p in products:
        try:
            title = p["title"]
            price_info = ""
            if p.get("savings_percent"):
                price_info = f"<p>🔥 <strong>{int(p['savings_percent'])}% OFF</strong>"
                if p.get("price"):
                    price_info += f" — Now <strong>${p['price']:.2f}</strong>"
                price_info += "</p>"

            body = f"""
<h2>{title}</h2>
{price_info}
<p>{p.get('description') or title}</p>
<p><a href="{p['url']}" target="_blank">👉 View Deal on Amazon</a></p>
"""
            data = {
                "type": "text",
                "title": title[:255],
                "body": body,
                "tags": "amazon,deals,homedecor,homeorganization,DIY,homegarden,sale",
                "native_inline_images": True,
            }

            # Add image if available
            if p.get("image_url"):
                data["type"] = "photo"
                data["source"] = p["image_url"]
                data["caption"] = body

            resp = requests.post(API_URL, data=data, auth=_auth(), timeout=15)
            if resp.status_code in (200, 201):
                posted += 1
                print(f"Tumblr posted [{posted}]: {title[:50]}")
            else:
                print(f"Tumblr error {resp.status_code}: {resp.text[:200]}")

            import time
            time.sleep(1)

        except Exception as e:
            print(f"Tumblr exception {p.get('asin')}: {e}")

    return posted
