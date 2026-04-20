#!/usr/bin/env python3
"""RSS Generator for beinsure.com - Africa and Latin America insurance news"""

import re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess; subprocess.check_call([sys.executable,"-m","pip","install","requests","beautifulsoup4","lxml"])
    import requests; from bs4 import BeautifulSoup

FEEDS = [
    {"url":"https://beinsure.com/n/africa-insurance-news/",    "title":"Beinsure - Africa Insurance News",    "output":"beinsure_africa.xml"},
    {"url":"https://beinsure.com/n/latin-america-insurance-news/","title":"Beinsure - Latin America Insurance News","output":"beinsure_latam.xml"},
]
HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.content.decode("utf-8","replace"), "lxml")

def extract(soup):
    articles, seen = [], set()
    for article in soup.find_all("article"):
        h = article.find("h2", class_="blog-entry-title")
        if not h: continue
        a = h.find("a", href=True)
        if not a: continue
        url = a["href"]
        if url in seen: continue
        seen.add(url)
        title = a.get_text(strip=True)
        desc_tag = article.find("div", class_=re.compile(r"excerpt|summary"))
        desc = desc_tag.get_text(strip=True) if desc_tag else ""
        # Try date from meta or time tag
        time_tag = article.find("time")
        date_str = time_tag.get("datetime","") if time_tag else ""
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z","+00:00")).astimezone(timezone.utc)
                pub_date = format_datetime(dt)
            except: pub_date = format_datetime(datetime.now(timezone.utc))
        else:
            pub_date = format_datetime(datetime.now(timezone.utc))
        articles.append({"title":title,"url":url,"description":desc,"date":pub_date})
    return articles

def build_rss(articles, title, feed_url):
    rss = ET.Element("rss", version="2.0"); rss.set("xmlns:atom","http://www.w3.org/2005/Atom")
    ch = ET.SubElement(rss,"channel")
    ET.SubElement(ch,"title").text=title
    ET.SubElement(ch,"link").text=feed_url
    ET.SubElement(ch,"description").text=title
    ET.SubElement(ch,"language").text="en"
    ET.SubElement(ch,"lastBuildDate").text=format_datetime(datetime.now(timezone.utc))
    al=ET.SubElement(ch,"atom:link"); al.set("href",feed_url); al.set("rel","self"); al.set("type","application/rss+xml")
    for a in articles:
        it=ET.SubElement(ch,"item")
        ET.SubElement(it,"title").text=a["title"]
        ET.SubElement(it,"link").text=a["url"]
        ET.SubElement(it,"guid",isPermaLink="true").text=a["url"]
        ET.SubElement(it,"pubDate").text=a["date"]
        if a["description"]: ET.SubElement(it,"description").text=a["description"]
    return rss

def main():
    for feed in FEEDS:
        print(f"Fetching {feed['url']}...")
        soup = fetch(feed["url"])
        articles = extract(soup)
        print(f"  Found {len(articles)} articles.")
        if not articles: continue
        tree = ET.ElementTree(build_rss(articles, feed["title"], feed["url"]))
        ET.indent(tree, space="  ")
        with open(feed["output"],"wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            tree.write(f, encoding="utf-8", xml_declaration=False)
        print(f"  Saved to {feed['output']}")
        for i,a in enumerate(articles[:3],1): print(f"    {i}. {a['title'][:70]}")

if __name__=="__main__": main()
