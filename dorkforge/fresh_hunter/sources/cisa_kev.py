"""CISA KEV (Known Exploited Vulnerabilities) — daily fresh, no SQLi URLs but high quality."""
import urllib.request
import json
import re


def harvest(dry_run=False):
    if dry_run:
        return []
    
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f'    CISA KEV error: {e}')
        return []
    
    vulns = data.get('vulnerabilities', [])
    
    # Filter for SQLi-related CVEs (by description)
    sql_vulns = [v for v in vulns if any(
        kw in v.get('shortDescription', '').lower() 
        for kw in ['sql', 'injection', 'mysql', 'database']
    )]
    
    # Extract URLs from references via NVD lookup
    # (CISA doesn't have URLs, but the CVE IDs can be looked up in NVD)
    return []  # CISA itself doesn't have URLs — caller should cross-ref NVD
