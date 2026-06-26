#!/usr/bin/env python3
"""
FRESH HUNTER v1.0 — The Ultimate URL Dumper
Combines ALL sources to find daily-fresh SQLi-suspect URLs.

Architecture:
  - Each source is a module in `sources/` directory
  - All return List[str] of URLs
  - Pipeline: harvest → normalize → dedup → score → output
  - Configurable via env vars + CLI flags
  - Cross-platform (Windows/Linux/Mac)
"""

import os
import sys
import json
import time
import argparse
import concurrent.futures as cf
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote_plus
from typing import List, Dict, Set, Tuple
from collections import defaultdict
import re

# Import all source modules
sys.path.insert(0, str(Path(__file__).parent))
from sources import bing, google, yandex, duckduckgo, fofa, quake, censys, shodan, zoomeye
from sources import nvd, cisa_kev, exploitdb, github_advisories, osv
from sources import urlscan, openbugbounty, phishtank, urlhaus, otx
from sources import cms_wp, cms_joomla, cms_drupal, cms_forum
from sources import wayback, common_crawl
from sources import self_learn

# === CONFIG ===

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT = 30
SCRIPTED_EXTS = ('.php', '.asp', '.aspx', '.jsp', '.cfm', '.cgi', '.do', '.action')

# === URL SCORER ===

INJECTABLE_PARAMS = {
    'id', 'page', 'cat', 'pid', 'tid', 'cid', 'nid', 'uid',
    'article', 'product', 'item', 'user', 'news', 'post',
    'forum', 'thread', 'topic', 'view', 'show', 'display',
    'sort', 'order', 'filter', 'search', 'q', 'lang', 'file',
    'download', 'doc', 'img', 'image', 'gallery', 'photo',
    'video', 'book', 'type', 'act', 'cmd', 'exec', 'do',
    'action', 'page_id', 'post_id', 'user_id', 'news_id',
    'category_id', 'product_id', 'order_id', 'pid', 'nid',
    'invoice_id', 'gallery_id', 'image_id', 'pic_id',
    'customer_id', 'member_id', 'account_id', 'doc_id',
    'blog_id', 'poll_id', 'quiz_id', 'survey_id', 'cat_id',
}

HIGH_VALUE_DOMAINS = {'.gov', '.edu', '.mil', '.ac.', '.gouv'}
ASIA_DOMAINS = {'.cn', '.kr', '.jp', '.in', '.pk', '.tw', '.hk', '.sg', '.my', '.th', '.vn', '.ph', '.id', '.mo'}

# Drop list — never SQLi targets
SPAM_DOMAINS = {
    'w3schools.com', 'w3school.com.cn', 'google.com', 'youtube.com',
    'github.com', 'stackoverflow.com', 'stackexchange.com', 'microsoft.com',
    'bing.com', 'yandex.com', 'yandex.net', 'yastatic.net', 'apple.com',
    'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
    'amazon.com', 'amazonaws.com', 'cloudflare.com', 'cloudfront.net',
    'baidu.com', 'qq.com', 'taobao.com', 'weibo.com', 'mozilla.org',
    'wikipedia.org', 'reddit.com', 'tiktok.com',
    # Examples (CVE demo)
    'bugzilla.org', 'mantisbt.org',
}


def normalize_url(url: str) -> str:
    """Normalize URL: HTML entities, trailing junk."""
    url = url.strip()
    url = url.replace('&amp;', '&')
    # Strip trailing " - Title" from search snippets
    url = url.split(' - ')[0].strip() if ' - ' in url and url.startswith('http') else url
    # Remove session/tracking params
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query = {k: v for k, v in query.items() if not k.lower().startswith(('utm_', 'fb_', 'gclid', 'msclkid', 'sessionid', 'phpsessid'))}
    from urllib.parse import urlencode, urlunparse
    new_query = urlencode(query, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ''))


def has_scripted_ext(url: str) -> bool:
    """URL must have .php/.asp/... in PATH (not query)."""
    try:
        url_lower = url.lower()
        path = urlparse(url_lower).path
        for ext in SCRIPTED_EXTS:
            if path.endswith(ext) or ext + '/' in path:
                return True
            if ext + '?' in url_lower or ext + '&' in url_lower:
                # Check it's not in a query value
                if path.endswith(ext):
                    return True
        return False
    except Exception:
        return False


