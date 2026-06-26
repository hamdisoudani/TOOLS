#!/usr/bin/env python3
"""
DorkForge v3 — Smart URL filter with diversity scoring.

KEY INSIGHT: Bing returns same SEO spam sites for MANY dorks.
Use dork-frequency as a quality signal:
- URL appears in 1-2 dorks → likely a REAL TARGET
- URL appears in 5+ dorks  → likely SEO spam (kinsta, gbhackers, etc.)
- URL appears in 50+ dorks → DEFINITELY spam

Quality Score:
- Start at 1.0
- / log2(2 + dork_count)  (more dorks = lower score)
- Filter score < 0.3

Plus standard filter:
- Strip SERP/share/login URLs
- Strip dork operators from param values (people searching for our dorks)
- Strip file hosts, shorteners
- Strip social share pages

OUTPUT:
- harvest_quality.txt — full URL list (no dedup)
- harvest_for_sqldumper.txt — deduped (host, path) with SQLi-prone params
- harvest_diversity_stats.txt — per-URL dork counts (for analysis)
"""
import sys
import re
import math
import argparse
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from collections import defaultdict, Counter

# Same as format_v2
from format_v2 import (
    SEARCH_ENGINES, SHORTENERS, DORK_SPAM, FILE_HOSTS, JUNK_URL_PATTERNS,
    SQLI_PARAMS, is_search_engine_serp, is_shortener, is_dork_spam,
    is_file_host, is_junk_url, has_sqli_param, smart_filter
)


# Patterns indicating the URL is someone SEARCHING for our dorks
DORK_OP_PATTERN = re.compile(
    r'(inurl|inbody|intitle|filetype|ext:|contains:|site:|allinurl|allintitle|allintext|allinanchor)',
    re.I
)


def has_dork_pollution(url: str) -> bool:
    """Check if URL param value contains dork operators (people searching for our dorks)."""
    try:
        p = urlparse(url)
        if not p.query:
            return False
        # Decode
        q_decoded = unquote(p.query)
        return bool(DORK_OP_PATTERN.search(q_decoded))
    except Exception:
        return False


def diversity_score(dork_count: int) -> float:
    """Lower score for URLs that appear in many dorks (spam signal)."""
    if dork_count <= 1:
        return 1.0
    # 1 dork = 1.0, 5 dorks = 0.46, 10 dorks = 0.34, 50 dorks = 0.21
    return 1.0 / math.log2(2 + dork_count)


def parse_dorkforge_txt_with_dorks(path: str):
    """
    Parse DorkForge TXT output, tracking which dork each URL came from.
    Returns: dict[url] -> set(dorks)
    """
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


