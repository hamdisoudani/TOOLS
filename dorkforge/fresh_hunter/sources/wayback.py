"""Wayback CDX — historical URL archive."""
import urllib.request
import urllib.parse
import re
import time


def harvest(dry_run=False, target_domains=None):
    """Query Wayback CDX for URLs matching pattern."""
    if dry_run:
        return []
    
    if target_domains is None:
        # Query for popular URL patterns
        patterns = [
            '*/*?id=*',
            '*/*?page=*',
            '*/*?cat=*',
            '*/*?pid=*',
        ]
    else:
        patterns = [f'{d}/*?id=*' for d in target_domains[:20]]
    
    urls = []
    for pattern in patterns:
        params = urllib.parse.urlencode({
            'url': pattern,
            'matchType': 'domain',
            'filter': 'mimetype:text/html',
            'limit': 5000,
            'output': 'json',
            'fl': 'original,timestamp',
        })
        url = f'http://web.archive.org/cdx/search/cdx?{params}'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            for row in data[1:]:  # Skip header
                original = row[0]
                # Filter for scripted ext
                if re.search(r'\.(php|asp|aspx|jsp|cfm|cgi)(\?|$)', original, re.I):
                    if not original.startswith('http'):
                        original = 'http://' + original
                    urls.append(original)
        except Exception as e:
            print(f'    Wayback error for {pattern}: {e}')
        time.sleep(1)  # Be polite
    
    return list(set(urls))