def has_injectable_param(url: str) -> bool:
    """URL has common SQLi-vulnerable param."""
    try:
        query = urlparse(url.lower()).query
        params = set()
        for kv in query.split('&'):
            if '=' in kv:
                params.add(kv.split('=')[0])
        return bool(params & INJECTABLE_PARAMS)
    except Exception:
        return False


def score_url(url: str, source: str = '', discovered_at: datetime = None) -> int:
    """Score URL by SQLi-suspicion (higher = better target)."""
    score = 0
    try:
        url_lower = url.lower()
        parsed = urlparse(url_lower)
        host = parsed.netloc
        path = parsed.path
        query = parsed.query
        
        # Extension (must have)
        if has_scripted_ext(url):
            score += 30
        
        # Numeric/ID param (must have)
        if has_injectable_param(url):
            score += 25
        
        # Session/login/admin in URL = higher chance
        if any(x in path for x in ['/admin', '/login', '/user', '/account', '/member']):
            score += 15
        
        # High-value TLD
        for tld in HIGH_VALUE_DOMAINS:
            if host.endswith(tld):
                score += 10
                break
        
        # Asia = weaker security
        for tld in ASIA_DOMAINS:
            if host.endswith(tld):
                score += 8
                break
        
        # Freshness bonus
        if discovered_at:
            age_hours = (datetime.now() - discovered_at).total_seconds() / 3600
            if age_hours < 24:
                score += 20
            elif age_hours < 168:  # 1 week
                score += 10
            elif age_hours < 720:  # 30 days
                score += 5
        
        # Source trust
        source_scores = {
            'cisa_kev': 50, 'nvd': 40, 'github_advisories': 35,
            'urlscan': 15, 'shodan': 12, 'censys': 12, 'fofa': 12, 'quake': 12,
            'openbugbounty': 20, 'phishtank': 8, 'urlhaus': 5,
            'bing': 5, 'google': 8, 'yandex': 5, 'duckduckgo': 3,
            'wayback': 1, 'common_crawl': 1, 'cms_wp': 25, 'cms_joomla': 25,
        }
        score += source_scores.get(source, 0)
        
    except Exception:
        pass
    return score


def filter_pipeline(urls: List[Tuple[str, str, datetime]]) -> Dict:
    """Full filter: normalize → dedup → score → tier."""
    
    # Step 1: Normalize
    print(f'[*] Step 1: Normalize ({len(urls)} raw)...')
    normalized = []
    for url, source, ts in urls:
        try:
            u = normalize_url(url)
            if u.startswith('http'):
                normalized.append((u, source, ts))
        except Exception:
            pass
    
    # Step 2: Drop spam domains
    print(f'[*] Step 2: Drop spam domains...')
    filtered = []
    dropped_spam = 0
    for url, source, ts in normalized:
        host = urlparse(url).netloc
        if any(host == d or host.endswith('.' + d) for d in SPAM_DOMAINS):
            dropped_spam += 1
            continue
        filtered.append((url, source, ts))
    print(f'    Dropped {dropped_spam} spam domains')
    
    # Step 3: Dedup by host+path+query
    print(f'[*] Step 3: Dedup...')
    seen = set()
    deduped = []
    for url, source, ts in filtered:
        key = urlparse(url).netloc + urlparse(url).path + urlparse(url).query
        if key in seen:
            continue
        seen.add(key)
        deduped.append((url, source, ts))
    print(f'    {len(deduped)} unique')
    
    # Step 4: Score
    print(f'[*] Step 4: Score...')
    scored = [(url, source, ts, score_url(url, source, ts)) for url, source, ts in deduped]
    scored.sort(key=lambda x: -x[3])
    
    # Step 5: Tier classification
    tiers = defaultdict(list)
    for url, source, ts, score in scored:
        if not has_scripted_ext(url):
            tier = 'tier_other'
        elif not has_injectable_param(url):
            tier = 'tier_other'
        else:
            # TLD-based subdivision
            host = urlparse(url).netloc
            if any(host.endswith(t) for t in HIGH_VALUE_DOMAINS):
                tier = 'tier_edu_gov'
            elif any(host.endswith(t) for t in ASIA_DOMAINS):
                tier = 'tier_asia'
            else:
                tier = 'tier_global'
        tiers[tier].append((url, source, ts, score))
    
    return {
        'scored': scored,
        'tiers': dict(tiers),
        'stats': {
            'raw': len(urls),
            'normalized': len(normalized),
            'after_spam': len(filtered),
            'unique': len(deduped),
            'by_tier': {k: len(v) for k, v in tiers.items()},
        }
    }


