"""NVD CVE 2.0 — extract SQLi URLs from CVE references."""
import urllib.request
import json
import re
from datetime import datetime, timedelta

URL_PATTERN = re.compile(r'https?://(?:www\.)?([a-z0-9\-\.]+\.[a-z]{2,})/[^\s]*\.(php|asp|aspx|jsp|cfm|cgi)[^\s]*', re.I)


def harvest_sql(dry_run=False, days=30):
    """Get SQLi CVEs from last N days, extract URLs from references."""
    if dry_run:
        return []
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    url = (
        f"https://services.nvd.nist.gov/rest/json/cves/2.0"
        f"?keywordSearch=sql%20injection"
        f"&lastModStartDate={start_date.strftime('%Y-%m-%dT00:00:00.000')}"
        f"&lastModEndDate={end_date.strftime('%Y-%m-%dT00:00:00.000')}"
        f"&resultsPerPage=2000"
    )
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f'    NVD error: {e}')
        return []
    
    urls = []
    for v in data.get('vulnerabilities', []):
        cve = v.get('cve', {})
        desc = cve.get('descriptions', [{}])[0].get('value', '')
        refs = cve.get('references', [])
        
        # Check description for SQLi
        if 'sql injection' not in desc.lower() and 'sql-injection' not in desc.lower():
            continue
        
        for ref in refs:
            r_url = ref.get('url', '')
            matches = URL_PATTERN.findall(r_url)
            for domain, ext in matches:
                # Build full URL
                urls.append(f'https://{domain}/')
    
    return list(set(urls))
