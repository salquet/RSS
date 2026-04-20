#!/usr/bin/env python3
"""
RSS Generator for observatorioinmobiliario.es
Produces observatorio_inmobiliario.xml
"""

import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "lxml"])
    import requests
    from bs4 import BeautifulSoup

BASE_URL = "https://observatorioinmobiliario.es"
NEWS_URL = "https://observatorioinmobiliario.es/"
OUTPUT_FILE = "observatorio_inmobiliario.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def fetch_page(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    html = resp.content.decode("utf-8", errors="replace")
    return BeautifulSoup(html, "lxml")


def parse_date_es(raw: str) -> str:
    """Parse '17 abril 2026' → RFC-2822."""
    raw = raw.strip()
    m = re.match(r"(\d{1,2})\s+([a-záéíóú]+)\s+(\d{4})", raw, re.I)
    if m:
        day, mon_str, year = m.groups()
        month = MONTHS_ES.get(mon_str.lower())
        if month:
            dt = datetime(int(year), month, int(day), tzinfo=timezone.utc)
            return format_datetime(dt)
    return format_datetime(datetime.now(timezone.utc))


def extract_articles(soup: BeautifulSoup) -> list[dict]:
    articles = []
    seen_urls = set()

    for article in soup.find_all("article"):
        # Title: class "card-body-title" (h2, h3, or p)
        title_tag = article.find(class_="card-body-title")
        if not title_tag:
            continue

        # If it's a container with a nested <a>, get the link from there
        a_in_title = title_tag.find("a", href=True) if title_tag.name not in ("a",) else None
        a_tag = a_in_title or title_tag.find_parent("a") or article.find("a", href=lambda h: h and "/noticias/" in h)
        if not a_tag:
            continue

        href = a_tag.get("href", "")
        if not href or "/tags/" in href:
            # Try any /noticias/ link in article
            a_tag = article.find("a", href=lambda h: h and "/noticias/" in h)
            if not a_tag:
                continue
            href = a_tag["href"]

        url = urljoin(BASE_URL, href)
        if url in seen_urls:
            continue

        title = title_tag.get_text(strip=True)
        if not title:
            continue

        # Date: <time class="card-body-date">
        time_tag = article.find("time", class_="card-body-date")
        raw_date = time_tag.get_text(strip=True) if time_tag else ""

        seen_urls.add(url)
        articles.append({
            "title": title,
            "url": url,
            "date": parse_date_es(raw_date) if raw_date else format_datetime(datetime.now(timezone.utc)),
        })

    return articles


def build_rss(articles: list[dict]) -> ET.Element:
    rss = ET.Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "Observatorio Inmobiliario"
    ET.SubElement(channel, "link").text = NEWS_URL
    ET.SubElement(channel, "description").text = "Noticias del mercado inmobiliario - Observatorio Inmobiliario"
    ET.SubElement(channel, "language").text = "es"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(datetime.now(timezone.utc))

    atom_link = ET.SubElement(channel, "atom:link")
    atom_link.set("href", NEWS_URL)
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    for art in articles:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = art["title"]
        ET.SubElement(item, "link").text = art["url"]
        ET.SubElement(item, "guid", isPermaLink="true").text = art["url"]
        ET.SubElement(item, "pubDate").text = art["date"]

    return rss


def main() -> None:
    print(f"Fetching {NEWS_URL} ...")
    soup = fetch_page(NEWS_URL)

    articles = extract_articles(soup)
    print(f"Found {len(articles)} articles.")

    if not articles:
        print("No articles found. The page structure may have changed.")
        sys.exit(1)

    rss_root = build_rss(articles)
    tree = ET.ElementTree(rss_root)
    ET.indent(tree, space="  ")

    with open(OUTPUT_FILE, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="utf-8", xml_declaration=False)

    print(f"RSS saved to {OUTPUT_FILE}")
    for i, art in enumerate(articles[:5], 1):
        print(f"  {i}. {art['title'][:70]}")
    if len(articles) > 5:
        print(f"  ... and {len(articles) - 5} more.")


if __name__ == "__main__":
    main()
