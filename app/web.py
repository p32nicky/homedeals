import logging
import os
from datetime import datetime, timezone, timedelta
from xml.etree.ElementTree import Element, SubElement, tostring

import jinja2
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db, list_products, get_latest_products, get_product_by_asin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
init_db(settings.db_path)

app = FastAPI(title=settings.site_title)

BASE_DIR = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(BASE_DIR, "templates")),
    autoescape=True,
)


def render(name: str, **ctx) -> HTMLResponse:
    html = _jinja_env.get_template(name).render(**ctx)
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    q: str = Query("", alias="q"),
    page: int = Query(1, ge=1),
):
    per_page = 24
    rows, total = list_products(settings.db_path, query=q, page=page, per_page=per_page)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render("index.html",
        products=rows, query=q, page=page,
        total=total, total_pages=total_pages,
        site_title=settings.site_title,
    )


@app.get("/product/{asin}", response_class=HTMLResponse)
async def product_detail(request: Request, asin: str):
    product = get_product_by_asin(settings.db_path, asin)
    if not product:
        return HTMLResponse("Product not found", status_code=404)
    return render("product.html", p=product, site_title=settings.site_title)


@app.get("/feed.xml")
async def rss_feed():
    products = get_latest_products(settings.db_path, limit=100, offset=0)

    rss = Element("rss", version="2.0")
    rss.set("xmlns:media", "http://search.yahoo.com/mrss/")
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = settings.site_title
    SubElement(channel, "link").text = settings.site_url
    SubElement(channel, "description").text = "Daily Amazon deals on home decor, DIY & organization"
    SubElement(channel, "language").text = "en-us"
    SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )

    now = datetime.now(timezone.utc)
    for idx, p in enumerate(products):
        item = SubElement(channel, "item")
        product_url = f"{settings.site_url}/product/{p['asin']}"
        title = p["title"]
        if p.get("savings_percent"):
            title = f"{int(p['savings_percent'])}% OFF - {title}"

        SubElement(item, "title").text = title
        SubElement(item, "link").text = product_url
        SubElement(item, "guid", isPermaLink="true").text = product_url

        desc = p.get("description") or p["title"]
        price_info = ""
        if p.get("price"):
            price_info = f"Now: ${p['price']:.2f}"
            if p.get("original_price"):
                price_info += f" (was ${p['original_price']:.2f})"
        p_url = p["url"]
        SubElement(item, "description").text = (
            f"{desc}<br/>{price_info}<br/>"
            f'<a href="{p_url}">View on Amazon →</a>'
        )

        if p.get("image_url"):
            enc = SubElement(item, "enclosure")
            enc.set("url", p["image_url"])
            enc.set("type", "image/jpeg")
            enc.set("length", "0")
            media = SubElement(item, "media:content")
            media.set("url", p["image_url"])
            media.set("medium", "image")

        pub_dt = now + timedelta(hours=idx * 2)
        SubElement(item, "pubDate").text = pub_dt.strftime("%a, %d %b %Y %H:%M:%S +0000")

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="unicode")
    return Response(content=xml_str, media_type="application/rss+xml")


@app.get("/api/status")
async def status():
    _, total = list_products(settings.db_path, per_page=1)
    return JSONResponse({"total_products": total, "site": settings.site_url})
