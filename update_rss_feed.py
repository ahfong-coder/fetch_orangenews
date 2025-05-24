#!/usr/bin/env python3
"""
RSS Feed Updater for Orange News

This script fetches the latest articles from the Orange News website and updates
the RSS feed XML file. It can be run manually or scheduled to run periodically.

Usage:
  python update_rss_feed.py [--output OUTPUT_FILE]

Options:
  --output OUTPUT_FILE    Path to save the updated RSS feed XML [default: feed.xml]
"""

import argparse
import datetime
import html
import json
import os
import re
import sys
import time
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Required packages not found. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4"])
    import requests
    from bs4 import BeautifulSoup

# Configuration
BASE_URL = "https://www.orangenews.hk"
TOPIC_URL = "https://www.orangenews.hk/html/topic/index.html"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


def fetch_page(url):
    """Fetch HTML content from the given URL."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-HK,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None


def extract_articles(html_content):
    """Extract article information from HTML content."""
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    articles = []

    # Find all article links and extract information
    for link in soup.find_all('a'):
        # Skip links without text or with common navigation text
        if not link.text or link.text.strip() in ["查看更多", "下載APP", "登入", "首頁"]:
            continue

        # Get title
        title = link.text.strip()
        if len(title) < 5:  # Skip very short titles
            continue

        # Get link
        href = link.get('href')
        if not href or href == '#':
            continue

        # Normalize URL
        if not href.startswith('http'):
            href = urljoin(BASE_URL, href)

        # Look for date in parent elements
        date_text = None
        parent = link.parent
        search_depth = 0
        while parent and search_depth < 5:
            text = parent.get_text()
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
            if date_match:
                date_text = date_match.group(1)
                break
            parent = parent.parent
            search_depth += 1

        # If no date found, use current date
        if not date_text:
            date_text = datetime.datetime.now().strftime('%Y-%m-%d')

        # Get description (use title if no specific description found)
        description = title

        # Add article if it has all required fields
        if title and href and date_text:
            # Check if this URL is already in our list to avoid duplicates
            if not any(a['link'] == href for a in articles):
                articles.append({
                    'title': title,
                    'link': href,
                    'pubDate': date_text,
                    'description': description
                })

    return articles


def generate_rss_xml(articles):
    """Generate RSS XML content from article data."""
    rss_content = '<?xml version="1.0" encoding="UTF-8" ?>\n'
    rss_content += '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
    rss_content += '<channel>\n'
    rss_content += '  <title>Orange News - Commentaries</title>\n'
    rss_content += f'  <link>{BASE_URL}/html/topic/index.html</link>\n'
    rss_content += '  <description>Latest commentaries from Orange News HK</description>\n'
    rss_content += '  <language>zh-cn</language>\n'
    rss_content += '  <atom:link href="https://totrphbm.manus.space/feed.xml" rel="self" type="application/rss+xml" />\n'
    rss_content += f'  <lastBuildDate>{datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")}</lastBuildDate>\n'

    for article in articles:
        title = html.escape(article.get('title', 'No Title'))
        link = html.escape(article.get('link', '#'))
        description = html.escape(article.get('description', title))
        
        # Parse date and format for RSS
        pub_date_str = article.get('pubDate')
        if pub_date_str:
            try:
                dt_object = datetime.datetime.strptime(pub_date_str, "%Y-%m-%d")
                dt_object = dt_object.replace(hour=12, minute=0, second=0, tzinfo=datetime.timezone.utc)
                pub_date_rfc822 = dt_object.strftime("%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                pub_date_rfc822 = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
        else:
            pub_date_rfc822 = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")

        rss_content += '  <item>\n'
        rss_content += f'    <title>{title}</title>\n'
        rss_content += f'    <link>{link}</link>\n'
        rss_content += f'    <description>{description}</description>\n'
        rss_content += f'    <pubDate>{pub_date_rfc822}</pubDate>\n'
        rss_content += f'    <guid isPermaLink="true">{link}</guid>\n'
        rss_content += '  </item>\n'

    rss_content += '</channel>\n'
    rss_content += '</rss>\n'
    
    return rss_content


def main():
    """Main function to update the RSS feed."""
    parser = argparse.ArgumentParser(description='Update Orange News RSS feed')
    parser.add_argument('--output', default='feed.xml', help='Output file path for the RSS feed')
    args = parser.parse_args()
    
    print(f"Fetching articles from {TOPIC_URL}...")
    html_content = fetch_page(TOPIC_URL)
    
    if not html_content:
        print("Failed to fetch content. Exiting.")
        return 1
    
    print("Extracting articles...")
    articles = extract_articles(html_content)
    
    if not articles:
        print("No articles found. Exiting.")
        return 1
    
    print(f"Found {len(articles)} articles.")
    
    print("Generating RSS XML...")
    rss_content = generate_rss_xml(articles)
    
    print(f"Writing RSS feed to {args.output}...")
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(rss_content)
        print(f"RSS feed successfully updated at {args.output}")
    except IOError as e:
        print(f"Error writing RSS feed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
