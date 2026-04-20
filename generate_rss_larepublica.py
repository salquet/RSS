#!/usr/bin/env python3
"""RSS Generator for larepublica.co"""

import re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess; subprocess.check_call([sys.executable,"-m","pip","install","requests","beautifulsoup4","lxml"])
    import requests; from bs4 import BeautifulSoup

NEWS_URL = "https://www.larepublica.co/"
OUTPUT_FILE = "larepublica.xml"
HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36","Accept-Language":"es-ES,es;q=0.9"}
ARTICLE_PATTERN = re.compile(r"larepublica\.co/(economia|empresas|finanzas|globoeconomia|especiales)/[^\"]+\d{7,}")

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.content.decode("utf-8","replace"), "lxml")

def extract(soup):
    articles, seen = [], set()
    for a in soup.find_all("a", href=ARTICLE_PATTERN):
        url = a["href"]
        if not url.startswith("http"): url = urljoin(NEWS_URL, url)
        if url in seen: continue
        title = a.get_text(strip=True)
        if not title or len(title) < 10: continue
        seen.add(url)
        articles.append({"title":title,"url":url,"date":format_datetime(datetime.now(timezone.utc))})
    return articles

def build_rss(articles):
    rss = ET.Element("rss", version="2.0"); rss.set("xmlns:atom","http://www.w3.org/2005/Atom")
    ch = ET.SubElement(rss,"channel")
    ET.SubElement(ch,"title").text="La República Colombia"
    ET.SubElement(ch,"link").text=NEWS_URL
    ET.SubElement(ch,"description").text="Noticias económicas y financieras de Colombia"
    ET.SubElement(ch,"language").text="es"
    ET.SubElement(ch,"lastBuildDate").text=format_datetime(datetime.now(timezone.utc))
    al=ET.SubElement(ch,"atom:link"); al.set("href",NEWS_URL); al.set("rel","self"); al.set("type","application/rss+xml")
    for a in articles:
        it=ET.SubElement(ch,"item")
        ET.SubElement(it,"title").text=a["title"]
        ET.SubElement(it,"link").text=a["url"]
        ET.SubElement(it,"guid",isPermaLink="true").text=a["url"]
        ET.SubElement(it,"pubDate").text=a["date"]
    return rss

def main():
    print(f"Fetching {NEWS_URL}...")
    soup = fetch(NEWS_URL)
    articles = extract(soup)
    print(f"Found {len(articles)} articles.")
    if not articles: sys.exit(1)
    tree = ET.ElementTree(build_rss(articles)); ET.indent(tree, space="  ")
    with open(OUTPUT_FILE,"wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="utf-8", xml_declaration=False)
    print(f"RSS saved to {OUTPUT_FILE}")
    for i,a in enumerate(articles[:5],1): print(f"  {i}. {a['title'][:70]}")

if __name__=="__main__": main()
