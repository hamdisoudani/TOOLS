"""Yandex search."""
import os, time, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus
import re

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
from .bing import gen_dorks


def search_one(query: str, pages: int = 3, session=None) -> list:
    if session is None:
        session = requests.Session()
        session.headers.update({'User-Agent': UA})
    urls = []
    for page in range(pages):
        p = page
        url = f'https://yandex.com/search/?text={quote_plus(query)}&p={p}'
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            found = re.findall(r'href="(https?://[^"]+)"', r.text)
            for u in found:
                if any(x in u for x in ['yandex.com', 'yandex.net', 'yastatic.net']):
                    continue
                urls.append(u)
        except Exception:
            pass
        time.sleep(1)
    return list(set(urls))


def harvest(dorks_count=100, pages=3, workers=5, dry_run=False):
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
            except Exception:
                pass
    return all_urls