def parse_dorkforge_sqlite_with_dorks(path: str):
    """Same but from SQLite."""
    import sqlite3
    url_to_dorks = defaultdict(set)
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("SELECT dork, url FROM hits")
        for dork, url in c.fetchall():
            url = url.replace('&amp;', '&')
            url_to_dorks[url].add(dork)
        conn.close()
    except Exception as e:
        print(f"[!] SQLite error: {e}")
    return url_to_dorks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True, help="dorkforge output .txt or .db")
    ap.add_argument("-o", "--output", required=True, help="clean URL list output")
    ap.add_argument("--sqlite", action="store_true", help="input is SQLite")
    ap.add_argument("--min-score", type=float, default=0.3,
                    help="min diversity score to keep (default 0.3)")
    ap.add_argument("--max-dorks", type=int, default=10,
                    help="max dork count to keep (default 10)")
    ap.add_argument("--no-diversity", action="store_true",
                    help="skip diversity filter")
    ap.add_argument("--no-dork-pollution", action="store_true",
                    help="skip dork-pollution filter")
    ap.add_argument("--stats-file", help="save diversity stats to this file")
    args = ap.parse_args()

    # Parse with dork tracking
    if args.sqlite or args.input.endswith('.db'):
        url_to_dorks = parse_dorkforge_sqlite_with_dorks(args.input)
    else:
        url_to_dorks = parse_dorkforge_txt_with_dorks(args.input)

    total_raw = sum(len(d) for d in url_to_dorks.values())
    print(f"[+] Parsed {total_raw} raw URLs ({len(url_to_dorks)} unique, "
          f"across {sum(1 for d in url_to_dorks.values() if d)} URL-dork mappings)")

    # Apply filters in order
    kept = []
    filter_stats = {
        "serp": 0, "shortener": 0, "dork_spam": 0,
        "file_host": 0, "junk_pattern": 0, "no_params": 0,
        "diversity": 0, "dork_pollution": 0
    }

    for url, dorks in url_to_dorks.items():
        # Standard smart filter
        keep, reason = smart_filter(url)
        if not keep:
            filter_stats[reason] = filter_stats.get(reason, 0) + 1
            continue

        # Dork pollution filter
        if not args.no_dork_pollution and has_dork_pollution(url):
            filter_stats["dork_pollution"] = filter_stats.get("dork_pollution", 0) + 1
            continue

        # Diversity filter (lower score for URLs appearing in many dorks)
        if not args.no_diversity:
            dork_count = len(dorks)
            if dork_count > args.max_dorks:
                filter_stats["diversity"] = filter_stats.get("diversity", 0) + 1
                continue
            score = diversity_score(dork_count)
            if score < args.min_score:
                filter_stats["diversity"] = filter_stats.get("diversity", 0) + 1
                continue

        kept.append((url, dorks))

    print(f"[+] After filter: {len(kept)} URLs")
    for reason, n in sorted(filter_stats.items(), key=lambda x: -x[1]):
        if n > 0:
            print(f"    {reason}: {n}")

    # Save diversity stats (optional)
    if args.stats_file:
        stats_path = Path(args.stats_file)
        with open(stats_path, 'w') as f:
            f.write("url\tdorks\tscore\n")
            for url, dorks in sorted(kept, key=lambda x: -len(x[1])):
                p = urlparse(url)
                f.write(f"{url}\t{len(dorks)}\t{diversity_score(len(dorks)):.3f}\n")
        print(f"[+] Diversity stats saved to {stats_path}")

    # SQLi param filter
    sqli = [(u, d) for u, d in kept if has_sqli_param(u)]
    print(f"[+] With SQLi-prone params: {len(sqli)}")

    # Dedup by (host, path) - keep all ?id= variants
    by_path = defaultdict(list)
    for u, d in sqli:
        p = urlparse(u)
        by_path[(p.netloc, p.path)].append((u, d))

    # For SQLiDumper: save full list (with all variations)
    out_full = Path(args.output)
    full_urls = sorted(set(u for u, d in sqli))
    out_full.write_text("\n".join(full_urls) + "\n", encoding="utf-8")
    print(f"[+] Saved {len(full_urls)} URLs to {out_full}")

    # Also save deduped by host+path (one URL per page)
    out_dedup = out_full.with_name(out_full.stem + "_unique.txt")
    dedup_urls = []
    for (host, path), ud_list in by_path.items():
        # Keep the one with most query params (most informative)
        ud_list.sort(key=lambda x: -len(urlparse(x[0]).query))
        dedup_urls.append(ud_list[0][0])
    out_dedup.write_text("\n".join(sorted(dedup_urls)) + "\n", encoding="utf-8")
    print(f"[+] Saved {len(dedup_urls)} unique host+path to {out_dedup}")

    # Also save all variants grouped by host (useful for SQLiDumper crawling)
    out_grouped = out_full.with_name(out_full.stem + "_grouped.txt")
    with open(out_grouped, 'w') as f:
        for (host, path), ud_list in sorted(by_path.items()):
            for u, d in ud_list:
                f.write(f"{host}\t{u}\n")
    print(f"[+] Saved grouped (host, url) to {out_grouped}")


if __name__ == "__main__":
    main()