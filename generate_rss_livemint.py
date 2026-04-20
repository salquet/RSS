#!/usr/bin/env python3
"""RSS Generator for livemint.com/insurance/news"""

import re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess; subprocess.check_call([sys.executable,"-m","pip","install","requests","beautifulsoup4","lxml"])
    import requests; from bs4 import BeautifulSoup

NEWS_URL = "https://www.livemint.com/insurance/news"
OUTPUT_FILE = "livemint_insurance.xml"
HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36","Accept-Language":"en-US,en;q=0.9"}

MONTHS = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}

def parse_date(raw):
    # e.g. "18 Apr 2026" or "22 Nov 2025"
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", raw)
    if m:
        month = MONTHS.get(m.group(2).lower())
        if month:
            dt = datetime(int(m.group(3)), month, int(m.group(1)), tzinfo=timezone.utc)
            return format_datetime(dt)
    return format_datetime(datetime.now(timezone.utc))

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.content.decode("utf-8","replace"), "lxml")

def extract(soup):
    articles, seen = [], set()
    for h2 in soup.find_all("h2"):
        a = h2.find("a", href=lambda h: h and "livemint.com/insurance" in h)
        if not a: continue
        url = a["href"].split("?")[0]
        if url in seen: continue
        title = a.get_text(strip=True)
        if not title: continue
        # Date: find nearby span/p with date pattern
        parent = h2.find_parent()
        raw_date = ""
        if parent:
            for tag in parent.find_all(["span","p","time"]):
                txt = tag.get_text(strip=True)
                if re.search(r"\d{1,2}\s+[A-Za-z]{3}\s+\d{4}", txt):
                    raw_date = txt; break
        seen.add(url)
        articles.append({"title":title,"url":url,"date":parse_date(raw_date)})
    return articles

def build_rss(articles):
    rss = ET.Element("rss", version="2.0"); rss.set("xmlns:atom","http://www.w3.org/2005/Atom")
    ch = ET.SubElement(rss,"channel")
    ET.SubElement(ch,"title").text="Livemint - Insurance News"
    ET.SubElement(ch,"link").text=NEWS_URL
    ET.SubElement(ch,"description").text="Insurance news from Livemint India"
    ET.SubElement(ch,"language").text="en"
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
    for i,a in enumerate(articles[:5],1): print(f"  {i}. {a['title'][:70]}".encode('ascii','replace').decode())

if __name__=="__main__": main()
