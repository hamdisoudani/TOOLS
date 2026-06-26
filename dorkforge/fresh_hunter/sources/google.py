"""Google search — needs residential IP."""
import os, time, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus
import re

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Reuse Bing dorks (Google accepts same syntax)
from .bing import gen_dorks


def search_one(query: str, pages: int = 3, session=None) -> list:
    if session is None:
        session = requests.Session()
        session.headers.update({'User-Agent': UA})
    urls = []
    for page in range(pages):
        start = page * 20
        url = f'https://www.google.com/search?q={quote_plus(query)}&num=20&start={start}'
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            # Google uses /url?q=URL&... for outbound
            found = re.findall(r'/url\?q=(https?://[^&"]+)', r.text)
            for u in found:
                from urllib.parse import unquote
                u = unquote(u)
                if any(x in u for x in ['google.com', 'gstatic.com', 'youtube.com', 'schema.org']):
                    continue
                urls.append(u)
        except Exception:
            pass
        time.sleep(0.5)
    return list(set(urls))


def harvest(dorks_count=200, pages=3, workers=8, dry_run=False):
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
