#!/usr/bin/env python3
"""
RSS Generator for idealista/news
Scrapes https://www.idealista.com/news/ and produces idealista_news.xml
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
    print("Installing dependencies...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "lxml"])
    import requests
    from bs4 import BeautifulSoup

BASE_URL = "https://www.idealista.com"
NEWS_URL = "https://www.idealista.com/news/"
OUTPUT_FILE = "idealista_news.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}


def fetch_page(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def parse_date(raw: str) -> str:
    """Convert DD/MM/YYYY or ISO-like strings to RFC-2822 for RSS."""
    raw = raw.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return format_datetime(dt)
        except ValueError:
            continue
    # Fallback: now
    return format_datetime(datetime.now(timezone.utc))


def extract_articles(soup: BeautifulSoup) -> list[dict]:
    articles = []
    seen_urls = set()

    # Strategy 1: <article> tags
    for tag in soup.find_all("article"):
        a = tag.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        if not href.startswith("/news/") and not href.startswith("http"):
            continue
        url = urljoin(BASE_URL, href)
        if url in seen_urls:
            continue

        # Title: first heading or link text
        heading = tag.find(["h1", "h2", "h3", "h4"])
        title = (heading.get_text(strip=True) if heading else a.get_text(strip=True))
        if not title:
            continue

        # Description
        p = tag.find("p")
        description = p.get_text(strip=True) if p else ""

        # Date
        date_tag = tag.find(["time", "span"], class_=re.compile(r"date|time|fecha|published", re.I))
        if not date_tag:
            date_tag = tag.find("time")
        raw_date = ""
        if date_tag:
            raw_date = date_tag.get("datetime") or date_tag.get_text(strip=True)

        seen_urls.add(url)
        articles.append({
            "title": title,
            "url": url,
            "description": description,
            "date": parse_date(raw_date) if raw_date else format_datetime(datetime.now(timezone.utc)),
        })

    # Strategy 2: anchor tags whose href matches /news/…/YYYY/MM/DD/
    if not articles:
        pattern = re.compile(r"^/news/.+/\d{4}/\d{2}/\d{2}/")
        for a in soup.find_all("a", href=pattern):
            url = urljoin(BASE_URL, a["href"])
            if url in seen_urls:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                # Try parent heading
                parent = a.find_parent(["h1", "h2", "h3", "h4", "li", "div"])
                if parent:
                    heading = parent.find(["h1", "h2", "h3", "h4"])
                    title = heading.get_text(strip=True) if heading else title
            if not title or len(title) < 5:
                continue

            # Extract date from URL  /news/section/year/month/day/id-slug
            m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", a["href"])
            raw_date = f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else ""

            seen_urls.add(url)
            articles.append({
                "title": title,
                "url": url,
                "description": "",
                "date": parse_date(raw_date) if raw_date else format_datetime(datetime.now(timezone.utc)),
            })

    return articles


def build_rss(articles: list[dict]) -> ET.Element:
    rss = ET.Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "idealista/news"
    ET.SubElement(channel, "link").text = NEWS_URL
    ET.SubElement(channel, "description").text = "Noticias inmobiliarias de idealista"
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


def indent(elem: ET.Element, level: int = 0) -> None:
    """Add pretty-print indentation in-place."""
    pad = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = pad + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = pad
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = pad
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = pad


def main() -> None:
    print(f"Fetching {NEWS_URL} ...")
    soup = fetch_page(NEWS_URL)

    articles = extract_articles(soup)
    print(f"Found {len(articles)} articles.")

    if not articles:
        print("No articles found. The page structure may have changed.")
        sys.exit(1)

    rss_root = build_rss(articles)
    indent(rss_root)

    tree = ET.ElementTree(rss_root)
    ET.indent(tree, space="  ")  # Python 3.9+

    with open(OUTPUT_FILE, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="utf-8", xml_declaration=False)

    print(f"RSS saved to {OUTPUT_FILE}")

    # Print summary
    for i, art in enumerate(articles[:5], 1):
        print(f"  {i}. {art['title'][:70]}")
    if len(articles) > 5:
        print(f"  ... and {len(articles) - 5} more.")


if __name__ == "__main__":
    main()
