#!/usr/bin/env python3
"""RSS Generator for indiatoday.in/india-today-money/insurance"""

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

BASE_URL = "https://www.indiatoday.in"
NEWS_URL = "https://www.indiatoday.in/india-today-money/insurance"
OUTPUT_FILE = "indiatoday_insurance.xml"
HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36","Accept-Language":"en-US,en;q=0.9"}

def date_from_url(url):
    # URL ends with: slug-ID-YYYY-MM-DD
    m = re.search(r"-(\d{4})-(\d{2})-(\d{2})$", url.rstrip("/"))
    if m:
        dt = datetime(int(m.group(1)),int(m.group(2)),int(m.group(3)),tzinfo=timezone.utc)
        return format_datetime(dt)
    return format_datetime(datetime.now(timezone.utc))

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.content.decode("utf-8","replace"), "lxml")

def extract(soup):
    articles, seen = [], set()
    for article in soup.find_all("article"):
        h2 = article.find("h2")
        if not h2: continue
        a = h2.find("a", href=True)
        if not a: continue
        href = a["href"]
        url = href if href.startswith("http") else urljoin(BASE_URL, href)
        if url in seen: continue
        title = a.get("title","") or a.get_text(strip=True)
        if not title or len(title) < 5: continue
        p = article.find("p")
        description = p.get_text(strip=True) if p else ""
        seen.add(url)
        articles.append({"title":title,"url":url,"description":description,"date":date_from_url(url)})
    return articles

def build_rss(articles):
    rss = ET.Element("rss", version="2.0"); rss.set("xmlns:atom","http://www.w3.org/2005/Atom")
    ch = ET.SubElement(rss,"channel")
    ET.SubElement(ch,"title").text="India Today Money - Insurance"
    ET.SubElement(ch,"link").text=NEWS_URL
    ET.SubElement(ch,"description").text="Insurance news from India Today Money"
    ET.SubElement(ch,"language").text="en"
    ET.SubElement(ch,"lastBuildDate").text=format_datetime(datetime.now(timezone.utc))
    al=ET.SubElement(ch,"atom:link"); al.set("href",NEWS_URL); al.set("rel","self"); al.set("type","application/rss+xml")
    for a in articles:
        it=ET.SubElement(ch,"item")
        ET.SubElement(it,"title").text=a["title"]
        ET.SubElement(it,"link").text=a["url"]
        ET.SubElement(it,"guid",isPermaLink="true").text=a["url"]
        ET.SubElement(it,"pubDate").text=a["date"]
        if a["description"]: ET.SubElement(it,"description").text=a["description"]
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
