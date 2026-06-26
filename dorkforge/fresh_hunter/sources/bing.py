"""Bing search — needs residential IP for full results."""
import os, time, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Volume dorks (all param x ext x topic combos)
PARAMS = ['id', 'page', 'cat', 'pid', 'tid', 'cid', 'nid', 'uid', 'article', 'product',
          'item', 'user', 'news', 'post', 'forum', 'thread', 'topic', 'view', 'show',
          'display', 'sort', 'order', 'filter', 'search', 'q', 'lang', 'file', 'download',
          'doc', 'img', 'image', 'gallery', 'photo', 'video', 'book', 'type', 'act',
          'cmd', 'exec', 'do', 'action', 'page_id', 'post_id', 'user_id', 'news_id',
          'category_id', 'product_id', 'order_id', 'invoice_id', 'gallery_id',
          'image_id', 'pic_id', 'customer_id', 'member_id', 'account_id']

EXTS = ['php', 'asp', 'aspx', 'jsp']
TOPICS = ['', 'login', 'admin', 'product', 'shop', 'news', 'article', 'blog', 'forum',
          'view', 'profile', 'search', 'download', 'gallery', 'book', 'course',
          'event', 'ticket', 'reservation', 'appointment']

PATHS = ['forum', 'blog', 'shop', 'product', 'news', 'gallery', 'admin', 'login',
         'user', 'account', 'download', 'view', 'article', 'page', 'detail']


def gen_dorks(count: int = 300) -> list:
    dorks = []
    # Layer 1: param x ext (basic)
    for ext in EXTS:
        for p in PARAMS[:30]:
            dorks.append(f'inurl:"?{p}=" ext:{ext}')
    # Layer 2: contains: ext + param (most effective)
    for ext in EXTS:
        for p in PARAMS[:20]:
            dorks.append(f'contains:{ext} inurl:"?{p}="')
    # Layer 3: ext + topic + param
    for ext in EXTS[:2]:
        for t in TOPICS[:8]:
            if t:
                for p in PARAMS[:8]:
                    dorks.append(f'ext:{ext} {t} inurl:"?{p}="')
    # Layer 4: path-based
    for path in PATHS:
        for ext in EXTS[:2]:
            dorks.append(f'inurl:{path} ext:{ext}')
    return dorks[:count]


def search_one(query: str, pages: int = 3, session=None) -> list:
    if session is None:
        session = requests.Session()
        session.headers.update({'User-Agent': UA})
    urls = []
    for page in range(pages):
        first = page * 20 + 1
        url = f'https://www.bing.com/search?q={quote_plus(query)}&count=20&first={first}'
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            # Extract URLs from Bing HTML (varied selectors)
            import re
            found = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>', r.text)
            for u in found:
                if any(x in u for x in ['bing.com', 'microsoft.com', 'msn.com', 'live.com', 'w3.org', 'mozilla.org', 'google.com']):
                    continue
                urls.append(u)
        except Exception as e:
            pass
        time.sleep(0.5)
    return list(set(urls))


def harvest(dorks_count=300, pages=3, workers=10, dry_run=False):
    if dry_run:
        return []
    dorks = gen_dorks(dorks_count)
    all_urls = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(search_one, d, pages): d for d in dorks}
        for i, fut in enumerate(as_completed(futures)):
            try:
                urls = fut.result()
                all_urls.extend(urls)
                if i % 20 == 0:
                    print(f'    Bing [{i+1}/{len(dorks)}] total: {len(all_urls)}')
            except Exception:
                pass
    return all_urls
