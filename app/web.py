import logging
import os
from datetime import datetime, timezone, timedelta

import jinja2
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
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


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return render("privacy.html", site_title=settings.site_title, query="")


@app.get("/go/{asin}")
async def go(asin: str):
    from fastapi.responses import RedirectResponse
    product = get_product_by_asin(settings.db_path, asin)
    url = product["url"] if product else f"https://www.amazon.com/dp/{asin}/?tag=nicdav09-20"
    return RedirectResponse(url=url, status_code=302)




@app.get("/api/status")
async def status():
    _, total = list_products(settings.db_path, per_page=1)
    return JSONResponse({"total_products": total, "site": settings.site_url})
