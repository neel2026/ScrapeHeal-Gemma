"""Small, real websites used by the live ScrapeHeal-Gemma walkthrough."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup


BOOKS_TO_SCRAPE_URL = "https://books.toscrape.com/"


def fetch_books_to_scrape() -> str:
    """Fetch the current Books to Scrape listing and reject unrelated responses."""
    response = requests.get(
        BOOKS_TO_SCRAPE_URL,
        timeout=35,
        headers={"User-Agent": "ScrapeHeal-Gemma/1.0 (+https://books.toscrape.com/)"},
    )
    response.raise_for_status()
    detected_encoding = getattr(response, "apparent_encoding", None)
    if detected_encoding:
        response.encoding = detected_encoding
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select("article.product_pod"):
        raise ValueError("The response did not look like Books to Scrape: no book cards were found.")
    return html
