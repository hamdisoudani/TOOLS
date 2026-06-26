"""URLhaus — malware URLs (hourly updated, free)."""
import urllib.request
import re


def harvest(dry_run=False):
    if dry_run:
        return []
    
    try:
        req = urllib.request.Request(
            'https://urlhaus.abuse.ch/downloads/text/',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            content = r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f'    URLhaus error: {e}')
        return []
    
    urls = []
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('http') and re.search(r'\.(php|asp|aspx|jsp|cfm|cgi)', line, re.I):
            # Skip comments / lines with #
            if line.startswith('#'):
                continue
            urls.append(line.split(' ')[0])
    
    return list(set(urls))
