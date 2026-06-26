#!/usr/bin/env python3
"""
DorkForge — Dork Yield Analyzer.

Reads a DorkForge harvest output (TXT or SQLite) and ranks dorks by
REAL TARGET yield (1-occurrence URLs with ?param= AND scripted extension).

Outputs:
- high_yield_dorks.txt — top tier dorks (yield >= 1) to keep running
- low_yield_dorks.txt — dorks to drop (yield == 0)
- yield_report.txt — full per-dork stats
- dork_recommendations.txt — actionable next steps

USAGE:
  py dork_yield_analyzer.py -i harvest.txt
  py dork_yield_analyzer.py -i harvest.db --sqlite
"""
import sys
import re
import argparse
from pathlib import Path
from collections import defaultdict, Counter
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
import format_v2
import format_v3


SCRIPT_EXTS = ('.php', '.asp', '.aspx', '.jsp', '.cfm', '.cgi')


def is_real_target(url, dorks_count):
    """A real target: 1-occurrence URL with params + no dork pollution."""
    if dorks_count != 1:
        return False
    if '?' not in url or '=' not in url:
        return False
    if format_v3.has_dork_pollution(url):
        return False
    return True


def is_scripted_target(url, dorks_count):
    """Real target + scripted extension (.php/.asp/etc)."""
    if not is_real_target(url, dorks_count):
        return False
    p = urlparse(url)
    path_lower = p.path.lower()
    return any(path_lower.endswith(ext) for ext in SCRIPT_EXTS)


def parse_txt(path):
    """Parse DorkForge TXT output: returns dict[url] -> set(dorks)."""
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


