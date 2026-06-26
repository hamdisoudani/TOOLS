"""
FRESH DAILY URLS PIPELINE
Runs from YOUR Windows machine (residential IP)
Bypasses datacenter CAPTCHA/blocks
Combines multiple fresh sources to get 5K-20K SQLi-suspect URLs/day
"""

import requests
import json
import re
import time
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os
import sys

OUTPUT_DIR = "C:\\Users\\<user>\\dorkforge\\fresh_harvest"
os.makedirs(OUTPUT_DIR, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT = 30


def bing_search(query, pages=10, engine='bing'):
    """Bing search via residential IP. Returns list of URLs."""
    results = []
    session = requests.Session()
    session.headers.update({'User-Agent': UA})
    
    for page in range(pages):
        # Bing first= parameter
        first = page * 10 + 1
        url = f"https://www.bing.com/search?q={quote_plus(query)}&count=20&first={first}"
        try:
            r = session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            # Extract URLs from Bing HTML
            urls = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>', r.text)
            for u in urls:
                # Skip Bing/CDN links
                if any(x in u for x in ['bing.com', 'microsoft.com', 'msn.com', 'live.com', 'w3.org', 'cloudflare.com', 'mozilla.org']):
                    continue
                results.append(u)
        except Exception as e:
            print(f'  Page {page+1} error: {e}')
        time.sleep(0.5)
    
    # Dedup
    return list(set(results))


def google_search(query, pages=10):
    """Google search via residential IP. Returns list of URLs."""
    results = []
    session = requests.Session()
    session.headers.update({'User-Agent': UA})
    
    for page in range(pages):
        start = page * 10
        url = f"https://www.google.com/search?q={quote_plus(query)}&num=20&start={start}"
        try:
            r = session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            # Extract URLs from Google HTML
            urls = re.findall(r'/url\?q=(https?://[^&"]+)', r.text)
            for u in urls:
                u = requests.utils.unquote(u)
                if any(x in u for x in ['google.com', 'gstatic.com', 'youtube.com']):
                    continue
                results.append(u)
        except Exception as e:
            print(f'  Page {page+1} error: {e}')
        time.sleep(0.5)
    
    return list(set(results))


def yandex_search(query, pages=5):
    """Yandex search (often works from residential IPs)."""
    results = []
    session = requests.Session()
    session.headers.update({'User-Agent': UA})
    
    for page in range(pages):
        p = page
        url = f"https://yandex.com/search/?text={quote_plus(query)}&p={p}"
        try:
            r = session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            urls = re.findall(r'href="(https?://[^"]+)"[^>]*>', r.text)
            for u in urls:
                if any(x in u for x in ['yandex.com', 'yandex.net', 'yastatic.net']):
                    continue
                results.append(u)
        except Exception as e:
            print(f'  Page {page+1} error: {e}')
        time.sleep(1)
    
    return list(set(results))


def has_scripted_ext(url):
    """URL must contain .php/.asp/.aspx/.jsp extension in path."""
    url_lower = url.lower().replace('&amp;', '&')
    path = url_lower.split('?')[0]
    for ext in ['.php', '.asp', '.aspx', '.jsp', '.cfm', '.cgi']:
        if path.endswith(ext) or ext + '?' in path or ext + '&' in path or ext + '/' in path:
            return True
    return False


def has_injectable_param(url):
    """URL must have a common SQLi-vulnerable param."""
    url_lower = url.lower()
    patterns = [
        'id=', 'page=', 'cat=', 'pid=', 'tid=', 'cid=', 'nid=',
        'article=', 'product=', 'item=', 'user=', 'news=',
        'forum=', 'thread=', 'topic=', 'view=', 'show=',
        'display=', 'sort=', 'order=', 'filter=', 'search=',
        'q=', 'lang=', 'file=', 'download=', 'doc=', 'img=',
        'image=', 'gallery=', 'photo=', 'video=', 'book=',
        'type=', 'act=', 'cmd=', 'exec=', 'do=', 'action=',
        'page_id=', 'post_id=', 'user_id=', 'news_id=',
        'category_id=', 'product_id=', 'order_id=',
    ]
    return any(p in url_lower for p in patterns)


def gen_volume_dorks():
    """Generate Bing-compatible volume dorks."""
    params = ['id', 'page', 'cat', 'pid', 'tid', 'cid', 'nid', 'article', 'product',
              'item', 'user', 'news', 'forum', 'thread', 'topic', 'view', 'show',
              'display', 'sort', 'order', 'filter', 'search', 'q', 'lang', 'file',
              'download', 'doc', 'img', 'image', 'gallery', 'photo', 'video', 'book',
              'type', 'act', 'cmd', 'exec', 'do', 'action', 'page_id', 'post_id',
              'user_id', 'news_id', 'category_id', 'product_id', 'order_id']
    
    extensions = ['php', 'asp', 'aspx', 'jsp']
    topics = ['', 'login', 'admin', 'product', 'shop', 'news', 'article', 'blog',
              'forum', 'view', 'profile', 'search', 'download', 'gallery']
    
    dorks = []
    
    # Layer 1: simple param x ext
    for ext in extensions:
        for param in params[:30]:
            dorks.append(f'inurl:"?{param}=" ext:{ext}')
    
    # Layer 2: contains: ext + param (most effective from prior tests)
    for ext in extensions:
        for param in params[:20]:
            dorks.append(f'contains:{ext} inurl:"?{param}="')
    
    # Layer 3: ext + topic + param (some yield unique)
    for ext in extensions[:2]:
        for topic in topics[:8]:
            if topic:
                for param in params[:8]:
                    dorks.append(f'ext:{ext} {topic} inurl:"?{param}="')
    
    # Layer 4: paths
    for path in ['forum', 'blog', 'shop', 'product', 'news', 'gallery', 'admin']:
        for ext in extensions[:2]:
            dorks.append(f'inurl:{path} ext:{ext}')
    
    # Layer 5: action paths (less common, more unique)
    for action in ['detail', 'view', 'show', 'display', 'edit', 'delete', 'update']:
        for ext in extensions[:2]:
            dorks.append(f'inurl:{action} ext:{ext}')
    
    return dorks


def main():
    print('=' * 70)
    print('FRESH DAILY URLS PIPELINE')
    print(f'Time: {datetime.now().isoformat()}')
    print('=' * 70)
    
    dorks = gen_volume_dorks()
    print(f'\n[*] Generated {len(dorks)} volume dorks')
    
    all_urls = set()
    
    print('\n[1/3] Running Bing search (uses residential IP)...')
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {}
        for i, dork in enumerate(dorks[:300]):  # 300 dorks first pass
            futures[ex.submit(bing_search, dork, 2)] = dork
        
        for i, fut in enumerate(as_completed(futures)):
            dork = futures[fut]
            try:
                urls = fut.result()
                # Filter immediately
                filtered = [u for u in urls if has_scripted_ext(u) and has_injectable_param(u)]
                for u in filtered:
                    all_urls.add(u)
                if i % 20 == 0:
                    print(f'  [{i+1}/{len(futures)}] {dork[:50]:50} → {len(filtered)} URLs (total: {len(all_urls)})')
            except Exception as e:
                pass
    
    print(f'\n[+] Bing found {len(all_urls)} URLs')
    
    # Save
    out_file = os.path.join(OUTPUT_DIR, f'fresh_bing_{datetime.now().strftime("%Y%m%d_%H%M")}.txt')
    with open(out_file, 'w') as f:
        for u in sorted(all_urls):
            f.write(u + '\n')
    print(f'[+] Saved: {out_file}')
    print(f'[+] Total: {len(all_urls)} unique URLs')


if __name__ == '__main__':
    main()
