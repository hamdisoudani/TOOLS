#!/usr/bin/env python3
"""
DorkForge v2 — Smart URL filter for SQLi targets.

Improvements over v1:
1. Strips search engine result pages (yandex, google, bing search URLs)
2. Strips dork-aggregator search results (sites that search for our dorks)
3. Strips URL shorteners (bit.ly, t.co, etc.)
4. Strips file hosts (drive.google.com, dropbox, etc.)
5. Strips social media share URLs (facebook.com/sharer, twitter.com/intent)
6. Extracts only URLs with REAL query parameters
7. Deduplicates by (host, path) keeping one URL per page
8. Optional: only keep URLs with SQLi-prone params
"""
import sys
import re
import argparse
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote


# ============================================================
# BLACKLISTS
# ============================================================

# Search engines - we don't want their SERP pages
SEARCH_ENGINES = {
    "google.com", "www.google.com", "bing.com", "www.bing.com",
    "yandex.com", "www.yandex.com", "yandex.ru", "duckduckgo.com",
    "baidu.com", "www.baidu.com", "sogou.com", "so.com",
    "search.yahoo.com", "www.startpage.com", "www.qwant.com",
    "online.yandex.com", "wap.yandex.com", "m.yandex.com",
    "pda.yandex.com", "yandex.com.tr",
    "search.aol.com", "www.ecosia.org",
}

# URL shorteners
SHORTENERS = {
    "bit.ly", "goo.gl", "t.co", "tinyurl.com", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "shorte.st", "clck.ru", "vk.cc",
    "tiny.cc", "shorturl.at", "rb.gy", "cutt.ly",
}

# Dork aggregators and SEO spam
DORK_SPAM = {
    "csdn.net", "blog.csdn.net", "juejin.cn", "cnblogs.com",
    "zhuanlan.zhihu.com", "segmentfault.com", "oschina.net",
    "medium.com", "github.com", "gist.github.com",
    "stackoverflow.com", "stackexchange.com", "quora.com",
    "reddit.com", "youtube.com", "facebook.com", "twitter.com",
    "x.com", "linkedin.com", "kalilinuxtutorials.com",
    "gbhackers.com", "hackersonlineclub.com", "dorksearch.com",
    "boxpiper.com", "learngoogle.com", "benjitrapp.github.io",
    "semrush.com", "ahrefs.com", "mangools.com", "moz.com",
    "link-assistant.com", "marketingminer.com", "googleguide.com",
    "coursehero.com", "pastebin.com", "paste2.org", "hastebin.com",
    "exploit-db.com", "cvedetails.com", "cve.mitre.org",
    "acunetix.com", "pentest-tools.com", "owasp.org",
    "wordpress.com", "blogspot.com", "wixsite.com",
    "weebly.com", "squarespace.com", "shopify.com",
    "drive.google.com", "docs.google.com", "dropbox.com",
    "mega.nz", "scribd.com", "slideshare.net",
    "researchgate.net", "academia.edu", "semanticscholar.org",
    "baike.baidu.com", "tieba.baidu.com", "weibo.com",
    "bilibili.com", "douban.com",
}

# File hosts (not exploitable via SQLi)
FILE_HOSTS = {
    "drive.google.com", "docs.google.com", "dropbox.com",
    "mega.nz", "1drv.ms", "onedrive.live.com",
    "mediafire.com", "4shared.com", "zippyshare.com",
    "rapidgator.net", "uploaded.net", "turbobit.net",
}

# URL patterns that indicate "search result" or "share" pages
JUNK_URL_PATTERNS = [
    r"/search\?",
    r"/search/",
    r"\?q=",
    r"\?query=",
    r"\?keyword=",
    r"\?search=",
    r"/sharer\.",
    r"/intent/",
    r"/share\?",
    r"/login\?",
    r"/signin\?",
    r"/signup\?",
    r"inurl:",
    r"inbody:",
    r"intitle:",
    r"inanchor:",
    r"ext:",
    r"contains:",
    r"filetype:",
    r"site:",
]


