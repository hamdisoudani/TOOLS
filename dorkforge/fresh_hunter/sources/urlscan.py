"""URLScan.io — community-driven live scans."""
import urllib.request
import json


def search_urlscan(query: str) -> list:
    url = f'https://urlscan.io/api/v1/search/?q={query}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except Exception as e:
        return []
    
    return [r.get('task', {}).get('url', '') for r in data.get('results', [])]


def harvest(dry_run=False):
    if dry_run:
        return []
    
    queries = [
        'task.url:"?id=" AND page.status:200',
        'task.url:php?id',
        'task.url:aspx?id',
        'task.url:jsp?id',
        'task.url:asp?id',
    ]
    
    urls = []
    for q in queries:
        urls.extend(search_urlscan(q))
    return list(set(u for u in urls if u))
