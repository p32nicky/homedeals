"""
Post new products to Tumblr via OAuth1.
"""
import time
import requests
from requests_oauthlib import OAuth1

BLOG = "amzonhomedeals.tumblr.com"
API_URL = f"https://api.tumblr.com/v2/blog/{BLOG}/post"

CONSUMER_KEY    = "TxHYOvd4AVFPBTiKy3AAAbpr9ztCJdFLa8fzTvSiJ9TV3vR1zx"
CONSUMER_SECRET = "p9rAvpJVp9CakR1XwN08jtXs797HHJumYO4MSRKdCqV14Kuh2x"
TOKEN           = "M18FBknEUfj5MtSzARSTy5FEoJLUReb2UxkccqyUqJ9CyJUkkj"
TOKEN_SECRET    = "XVscoOV1zTOx4xrJfL88ZzBksJPOrt06prA46ZhNi7yo8kMrvW"


def _auth():
    return OAuth1(CONSUMER_KEY, CONSUMER_SECRET, TOKEN, TOKEN_SECRET)


def _post(data: dict) -> bool:
    resp = requests.post(API_URL, data=data, auth=_auth(), timeout=15)
    print(f"Tumblr status={resp.status_code}")
    return resp.status_code in (200, 201)


def post_products(products: list[dict]) -> int:
    posted = 0
    for i, p in enumerate(products):
        try:
            title = p["title"]
            price_info = ""
            if p.get("savings_percent"):
                price_info = f"<p>🔥 <strong>{int(p['savings_percent'])}% OFF</strong>"
                if p.get("price"):
                    price_info += f" — Now <strong>${p['price']:.2f}</strong>"
                price_info += "</p>"

            img_tag = f'<p><img src="{p["image_url"]}"/></p>' if p.get("image_url") else ""
            body = f"""{img_tag}
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
            }

            print(f"[{i+1}/{len(products)}] Posting: {title[:50]}")
            ok = _post(data)
            if ok:
                posted += 1
                print(f"[{i+1}] OK — total={posted}")
            else:
                print(f"[{i+1}] FAILED")

            time.sleep(1)

        except Exception as e:
            print(f"[{i+1}] Exception {p.get('asin')}: {e}")

    return posted