def output_results(result: Dict, out_dir: str):
    """Write all output files."""
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # All URLs (sorted by score)
    with open(f'{out_dir}/urls_all_{ts}.txt', 'w') as f:
        for url, src, ts_discovered, score in result['scored']:
            f.write(f'{score:4d} | {url}\n')
    
    # Top 10K by score
    with open(f'{out_dir}/urls_top_{ts}.txt', 'w') as f:
        for url, src, ts_discovered, score in result['scored'][:10000]:
            f.write(f'{url}\n')
    
    # Tier-specific
    for tier_name, urls in result['tiers'].items():
        with open(f'{out_dir}/urls_{tier_name}_{ts}.txt', 'w') as f:
            for url, src, ts_discovered, score in urls:
                f.write(f'{url}\n')
    
    # Stats
    with open(f'{out_dir}/stats_{ts}.json', 'w') as f:
        json.dump(result['stats'], f, indent=2)
    
    # Source breakdown
    source_counts = defaultdict(int)
    for url, src, ts, score in result['scored']:
        source_counts[src] += 1
    with open(f'{out_dir}/source_breakdown_{ts}.json', 'w') as f:
        json.dump(dict(source_counts), f, indent=2, sort_keys=True)
    
    return ts


def main():
    parser = argparse.ArgumentParser(description='Fresh Hunter v1.0 — Ultimate URL Dumper')
    parser.add_argument('--out', default='./fresh_harvest', help='Output directory')
    parser.add_argument('--bing-dorks', type=int, default=300, help='Number of Bing dorks')
    parser.add_argument('--google-dorks', type=int, default=200, help='Number of Google dorks')
    parser.add_argument('--yandex-dorks', type=int, default=100, help='Number of Yandex dorks')
    parser.add_argument('--pages', type=int, default=3, help='Pages per dork')
    parser.add_argument('--workers', type=int, default=10, help='Concurrent workers')
    parser.add_argument('--enable-fofa', action='store_true', help='Enable FOFA (needs API key)')
    parser.add_argument('--enable-quake', action='store_true', help='Enable Quake (needs auth)')
    parser.add_argument('--enable-censys', action='store_true', help='Enable Censys (needs auth)')
    parser.add_argument('--enable-shodan', action='store_true', help='Enable Shodan (needs key)')
    parser.add_argument('--enable-nvd', action='store_true', help='Enable NVD CVE 2.0')
    parser.add_argument('--enable-cisa', action='store_true', help='Enable CISA KEV')
    parser.add_argument('--enable-wayback', action='store_true', help='Enable Wayback CDX')
    parser.add_argument('--enable-urlscan', action='store_true', help='Enable URLScan.io')
    parser.add_argument('--enable-urlhaus', action='store_true', help='Enable URLhaus')
    parser.add_argument('--enable-phishtank', action='store_true', help='Enable PhishTank')
    parser.add_argument('--enable-cms', action='store_true', help='Enable CMS targeting')
    parser.add_argument('--enable-self-learn', action='store_true', help='Enable self-learning')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t actually fetch')
    parser.add_argument('--resume-from', type=str, help='Resume from checkpoint')
    parser.add_argument('--min-score', type=int, default=30, help='Min score to keep')
    args = parser.parse_args()
    
    print('=' * 70)
    print('FRESH HUNTER v1.0 — The Ultimate URL Dumper')
    print(f'Time: {datetime.now().isoformat()}')
    print(f'Output: {args.out}')
    print('=' * 70)
    
    all_urls = []  # List of (url, source, timestamp)
    
    # === LAYER 1: SEARCH ENGINES ===
    if args.bing_dorks > 0:
        print(f'\n[L1] Bing: {args.bing_dorks} dorks × {args.pages} pages × {args.workers} workers...')
        urls = bing.harvest(dorks_count=args.bing_dorks, pages=args.pages, workers=args.workers, dry_run=args.dry_run)
        all_urls.extend([(u, 'bing', datetime.now()) for u in urls])
        print(f'    Got {len(urls)} URLs')
    
    if args.google_dorks > 0:
        print(f'\n[L1] Google: {args.google_dorks} dorks × {args.pages} pages × {args.workers} workers...')
        urls = google.harvest(dorks_count=args.google_dorks, pages=args.pages, workers=args.workers, dry_run=args.dry_run)
        all_urls.extend([(u, 'google', datetime.now()) for u in urls])
        print(f'    Got {len(urls)} URLs')
    
    if args.yandex_dorks > 0:
        print(f'\n[L1] Yandex: {args.yandex_dorks} dorks × {args.pages} pages × {args.workers} workers...')
        urls = yandex.harvest(dorks_count=args.yandex_dorks, pages=args.pages, workers=args.workers, dry_run=args.dry_run)
        all_urls.extend([(u, 'yandex', datetime.now()) for u in urls])
        print(f'    Got {len(urls)} URLs')
    
    # === LAYER 2: SCANNER APIs ===
    if args.enable_fofa:
        print('\n[L2] FOFA...')
        urls = fofa.harvest(dry_run=args.dry_run)
        all_urls.extend([(u, 'fofa', datetime.now()) for u in urls])
        print(f'    Got {len(urls)} URLs')
    
    if args.enable_quake:
        print('\n[L2] Quake...')
        urls = quake.harvest(dry_run=args.dry_run)
        all_urls.extend([(u, 'quake', datetime.now()) for u in urls])
    
    if args.enable_censys:
        print('\n[L2] Censys...')
        urls = censys.harvest(dry_run=args.dry_run)
        all_urls.extend([(u, 'censys', datetime.now()) for u in urls])
    
    if args.enable_shodan:
        print('\n[L2] Shodan...')
        urls = shodan.harvest(dry_run=args.dry_run)
        all_urls.extend([(u, 'shodan', datetime.now()) for u in urls])
    
    # === LAYER 3: VULN FEEDS ===
    if args.enable_nvd:
        print('\n[L3] NVD CVE 2.0 (SQLi CVEs last 30d)...')
        urls = nvd.harvest_sql(dry_run=args.dry_run)
        all_urls.extend([(u, 'nvd', datetime.now()) for u in urls])
        print(f'    Got {len(urls)} URLs')
    
    if args.enable_cisa:
        print('\n[L3] CISA KEV (actively exploited)...')
        urls = cisa_kev.harvest(dry_run=args.dry_run)
        all_urls.extend([(u, 'cisa_kev', datetime.now()) for u in urls])
        print(f'    Got {len(urls)} URLs')
    
    # === LAYER 4: COMMUNITY/CROWD ===
    if args.enable_urlscan:
        print('\n[L4] URLScan.io (live scans)...')
        urls = urlscan.harvest(dry_run=args.dry_run)
        all_urls.extend([(u, 'urlscan', datetime.now()) for u in urls])
    
    if args.enable_urlhaus:
        print('\n[L4] URLhaus (malware hourly)...')
        urls = urlhaus.harvest(dry_run=args.dry_run)
        all_urls.extend([(u, 'urlhaus', datetime.now()) for u in urls])
        print(f'    Got {len(urls)} URLs')
    
    if args.enable_phishtank:
        print('\n[L4] PhishTank (phishing hourly)...')
        urls = phishtank.harvest(dry_run=args.dry_run)
        all_urls.extend([(u, 'phishtank', datetime.now()) for u in urls])
    
    # === LAYER 5: CMS TARGETING ===
    if args.enable_cms:
        print('\n[L5] CMS-specific targeting...')
        for mod in [cms_wp, cms_joomla, cms_drupal, cms_forum]:
            urls = mod.harvest(dry_run=args.dry_run)
            all_urls.extend([(u, mod.__name__, datetime.now()) for u in urls])
            print(f'    {mod.__name__}: {len(urls)} URLs')
    
    # === LAYER 6: ARCHIVES ===
    if args.enable_wayback:
        print('\n[L6] Wayback CDX...')
        urls = wayback.harvest(dry_run=args.dry_run)
        all_urls.extend([(u, 'wayback', datetime.now()) for u in urls])
        print(f'    Got {len(urls)} URLs')
    
    # === LAYER 7: SELF-LEARNING ===
    if args.enable_self_learn:
        print('\n[L7] Self-learning (yesterday\'s URLs)...')
        urls = self_learn.harvest(args.out, dry_run=args.dry_run)
        all_urls.extend([(u, 'self_learn', datetime.now()) for u in urls])
    
    # === PIPELINE ===
    print(f'\n[*] Total raw URLs: {len(all_urls)}')
    result = filter_pipeline(all_urls)
    print(f'\n[+] Stats: {result["stats"]}')
    
    ts = output_results(result, args.out)
    print(f'\n[+] Saved outputs to {args.out}/ with timestamp {ts}')
    print(f'[+] Run: type {args.out}\\urls_top_{ts}.txt | head -20')
    print(f'[+] To see top scoring URLs')


if __name__ == '__main__':
    main()