# SQLi-prone query parameters (the patterns we WANT in URLs)
SQLI_PARAMS = [
    # Tier 1: classic
    "id", "uid", "pid", "cid", "tid", "fid", "rid", "lid", "bid", "eid",
    "gid", "mid", "nid", "oid", "aid", "kid", "jid", "wid", "xid", "yid",
    "cat", "category", "page", "view", "show", "display", "item", "items",
    "product", "products", "prod", "pro", "p", "post", "blog", "article",
    "news", "newsid", "artid", "topic", "thread", "forum", "board", "section",
    "sec", "chapter", "episode", "track", "album", "movie", "film", "video",
    "vid", "gallery", "photo", "image", "img", "pic", "download", "file",
    "doc", "attachment", "attach", "upload", "user", "usr", "account", "acc",
    "member", "mem", "profile", "userid", "search", "q", "s", "query",
    "keyword", "kw", "term", "filter", "sort", "order", "dir", "date",
    "year", "month", "day", "lang", "language", "locale", "type", "kind",
    "mode", "format", "style", "template", "theme", "action", "act", "do",
    "op", "cmd", "exec", "func", "method", "load", "read", "get", "include",
    "require", "src", "source", "path", "dir", "file", "url", "redirect",
    "redir", "return", "returnurl", "next", "prev", "callback", "ref",
    "sid", "session", "sessionid", "token", "key", "apikey", "tab", "step",
    "phase", "level", "rank", "row", "col", "field",
    # More
    "i", "n", "v", "k", "c", "t", "f", "u", "a", "b", "d", "e", "g", "h",
    "j", "l", "m", "o", "r", "w", "x", "y", "z", "r", "p", "s",
    "num", "no", "ref", "code", "txt", "text", "title", "name",
    "img_id", "cat_id", "page_id", "item_id", "post_id", "thread_id",
    "topic_id", "user_id", "product_id", "category_id", "order_id",
    "manufacturer_id", "vendor_id", "customer_id", "review_id",
    "comment_id", "attachment_id", "tag_id", "author_id",
    "node", "nid", "taxonomy", "term", "vid",
    "p", "page_id", "cat", "category_id", "tag", "tag_id", "author", "author_id",
    "threadid", "postid", "userid", "forumid",
    "p_id", "c_id", "t_id", "f_id", "u_id", "g_id", "n_id", "r_id",
    "from", "to", "start", "end", "limit", "offset", "skip", "take",
    "ipp", "perpage", "pagesize",
]


def is_search_engine_serp(url: str) -> bool:
    """Detect Bing/Yandex/Google search result page."""
    try:
        p = urlparse(url)
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if host in SEARCH_ENGINES:
            return True
        # Also detect via path
        if "/search" in p.path.lower() and ("?q=" in url or "?text=" in url or "?query=" in url):
            return True
    except Exception:
        pass
    return False


def is_shortener(url: str) -> bool:
    try:
        p = urlparse(url)
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host in SHORTENERS
    except Exception:
        return False


def is_dork_spam(url: str) -> bool:
    try:
        p = urlparse(url)
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if host in DORK_SPAM:
            return True
        # Pattern check
        for kw in ["dork", "hack", "security-blog", "pentest"]:
            if kw in host:
                return True
    except Exception:
        pass
    return False


def is_file_host(url: str) -> bool:
    try:
        p = urlparse(url)
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host in FILE_HOSTS
    except Exception:
        return False


def is_junk_url(url: str) -> bool:
    """Check for SERP/share/login patterns."""
    url_lower = url.lower()
    for pat in JUNK_URL_PATTERNS:
        if re.search(pat, url_lower):
            return True
    return False


