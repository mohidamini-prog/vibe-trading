import yfinance as pd_yf
import pandas as pd
import numpy as np
import urllib.request
import json
import xml.etree.ElementTree as ET

def fetch_yahoo_news(ticker="AAPL"):
    """Fetch recent news for a ticker via Yahoo Finance RSS feed."""
    url = f"https://finance.yahoo.com/rss/headline?s={ticker}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        response = urllib.request.urlopen(req)
        root = ET.fromstring(response.read())
        items = root.findall('.//item')
        news = []
        for item in items[:5]:
            title = item.find('title').text
            pub_date = item.find('pubDate').text
            news.append({'title': title, 'date': pub_date})
        return news
    except Exception as e:
        return [{'title': f"Error fetching news: {e}", 'date': ''}]

print("--- NEWS API INTEGRATION TEST ---")
print("Latest AAPL News from Yahoo Finance:")
for n in fetch_yahoo_news("AAPL"):
    print(f"- [{n['date']}] {n['title']}")
