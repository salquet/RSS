#!/usr/bin/env python3
"""
RSS Generator for elconfidencial.com/inmobiliario
Produces elconfidencial_inmobiliario.xml
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

BASE_URL = "https://www.elconfidencial.com"
NEWS_URL = "https://www.elconfidencial.com/inmobiliario/"
OUTPUT_FILE = "elconfidencial_inmobiliario.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_page(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    html = resp.content.decode("utf-8", errors="replace")
    return BeautifulSoup(html, "lxml")


def date_from_url(url: str) -> str:
    """Extract date from URL pattern /YYYY-MM-DD/ → RFC-2822."""
    m = re.search(r"/(\d{4})-(\d{2})-(\d{2})/", url)
    if m:
        dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        return format_datetime(dt)
    return format_datetime(datetime.now(timezone.utc))


def extract_articles(soup: BeautifulSoup) -> list[dict]:
    articles = []
    seen_urls = set()

    for article in soup.find_all("article"):
        # URL: any <a> linking to /inmobiliario/
        a_tag = article.find("a", href=lambda h: h and "/inmobiliario/" in h)
        if not a_tag:
            continue
        url = a_tag["href"]
        if not url.startswith("http"):
            url = urljoin(BASE_URL, url)
        if url in seen_urls:
            continue

        # Title: first heading
        heading = article.find(["h1", "h2", "h3", "h4"])
        title = heading.get_text(strip=True) if heading else a_tag.get_text(strip=True)
        if not title:
            continue

        # Description: <p class="..leadin.."> or first <p>
        desc_tag = article.find("p", class_=re.compile(r"leadin|subtitle|summary", re.I))
        if not desc_tag:
            desc_tag = article.find("p")
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        seen_urls.add(url)
        articles.append({
            "title": title,
            "url": url,
            "description": description,
            "date": date_from_url(url),
        })

    return articles


def build_rss(articles: list[dict]) -> ET.Element:
    rss = ET.Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "El Confidencial - Inmobiliario"
    ET.SubElement(channel, "link").text = NEWS_URL
    ET.SubElement(channel, "description").text = "Noticias inmobiliarias de El Confidencial"
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
        if art["description"]:
            ET.SubElement(item, "description").text = art["description"]

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