def parse_sqlite(path):
    """Parse DorkForge SQLite output."""
    import sqlite3
    url_to_dorks = defaultdict(set)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    try:
        c.execute("SELECT dork, url FROM hits")
        for dork, url in c.fetchall():
            url = url.replace('&amp;', '&')
            url_to_dorks[url].add(dork)
    except sqlite3.OperationalError:
        # Different schema
        c.execute("SELECT dork, url FROM urls")
        for dork, url in c.fetchall():
            url = url.replace('&amp;', '&')
            url_to_dorks[url].add(dork)
    conn.close()
    return url_to_dorks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True)
    ap.add_argument("--sqlite", action="store_true")
    ap.add_argument("-o", "--output-dir", default=".",
                    help="output directory (default: cwd)")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(exist_ok=True, parents=True)

    # Parse
    if args.sqlite or args.input.endswith('.db'):
        url_to_dorks = parse_sqlite(args.input)
    else:
        url_to_dorks = parse_txt(args.input)

    # Per-dork stats
    dork_total = Counter()
    dork_real = Counter()
    dork_scripted = Counter()

    for url, dorks in url_to_dorks.items():
        dork_count = len(dorks)
        for d in dorks:
            dork_total[d] += 1
        if is_real_target(url, dork_count):
            for d in dorks:
                dork_real[d] += 1
        if is_scripted_target(url, dork_count):
            for d in dorks:
                dork_scripted[d] += 1

    # Sort by scripted yield (the highest-value metric)
    all_dorks = sorted(dork_total.keys())
    high_yield = [d for d in all_dorks if dork_scripted[d] >= 1]
    mid_yield = [d for d in all_dorks if dork_real[d] >= 1 and dork_scripted[d] == 0]
    low_yield = [d for d in all_dorks if dork_real[d] == 0]

    print(f"[+] Total dorks: {len(all_dorks)}")
    print(f"[+] HIGH yield (1+ scripted targets): {len(high_yield)}")
    print(f"[+] MID yield (1+ real targets, no scripted): {len(mid_yield)}")
    print(f"[+] LOW yield (no real targets): {len(low_yield)}")
    print(f"[+] Total real targets: {sum(dork_real.values())}")
    print(f"[+] Total scripted targets: {sum(dork_scripted.values())}")

    # Save HIGH yield (re-run these!)
    high_path = out_dir / "high_yield_dorks.txt"
    high_path.write_text("\n".join(high_yield) + "\n", encoding="utf-8")
    print(f"[+] Saved {len(high_yield)} HIGH-yield dorks → {high_path}")

    # Save LOW yield (drop these)
    low_path = out_dir / "low_yield_dorks.txt"
    low_path.write_text("\n".join(low_yield) + "\n", encoding="utf-8")
    print(f"[+] Saved {len(low_yield)} LOW-yield dorks → {low_path}")

    # Full report
    report_path = out_dir / "yield_report.txt"
    with open(report_path, 'w') as f:
        f.write(f"# DorkForge Yield Report\n")
        f.write(f"# Input: {args.input}\n")
        f.write(f"# Total dorks: {len(all_dorks)}\n")
        f.write(f"# Total URLs: {sum(dork_total.values())}\n")
        f.write(f"# Real targets: {sum(dork_real.values())}\n")
        f.write(f"# Scripted targets: {sum(dork_scripted.values())}\n\n")
        f.write(f"# {'dork':<60s} {'urls':>6s} {'real':>5s} {'script':>6s}\n")
        f.write("# " + "-" * 85 + "\n")
        for d in sorted(all_dorks, key=lambda x: (-dork_scripted[x], -dork_real[x], -dork_total[x])):
            f.write(f"  {d:<60s} {dork_total[d]:>6d} {dork_real[d]:>5d} {dork_scripted[d]:>6d}\n")
    print(f"[+] Saved yield report → {report_path}")

    # Recommendations
    rec_path = out_dir / "dork_recommendations.txt"
    with open(rec_path, 'w') as f:
        f.write("DorkForge Recommendations\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Harvest: {args.input}\n")
        f.write(f"Total dorks: {len(all_dorks)}\n")
        f.write(f"High-yield dorks: {len(high_yield)} ({len(high_yield)*100//max(1,len(all_dorks))}%)\n\n")

        f.write("RECOMMENDED ACTIONS\n")
        f.write("-" * 50 + "\n\n")

        f.write(f"1. KEEP these {len(high_yield)} high-yield dorks for future harvests:\n")
        f.write(f"   cp {high_path} dorks_curated.txt\n")
        f.write(f"   py dorkforge.py -f dorks_curated.txt -e bing -p 4 -w 15 -o curated_harvest.txt\n\n")

        f.write(f"2. DROP these {len(low_yield)} zero-yield dorks:\n")
        f.write(f"   # Don't waste Bing quota on these\n")
        f.write(f"   # Many of these are likely overlapping with high-yield dorks\n\n")

        f.write(f"3. EXPAND high-yielders with parameter variants:\n")
        f.write("   # For each high-yield dork, try related params:\n")
        f.write("   # contains:asp inurl:'?id=' (5x yield)\n")
        f.write("   # -> contains:asp inurl:'?pid='\n")
        f.write("   # -> contains:asp inurl:'?uid='\n\n")

        f.write(f"4. INCREASE PAGES on high-yielders:\n")
        f.write(f"   # Use -p 5 instead of -p 2 for deeper harvest\n")
        f.write(f"   # Each page = 10 more URLs per dork\n\n")

        f.write("TOP 10 SCRIPTED-YIELD DORKS:\n")
        f.write("-" * 50 + "\n")
        for d in sorted(high_yield, key=lambda x: -dork_scripted[x])[:10]:
            f.write(f"  {dork_scripted[d]:2d}x {d}\n")
    print(f"[+] Saved recommendations → {rec_path}")

    # Show top 20 dorks
    print(f"\n{'='*60}")
    print(f"Top 20 dorks by scripted-target yield:")
    for d in sorted(high_yield, key=lambda x: (-dork_scripted[x], -dork_real[x]))[:20]:
        print(f"  {dork_scripted[d]:2d}x scripted / {dork_real[d]:2d}x real / {dork_total[d]:3d} urls  →  {d}")


if __name__ == "__main__":
    main()