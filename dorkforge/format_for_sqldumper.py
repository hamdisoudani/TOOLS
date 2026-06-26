#!/usr/bin/env python3
"""
Format DorkForge harvest output for SQLi Dumper / SQLmap import.
- Reads raw dorkforge output (URL + engine + dork headers)
- Filters out SEO spam / dork-list aggregator sites
- Extracts URLs with parameters
- Dedups by host+param combo
- Outputs: clean URL list ready for sqldumper
"""
import sys
import re
import argparse
from pathlib import Path
from urllib.parse import urlparse, parse_qs


# ─── SEO spam / dork-list aggregator blacklist ───────────────────────────────
# These sites list Google dorks instead of being real targets
SPAM_DOMAINS = {
    # Dork aggregators
    "kalilinuxtutorials.com",
    "gbhackers.com",
    "benjitrapp.github.io",
    "learngoogle.com",
    "boxpiper.com",
    "medium.com",
    "github.com",
    "gist.github.com",
    "stackoverflow.com",
    "dba.stackexchange.com",
    "coursehero.com",
    "sourashtracollege.com",  # already has ?id= but is college
    "googleguide.com",
    "marketingminer.com",
    "link-assistant.com",
    "zhuanlan.zhihu.com",
    "csdn.net",
    "cnblogs.com",
    "juejin.cn",
    "hackersonlineclub.com",
    "dorksearch.com",
    "exploit-db.com",
    "owasp.org",
    "acunetix.com",
    "pentest-tools.com",
    "insecure.org",
    "cvedetails.com",
    # Blog/forum spam
    "blog.csdn.net",
    "blog.sina.com.cn",
    "blog.inurl.com.br",
    "gist.github.com",
    # SEO/analytics
    "paste2.org",
    "pastebin.com",
    "avast.com",
    # Search engines & social
    "pda.yandex.com",
    "yandex.com",
    "duckduckgo.com",
    "google.com",
    "youtube.com",
    "facebook.com",
    "twitter.com",
    "linkedin.com",
    "instagram.com",
    "reddit.com",
    "quora.com",
    # Generic hosting/CDN
    "wordpress.com",
    "blogspot.com",
    "wixsite.com",
    "weebly.com",
    "squarespace.com",
    "shopify.com",
    # File hosts (not exploitable)
    "drive.google.com",
    "docs.google.com",
    "dropbox.com",
    "mega.nz",
}


def is_spam(url: str) -> bool:
    """Check if URL is from a known SEO spam / aggregator domain"""
    try:
        p = urlparse(url)
        host = p.netloc.lower()
        # Remove www.
        if host.startswith("www."):
            host = host[4:]
        # Check exact match and parent domain match
        for spam in SPAM_DOMAINS:
            if host == spam or host.endswith("." + spam):
                return True
        # Check for common blog/forum patterns that are aggregator content
        if any(kw in host for kw in ["dork", "hack", "security-blog", "pentest"]):
            return True
        return False
    except Exception:
        return True


def parse_dorkforge_txt(path: str):
    """Parse dorkforge's TXT output format:
    # DorkForge v1.0 | engines=bing | dorks=5629 | pages/dork=2

    ## dork: inurl:?id=
    https://example.com/?id=1
    https://example.com/?id=2
    """
    urls = set()
    engine = None
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#') and 'engines=' in line:
                m = re.search(r'engines=([\w,]+)', line)
                if m:
                    engine = m.group(1)
                continue
            if line.startswith('##') or line.startswith('#'):
                continue
            if line.startswith(('http://', 'https://')):
                urls.add(line)
    return urls, engine


def parse_dorkforge_sqlite(path: str):
    """Parse dorkforge's SQLite output for richer data"""
    import sqlite3
    urls_by_dork = {}
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("SELECT dork, url FROM hits")
        for dork, url in c.fetchall():
            urls_by_dork.setdefault(dork, set()).add(url)
        conn.close()
    except Exception as e:
        print(f"[!] SQLite parse error: {e}")
    return urls_by_dork


def filter_with_params(urls):
    """Keep only URLs with query parameters (the SQLi targets)"""
    out = []
    for url in urls:
        if '?' in url and '=' in url:
            # Filter to URLs with recognized SQLi-prone params
            q = urlparse(url).query.lower()
            if any(p + '=' in q for p in ['id=', 'cat=', 'page=', 'view=', 'show=',
                                            'item=', 'product=', 'news=', 'article=',
                                            'topic=', 'thread=', 'forum=', 'search=',
                                            'q=', 's=', 'query=', 'keyword=', 'file=',
                                            'path=', 'dir=', 'include=', 'template=',
                                            'user=', 'name=', 'lang=', 'locale=',
                                            'type=', 'sort=', 'order=', 'date=',
                                            'year=', 'month=', 'day=', 'pid=', 'cid=',
                                            'tid=', 'fid=', 'rid=', 'uid=', 'lid=',
                                            'bid=', 'eid=', 'gid=', 'mid=', 'nid=',
                                            'oid=', 'aid=', 'bid=', 'kid=', 'jid=',
                                            'wid=', 'xid=', 'yid=']):
                out.append(url)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True, help="dorkforge output .txt or .db")
    ap.add_argument("-o", "--output", required=True, help="clean URL list output")
    ap.add_argument("--sqlite", action="store_true",
                    help="parse SQLite db instead of TXT")
    ap.add_argument("--with-params-only", action="store_true",
                    help="only keep URLs with query parameters")
    ap.add_argument("--no-spam-filter", action="store_true",
                    help="don't filter spam domains")
    args = ap.parse_args()

    # Parse
    if args.sqlite or args.input.endswith('.db'):
        urls_by_dork = parse_dorkforge_sqlite(args.input)
        urls = set()
        for u in urls_by_dork.values():
            urls.update(u)
        engine = "from_sqlite"
    else:
        urls, engine = parse_dorkforge_txt(args.input)
        urls_by_dork = {}
    print(f"[+] Parsed {len(urls)} unique URLs (engine={engine})")

    # Filter spam
    if not args.no_spam_filter:
        before = len(urls)
        urls = {u for u in urls if not is_spam(u)}
        print(f"[+] After spam filter: {len(urls)} ({before - len(urls)} spam removed)")

    # Filter to URLs with parameters
    if args.with_params_only:
        before = len(urls)
        urls = filter_with_params(urls)
        print(f"[+] After param filter: {len(urls)} ({before - len(urls)} removed)")

    # Dedup & sort
    clean = sorted(urls)
    print(f"[+] Final URL list: {len(clean)} URLs")

    # Stats
    hosts = set()
    for u in clean:
        hosts.add(urlparse(u).netloc)
    print(f"[+] Unique hosts: {len(hosts)}")

    # Write
    out = Path(args.output)
    out.write_text("\n".join(clean) + "\n", encoding="utf-8")
    print(f"[+] Written to {out}")


if __name__ == "__main__":
    main()