#!/usr/bin/env python3
"""
DorkForge vFinal — Multi-pass URL filter for SQLiDumper export.

Strategy:
PASS 1 — Smart filter (strip SERP, spam, shorteners, etc.)
PASS 2 — Dork pollution filter (URLs whose param values contain dork operators)
PASS 3 — Diversity filter (URLs appearing in too many dorks = spam signal)
PASS 4 — SQLi param filter (URLs with known SQLi-prone params)
PASS 5 — Extension tier classification:
  - SCRIPTED (php/asp/aspx/jsp/cfm/cgi): highest priority targets
  - CMS-like (libguides, archiveofourown with ?id=): medium
  - Other (?id= on news sites, etc.): low priority

OUTPUT:
- harvest_final.txt — full list, all variations, dedup by URL
- harvest_final_unique.txt — one URL per (host, path) with most params
- harvest_final_grouped.txt — sorted by host for SQLiDumper crawling
- harvest_final_stats.json — per-host breakdown
"""
import sys
import re
import math
import json
import argparse
from pathlib import Path
from urllib.parse import urlparse, unquote
from collections import defaultdict, Counter

from format_v2 import (
    smart_filter, has_sqli_param,
    DORK_SPAM, SEARCH_ENGINES
)
from format_v3 import has_dork_pollution

# Script extensions — high-confidence SQLi targets
SCRIPT_EXTS = ('.php', '.asp', '.aspx', '.jsp', '.cfm', '.cgi', '.pl', '.py', '.rb', '.do', '.action')

# CMS patterns — known SQLi-prone CMS URLs
CMS_PATTERNS = [
    r'/wp-content/',
    r'/wp-includes/',
    r'/wp-json/',
    r'/administrator/',
    r'/com_content/',
    r'/com_virtuemart/',
    r'/index\.php\?option=com_',
    r'/forumdisplay\.php',
    r'/viewtopic\.php',
    r'/viewforum\.php',
    r'/showthread\.php',
    r'/node/',
    r'/taxonomy/term',
    r'/profile\.php',
    r'/member\.php',
    r'/blog/',
    r'/article/',
    r'/news/',
    r'/product/',
    r'/item/',
]

CMS_REGEX = re.compile('|'.join(CMS_PATTERNS), re.I)


def classify_url(url: str) -> str:
    """Classify URL into tier: SCRIPTED / CMS / OTHER"""
    p = urlparse(url)
    path_lower = p.path.lower()
    if any(path_lower.endswith(ext) for ext in SCRIPT_EXTS):
        return "SCRIPTED"
    if CMS_REGEX.search(url):
        return "CMS"
    return "OTHER"


def parse_dorkforge_txt(path: str):
    url_to_dorks = defaultdict(set)
    current_dork = None
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line.startswith('## dork:'):
                current_dork = line.replace('## dork:', '').strip()
            elif line.startswith(('http://', 'https://')):
                line = line.replace('&amp;', '&')
                if current_dork:
                    url_to_dorks[line].add(current_dork)
    return url_to_dorks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True)
    ap.add_argument("-o", "--output", required=True, help="final URL list")
    ap.add_argument("--max-dorks", type=int, default=15,
                    help="max dork count to keep (default 15)")
    args = ap.parse_args()

    url_to_dorks = parse_dorkforge_txt(args.input)
    total_raw = sum(len(d) for d in url_to_dorks.values())
    print(f"[+] Parsed {total_raw} raw URLs ({len(url_to_dorks)} unique)")

    # Apply filters
    by_tier = {"SCRIPTED": [], "CMS": [], "OTHER": []}
    filter_stats = Counter()

    for url, dorks in url_to_dorks.items():
        # Smart filter
        keep, reason = smart_filter(url)
        if not keep:
            filter_stats[reason] += 1
            continue

        # Dork pollution filter
        if has_dork_pollution(url):
            filter_stats["dork_pollution"] += 1
            continue

        # Must have params
        if '?' not in url or '=' not in url:
            filter_stats["no_params"] += 1
            continue

        # Diversity
        dork_count = len(dorks)
        if dork_count > args.max_dorks:
            filter_stats["diversity"] += 1
            continue

        # Classify
        tier = classify_url(url)
        by_tier[tier].append((url, dork_count))

    print(f"\n[+] Tier breakdown:")
    for tier, urls in by_tier.items():
        print(f"    {tier}: {len(urls)} URLs")

    print(f"\n[+] Filter stats:")
    for reason, n in filter_stats.most_common():
        print(f"    {reason}: {n}")

    # Output: SCRIPTED first, then CMS, then OTHER
    all_kept = []
    for tier in ["SCRIPTED", "CMS", "OTHER"]:
        all_kept.extend(by_tier[tier])

    print(f"\n[+] Total targets: {len(all_kept)}")

    # Save full list (deduped by URL, sorted by tier)
    out_full = Path(args.output)
    with open(out_full, 'w') as f:
        for url, _ in all_kept:
            f.write(url + '\n')
    print(f"[+] Saved {len(all_kept)} URLs to {out_full}")

    # Dedup by (host, path), keep one per page
    by_path = defaultdict(list)
    for url, count in all_kept:
        p = urlparse(url)
        by_path[(p.netloc, p.path)].append((url, count))

    out_unique = out_full.with_name(out_full.stem + "_unique.txt")
    with open(out_unique, 'w') as f:
        for (host, path), entries in by_path.items():
            # Keep the one with most query params (most informative)
            entries.sort(key=lambda x: -len(urlparse(x[0]).query))
            f.write(entries[0][0] + '\n')
    print(f"[+] Saved {len(by_path)} unique host+path to {out_unique}")

    # Grouped by host (for SQLiDumper crawling)
    out_grouped = out_full.with_name(out_full.stem + "_grouped.txt")
    with open(out_grouped, 'w') as f:
        for (host, path), entries in sorted(by_path.items()):
            for url, count in entries:
                f.write(f"{host}\t{url}\n")
    print(f"[+] Saved grouped to {out_grouped}")

    # Per-host stats
    out_stats = out_full.with_name(out_full.stem + "_stats.json")
    host_stats = defaultdict(lambda: {"urls": 0, "tier": "OTHER", "paths": set()})
    for (host, path), entries in by_path.items():
        # Tier = highest tier for this host
        tiers = [t for u, c in entries for t in [classify_url(u)]]
        tier = "SCRIPTED" if "SCRIPTED" in tiers else ("CMS" if "CMS" in tiers else "OTHER")
        host_stats[host]["urls"] += len(entries)
        host_stats[host]["paths"].add(path)
        host_stats[host]["tier"] = tier

    stats = {}
    for host, info in sorted(host_stats.items(), key=lambda x: -x[1]["urls"]):
        stats[host] = {
            "urls": info["urls"],
            "unique_paths": len(info["paths"]),
            "tier": info["tier"]
        }

    with open(out_stats, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"[+] Saved stats to {out_stats}")

    print(f"\n[+] Top 25 hosts by URL count:")
    for host, info in list(stats.items())[:25]:
        print(f"  {info['urls']:3d} URLs / {info['unique_paths']:2d} paths [{info['tier']:9s}] {host}")


if __name__ == "__main__":
    main()