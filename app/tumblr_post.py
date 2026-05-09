"""
Post new products to Tumblr via NPF API + OAuth1.
"""
import re
import time
import requests
from requests_oauthlib import OAuth1

BLOG = "amzonhomedeals.tumblr.com"
API_URL = f"https://api.tumblr.com/v2/blog/{BLOG}/post"
BITLY_TOKEN = "269c53e1b2eb6dcb2035d4d6ecfac4f2105ce35a"

CONSUMER_KEY    = "TxHYOvd4AVFPBTiKy3AAAbpr9ztCJdFLa8fzTvSiJ9TV3vR1zx"
CONSUMER_SECRET = "p9rAvpJVp9CakR1XwN08jtXs797HHJumYO4MSRKdCqV14Kuh2x"
TOKEN           = "M18FBknEUfj5MtSzARSTy5FEoJLUReb2UxkccqyUqJ9CyJUkkj"
TOKEN_SECRET    = "XVscoOV1zTOx4xrJfL88ZzBksJPOrt06prA46ZhNi7yo8kMrvW"


def _auth():
    return OAuth1(CONSUMER_KEY, CONSUMER_SECRET, TOKEN, TOKEN_SECRET)


def _shorten(url: str) -> str:
    try:
        resp = requests.post(
            "https://api-ssl.bitly.com/v4/shorten",
            json={"long_url": url},
            headers={"Authorization": f"Bearer {BITLY_TOKEN}"},
            timeout=5,
        )
        return resp.json().get("link", url)
    except Exception:
        return url


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def post_products(products: list[dict]) -> int:
    print(f"=== TUMBLR v5 LEGACY LINK url={API_URL} ===")
    posted = 0
    for i, p in enumerate(products):
        try:
            title = p["title"]
            price_line = ""
            if p.get("savings_percent"):
                price_line = f"🔥 {int(p['savings_percent'])}% OFF"
                if p.get("price"):
                    price_line += f" — Now ${p['price']:.2f}"

            desc = _strip_html(p.get("description") or title)

            short_url = _shorten(p["url"])
            data = {
                "type": "link",
                "title": title[:255],
                "url": short_url,
                "description": f"{price_line}\n\n{desc}"[:1000],
                "tags": "amazon,deals,homedecor,homeorganization,DIY,homegarden,sale",
            }

            print(f"[{i+1}/{len(products)}] Posting: {title[:50]}")
            resp = requests.post(API_URL, data=data, auth=_auth(), timeout=15)
            print(f"Tumblr status={resp.status_code}")
            if resp.status_code in (200, 201):
                posted += 1
                print(f"[{i+1}] OK — total={posted}")
            else:
                print(f"[{i+1}] FAILED: {resp.text[:200]}")

            time.sleep(1)

        except Exception as e:
            print(f"[{i+1}] Exception {p.get('asin')}: {e}")

    return posted
