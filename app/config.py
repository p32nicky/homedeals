import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str
    site_url: str
    site_title: str
    amazon_access_key: str
    amazon_secret_key: str
    amazon_associate_tag: str


def get_settings() -> Settings:
    return Settings(
        db_path=os.environ.get("DB_PATH", "./data/homedeals.sqlite3"),
        site_url=os.environ.get("SITE_URL", "https://homedeals.vercel.app"),
        site_title=os.environ.get("SITE_TITLE", "Home Deals Daily"),
        amazon_access_key=os.environ.get("AMAZON_ACCESS_KEY", ""),
        amazon_secret_key=os.environ.get("AMAZON_SECRET_KEY", ""),
        amazon_associate_tag=os.environ.get("AMAZON_ASSOCIATE_TAG", "nicdav09-20"),
    )
