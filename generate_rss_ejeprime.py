#!/usr/bin/env python3
"""
RSS Generator for ejeprime.com/residencial
Scrapes https://www.ejeprime.com/residencial and produces ejeprime_residencial.xml
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

BASE_URL = "https://www.ejeprime.com"
NEWS_URL = "https://www.ejeprime.com/residencial"
OUTPUT_FILE = "ejeprime_residencial.xml"

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
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


def fetch_page(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    html = resp.content.decode("utf-8", errors="replace")
    return BeautifulSoup(html, "lxml")


def parse_date_es(raw: str) -> str:
    """Parse '16 abr 2026 - 15:11' → RFC-2822."""
    raw = raw.strip()
    # Pattern: DD mon YYYY - HH:MM
    m = re.match(r"(\d{1,2})\s+([a-záéíóú]+)\s+(\d{4})(?:\s*-\s*(\d{2}:\d{2}))?", raw, re.I)
    if m:
        day, mon_str, year, time_str = m.groups()
        month = MONTHS_ES.get(mon_str.lower()[:3])
        if month:
            time_str = time_str or "00:00"
            hour, minute = map(int, time_str.split(":"))
            dt = datetime(int(year), month, int(day), hour, minute, tzinfo=timezone.utc)
            return format_datetime(dt)
    return format_datetime(datetime.now(timezone.utc))


def extract_articles(soup: BeautifulSoup) -> list[dict]:
    articles = []
    seen_urls = set()

    for article in soup.find_all("article", class_="news_list_item"):
        # URL + Title
        a_title = article.find("a", class_="title") or article.find("a", href=True)
        if not a_title:
            continue
        href = a_title.get("href", "")
        url = urljoin(BASE_URL, href)
        if url in seen_urls:
            continue

        heading = article.find(["h1", "h2", "h3"])
        title = heading.get_text(strip=True) if heading else a_title.get_text(strip=True)
        if not title:
            continue

        # Date: <p class="date">
        date_tag = article.find("p", class_="date")
        raw_date = date_tag.get_text(strip=True) if date_tag else ""

        # Description: <div class="text ...">
        desc_tag = article.find("div", class_=re.compile(r"\btext\b"))
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        # Author
        author_tag = article.find("p", class_="author")
        author = author_tag.get_text(strip=True) if author_tag else ""

        seen_urls.add(url)
        articles.append({
            "title": title,
            "url": url,
            "description": description,
            "date": parse_date_es(raw_date) if raw_date else format_datetime(datetime.now(timezone.utc)),
            "author": author,
        })

    return articles


def build_rss(articles: list[dict]) -> ET.Element:
    rss = ET.Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    rss.set("xmlns:dc", "http://purl.org/dc/elements/1.1/")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "EjePrime - Residencial"
    ET.SubElement(channel, "link").text = NEWS_URL
    ET.SubElement(channel, "description").text = "Noticias sobre promociones residenciales - EjePrime"
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
        if art["author"]:
            ET.SubElement(item, "dc:creator").text = art["author"]

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