def has_sqli_param(url: str) -> bool:
    """Check if URL has SQLi-prone query parameters."""
    try:
        p = urlparse(url)
        if not p.query:
            return False
        # Get all param names (case-insensitive)
        params_lower = p.query.lower()
        # Split on & or ;
        param_strs = re.split(r'[&;]', params_lower)
        for ps in param_strs:
            if '=' in ps:
                name = ps.split('=', 1)[0].strip()
                if name in SQLI_PARAMS:
                    return True
        return False
    except Exception:
        return False


def smart_filter(url: str) -> tuple:
    """
    Return (keep: bool, reason: str) for a URL.
    keep=True means URL is a real SQLi target.
    """
    # Always strip
    if is_search_engine_serp(url):
        return False, "serp"
    if is_shortener(url):
        return False, "shortener"
    if is_dork_spam(url):
        return False, "dork_spam"
    if is_file_host(url):
        return False, "file_host"
    if is_junk_url(url):
        return False, "junk_pattern"

    # Must have query params
    p = urlparse(url)
    if not p.query or '=' not in p.query:
        return False, "no_params"

    return True, "ok"


def parse_dorkforge_txt(path: str):
    """Parse DorkForge TXT output."""
    urls = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line.startswith(('http://', 'https://')):
                # Decode &amp;
                line = line.replace('&amp;', '&')
                urls.append(line)
    return urls


def parse_dorkforge_sqlite(path: str):
    """Parse DorkForge SQLite output."""
    import sqlite3
    urls = []
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("SELECT url FROM hits")
        for (url,) in c.fetchall():
            url = url.replace('&amp;', '&')
            urls.append(url)
        conn.close()
    except Exception as e:
        print(f"[!] SQLite error: {e}")
    return urls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True, help="dorkforge output .txt or .db")
    ap.add_argument("-o", "--output", required=True, help="clean URL list output")
    ap.add_argument("--sqlite", action="store_true", help="input is SQLite")
    ap.add_argument("--unique-hostpath", action="store_true", default=True,
                    help="dedup by (host, path) keeping one URL per page")
    ap.add_argument("--all", action="store_true",
                    help="keep all URLs (don't filter to SQLi params)")
    ap.add_argument("--stats", action="store_true", help="print detailed stats")
    args = ap.parse_args()

    # Parse input
    if args.sqlite or args.input.endswith('.db'):
        urls = parse_dorkforge_sqlite(args.input)
    else:
        urls = parse_dorkforge_txt(args.input)
    print(f"[+] Parsed {len(urls)} URLs")

    # Apply smart filter
    kept = []
    filtered = {"serp": 0, "shortener": 0, "dork_spam": 0,
                "file_host": 0, "junk_pattern": 0, "no_params": 0}
    for u in urls:
        keep, reason = smart_filter(u)
        if keep:
            kept.append(u)
        else:
            filtered[reason] = filtered.get(reason, 0) + 1
    print(f"[+] After filter: {len(kept)} ({len(urls) - len(kept)} removed)")

    if args.stats:
        for reason, n in sorted(filtered.items(), key=lambda x: -x[1]):
            print(f"    {reason}: {n}")

    # SQLi param filter
    if not args.all:
        sqli = [u for u in kept if has_sqli_param(u)]
        print(f"[+] With SQLi-prone params: {len(sqli)} ({100*len(sqli)/max(1,len(kept)):.1f}% of kept)")
        kept = sqli

    # Dedup
    if args.unique_hostpath:
        seen = set()
        deduped = []
        for u in kept:
            p = urlparse(u)
            key = (p.netloc, p.path)
            if key not in seen:
                seen.add(key)
                deduped.append(u)
        print(f"[+] After (host, path) dedup: {len(deduped)}")
        kept = deduped

    # Save
    out = Path(args.output)
    out.write_text("\n".join(sorted(set(kept))) + "\n", encoding="utf-8")
    print(f"[+] Saved {len(kept)} URLs to {out}")


if __name__ == "__main__":
    main()