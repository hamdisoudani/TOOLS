#!/usr/bin/env python3
"""
DorkForge v1.0 — multi-engine dork executor.

Pulls dorks from file or stdin, scrapes N pages per dork from the chosen
search engine, dedupes, and writes hits to TXT (+ optional SQLite).

Features (per spec):
  ✓ Multi-threading: --workers N (concurrent dorks)
  ✓ Pages-per-dork: --pages N
  ✓ Engine selector: --engine {ddg|bing|brave|yandex|all}
  ✓ Live progress: tqdm bar with processed dorks + URLs scraped

Usage:
    python3 dorkforge.py -f dorks.txt -e ddg -p 5 -w 20 -o out.txt
    python3 dorkforge.py -f dorks.txt -e bing -p 10 -w 5 -o out.txt --sqlite hits.db
    cat dorks.txt | python3 dorkforge.py -e yandex -p 5 -w 30
    python3 dorkforge.py -f dorks.txt -e all --pages 3 --workers 50

Notes:
  - curl_cffi gives us Safari iOS fingerprint (same as dork-hunter).
  - Falls back to plain requests if curl_cffi is not installed.
  - Skips search engine domains from results automatically.
  - On HTTP 429 or "unusual traffic" → exponential backoff, then retry.
"""

import argparse
import re
import sys
import time
import random
import sqlite3
import concurrent.futures
from pathlib import Path
from typing import Set, List, Optional, Tuple
from urllib.parse import unquote, urlparse, parse_qs

# Try to use curl_cffi for browser-grade TLS fingerprint; fall back to requests.
try:
    from curl_cffi import requests as cffi_requests
    HAVE_CFFI = True
except ImportError:
    import requests
    HAVE_CFFI = False

# ─── Config ──────────────────────────────────────────────────────────────────

ENGINES = ("ddg", "bing", "brave", "yandex", "all")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
)

ENGINE_URLS = {
    "ddg":   "https://html.duckduckgo.com/html/",
    "bing":  "https://www.bing.com/search",
    "brave": "https://search.brave.com/search",
    "yandex":"https://yandex.com/search/",
}

ENGINE_RESULTS_PER_PAGE = {
    "ddg":   10,   # DDG HTML endpoint
    "bing":  10,   # Bing web
    "brave": 20,   # Brave
    "yandex":10,   # Yandex web
}

EXCLUDED_DOMAINS = {
    "google.com", "www.google.com", "bing.com", "www.bing.com",
    "yahoo.com", "duckduckgo.com", "www.duckduckgo.com",
    "baidu.com", "yandex.com", "yandex.ru", "youtube.com", "facebook.com",
    "twitter.com", "x.com", "instagram.com", "linkedin.com",
    "wikipedia.org", "amazon.com", "microsoft.com", "github.com",
    "stackoverflow.com", "pinterest.com", "reddit.com", "tiktok.com",
    "ebay.com", "apple.com", "netflix.com", "twitch.tv", "discord.com",
    "brave.com", "search.brave.com",
}

# Try to import tqdm for progress; fall back to simple counter
try:
    from tqdm import tqdm
    HAVE_TQDM = True
except ImportError:
    HAVE_TQDM = False


# ─── Result extraction (engine-agnostic) ──────────────────────────────────────

# Match any <a href="...">URL</a> inside result blocks. We rely on the
# structure: search engines put result links in <a href="..."> with on-page
# anchor text. We grab the href directly.
RE_HREF = re.compile(r'<a[^>]+href="(https?://[^"]+)"[^>]*>', re.IGNORECASE)
RE_DDG_REDIR = re.compile(r'youtube\.com\.duckduckgo\.com|youtube_redirect|youtube##', re.IGNORECASE)


def extract_urls(html: str, engine: str) -> List[str]:
    """Pull candidate URLs from the search results page."""
    urls = []
    seen_local = set()

    if engine == "ddg":
        # DDG HTML uses a redirect URL like //duckduckgo.com/l/?uddg=<encoded>
        # and also direct result__a class links. Use a specific pattern.
        # Pattern 1: result links in <a class="result__a" href="...">
        for m in re.finditer(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', html, re.IGNORECASE
        ):
            href = m.group(1)
            # DDG wraps external links in //duckduckgo.com/l/?uddg=<encoded>
            if "uddg=" in href:
                m2 = re.search(r'uddg=([^&]+)', href)
                if m2:
                    try:
                        from urllib.parse import unquote as _u
                        href = _u(m2.group(1))
                    except Exception:
                        pass
            if href and href not in seen_local:
                seen_local.add(href)
                urls.append(href)
        # Fallback: any <a href="http..."> in result__a class
        if not urls:
            for m in RE_HREF.finditer(html):
                href = m.group(1)
                if "duckduckgo.com" in href:
                    continue
                if href not in seen_local:
                    seen_local.add(href)
                    urls.append(href)

    elif engine == "bing":
        # Bing uses <li class="b_algo">...<a href="...">...</a>
        for m in re.finditer(
            r'<li[^>]+class="b_algo"[^>]*>.*?<a[^>]+href="(https?://[^"]+)"',
            html, re.IGNORECASE | re.DOTALL,
        ):
            href = m.group(1)
            if href not in seen_local:
                seen_local.add(href)
                urls.append(href)
        if not urls:
            for m in RE_HREF.finditer(html):
                href = m.group(1)
                if any(d in href for d in ("bing.com", "microsoft.com")):
                    continue
                if href not in seen_local:
                    seen_local.add(href)
                    urls.append(href)

    elif engine == "brave":
        # Brave result links: <a class="h" href="...">
        for m in re.finditer(
            r'<a[^>]+class="[^"]*\bh\b[^"]*"[^>]+href="(https?://[^"]+)"',
            html, re.IGNORECASE,
        ):
            href = m.group(1)
            if "brave.com" in href:
                continue
            if href not in seen_local:
                seen_local.add(href)
                urls.append(href)
        if not urls:
            for m in RE_HREF.finditer(html):
                href = m.group(1)
                if "brave.com" in href:
                    continue
                if href not in seen_local:
                    seen_local.add(href)
                    urls.append(href)

    elif engine == "yandex":
        # Yandex result links: <a class="Link Link_theme_normal OrganicTitle-Link" href="...">
        for m in re.finditer(
            r'<a[^>]+class="[^"]*OrganicTitle[^"]*"[^>]+href="([^"]+)"',
            html, re.IGNORECASE,
        ):
            href = m.group(1)
            # Yandex uses redirect: https://yandex.com/clck/jsredir?from=...
            if "clck/jsredir" in href:
                continue
            if "yandex." in href and "yandex.com/search" in href:
                continue
            if href not in seen_local:
                seen_local.add(href)
                urls.append(href)
        if not urls:
            for m in RE_HREF.finditer(html):
                href = m.group(1)
                if any(d in href for d in ("yandex.com", "yandex.ru")):
                    continue
                if href not in seen_local:
                    seen_local.add(href)
                    urls.append(href)

    return urls


def filter_excluded(urls: List[str]) -> List[str]:
    """Drop search engine domains and any obvious garbage."""
    out = []
    for u in urls:
        try:
            host = urlparse(u).hostname or ""
        except Exception:
            continue
        if not host:
            continue
        if host in EXCLUDED_DOMAINS:
            continue
        if host.startswith("www."):
            host = host[4:]
        if host in EXCLUDED_DOMAINS:
            continue
        out.append(u)
    return out


def is_blocked(html: str, status: int) -> bool:
    """Detect rate-limit / captcha / challenge pages."""
    if status in (202, 429, 503):
        return True
    if status != 200:
        return True
    low = html.lower()
    if len(html) < 800:
        return True
    for marker in (
        "unusual traffic", "captcha", "access denied",
        "are you a human", "cf-challenge", "checking your browser",
        "rate limit", "too many requests", "automated requests",
        "lite.duckduckgo.com/lite",  # DDG fallback to lite (no results)
    ):
        if marker in low:
            return True
    return False


# ─── HTTP layer ──────────────────────────────────────────────────────────────

class Client:
    """HTTP client with optional browser-fingerprint impersonation."""

    def __init__(self, use_cffi: bool = True, timeout: int = 25):
        self.use_cffi = use_cffi and HAVE_CFFI
        self.timeout = timeout
        if self.use_cffi:
            self._session = cffi_requests.Session(impersonate="safari17_2_ios")
        else:
            self._session = None  # use requests.Session per call

    def get(self, url: str, params: dict, headers: dict = None) -> Tuple[int, str]:
        hdrs = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        }
        if headers:
            hdrs.update(headers)
        try:
            if self.use_cffi:
                r = self._session.get(
                    url, params=params, headers=hdrs, timeout=self.timeout,
                    allow_redirects=True,
                )
                return r.status_code, r.text
            else:
                hdrs.setdefault("User-Agent", DEFAULT_USER_AGENT)
                r = requests.get(
                    url, params=params, headers=hdrs, timeout=self.timeout,
                    allow_redirects=True,
                )
                return r.status_code, r.text
        except Exception as e:
            return 0, f"ERROR: {e}"


# ─── Scraper ─────────────────────────────────────────────────────────────────

class Scraper:
    """Scrapes one dork across N pages of one engine."""

    def __init__(self, client: Client, engine: str, pages: int,
                 delay_min: float = 0.4, delay_max: float = 1.2,
                 max_retries: int = 3):
        self.client = client
        self.engine = engine
        self.pages = pages
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.base_url = ENGINE_URLS[engine]

    def _params(self, dork: str, page: int) -> dict:
        if self.engine == "ddg":
            # kl=us-en forces English HTML endpoint. Other params cause 202.
            return {
                "q": dork,
                "kl": "us-en",
                "s": str((page - 1) * ENGINE_RESULTS_PER_PAGE["ddg"]),
            }
        if self.engine == "bing":
            return {"q": dork, "first": str((page - 1) * ENGINE_RESULTS_PER_PAGE["bing"] + 1) if page > 1 else ""}
        if self.engine == "brave":
            return {"q": dork, "offset": str((page - 1) * ENGINE_RESULTS_PER_PAGE["brave"])}
        if self.engine == "yandex":
            return {"text": dork, "p": str(page - 1)}
        return {"q": dork}

    def scrape(self, dork: str) -> List[str]:
        """Scrape all pages for one dork. Returns de-duped, filtered URLs."""
        all_urls: List[str] = []
        seen_local: Set[str] = set()

        for page in range(1, self.pages + 1):
            delay = random.uniform(self.delay_min, self.delay_max)
            time.sleep(delay)

            status, html = 0, ""
            for attempt in range(self.max_retries):
                status, html = self.client.get(self.base_url, self._params(dork, page))
                if status == 200 and not is_blocked(html, status):
                    break
                # Backoff
                wait = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait)
            else:
                # All retries blocked — skip this dork
                break

            if is_blocked(html, status):
                break  # persistent block, move on

            urls = filter_excluded(extract_urls(html, self.engine))
            for u in urls:
                if u not in seen_local:
                    seen_local.add(u)
                    all_urls.append(u)

        return all_urls


# ─── Worker (one dork per worker) ────────────────────────────────────────────

def process_dork(args_tuple) -> Tuple[str, str, List[str]]:
    """Worker function. Returns (dork, engine, urls)."""
    dork, engine, client, pages = args_tuple
    scraper = Scraper(client, engine, pages)
    try:
        urls = scraper.scrape(dork)
        return dork, engine, urls
    except Exception as e:
        return dork, engine, [f"ERROR: {e}"]


# ─── Output sinks ────────────────────────────────────────────────────────────

def write_output(path: str, engine: str, dork: str, urls: List[str]):
    """Append results to TXT file."""
    mode = "a" if Path(path).exists() else "w"
    with open(path, mode, encoding="utf-8") as f:
        if mode == "w":
            f.write(f"# DorkForge v1.0 | engine={engine} | dorks_run=0 | urls=0\n\n")
        f.write(f"## dork: {dork}\n")
        for u in urls:
            if u.startswith("ERROR:"):
                f.write(f"# {u}\n")
            else:
                f.write(f"{u}\n")
        f.write("\n")


def write_sqlite(path: str, engine: str, dork: str, urls: List[str]):
    """Append results to SQLite. Idempotent: schema + UNIQUE on (engine, url)."""
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP,
            engine TEXT NOT NULL,
            dork TEXT NOT NULL,
            url TEXT NOT NULL,
            UNIQUE(engine, url)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_dork ON hits(dork)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_engine ON hits(engine)")
    inserted = 0
    for u in urls:
        if u.startswith("ERROR:"):
            continue
        try:
            c.execute(
                "INSERT OR IGNORE INTO hits (engine, dork, url) VALUES (?, ?, ?)",
                (engine, dork, u),
            )
            if c.rowcount > 0:
                inserted += 1
        except sqlite3.Error:
            pass
    conn.commit()
    conn.close()
    return inserted


# ─── Progress ────────────────────────────────────────────────────────────────

class Progress:
    """Lightweight progress tracker with live stats."""

    def __init__(self, total: int, enabled: bool = True):
        self.total = total
        self.processed = 0
        self.urls = 0
        self.errors = 0
        self.start_ts = time.time()
        self.enabled = enabled
        self._bar = None
        if enabled and HAVE_TQDM:
            self._bar = tqdm(
                total=total, desc="DorkForge", unit="dork",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}",
                file=sys.stderr,
            )

    def update(self, urls_found: int, errors: int = 0):
        self.processed += 1
        self.urls += urls_found
        self.errors += errors
        if self._bar:
            self._bar.set_postfix({
                "urls": self.urls,
                "errs": self.errors,
            })
            self._bar.update(1)
        elif self.enabled:
            # Fallback: print a one-line update
            elapsed = int(time.time() - self.start_ts)
            rate = self.processed / max(elapsed, 1)
            print(
                f"\r[DorkForge] {self.processed}/{self.total} | "
                f"urls={self.urls} errs={self.errors} | "
                f"{elapsed}s ({rate:.1f}/s)",
                end="", file=sys.stderr, flush=True,
            )

    def close(self):
        if self._bar:
            self._bar.close()
        elif self.enabled:
            print(file=sys.stderr)
        elapsed = int(time.time() - self.start_ts)
        print(
            f"\n[done] {self.processed}/{self.total} dorks | {self.urls} urls | "
            f"{self.errors} errors | {elapsed}s",
            file=sys.stderr,
        )


# ─── Main ────────────────────────────────────────────────────────────────────

def load_dorks(path: Optional[str]) -> List[str]:
    if path:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    # Stdin
    return [line.strip() for line in sys.stdin if line.strip() and not line.startswith("#")]


def main():
    ap = argparse.ArgumentParser(
        description="DorkForge v1.0 — multi-engine dork executor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -f dorks.txt -e ddg -p 5 -w 20
  %(prog)s -f dorks.txt -e bing -p 10 -w 5 -o hits.txt --sqlite hits.db
  %(prog)s -f dorks.txt -e all --pages 3 --workers 50 --no-progress
        """,
    )
    ap.add_argument("-f", "--file", help="Dork file (one per line). Use - for stdin.")
    ap.add_argument("-d", "--dork", help="Single dork (overrides -f)")
    ap.add_argument("-e", "--engine", choices=ENGINES, default="ddg",
                    help="Search engine (default: ddg)")
    ap.add_argument("-p", "--pages", type=int, default=5,
                    help="Pages per dork (default: 5)")
    ap.add_argument("-w", "--workers", type=int, default=10,
                    help="Concurrent dork workers (default: 10)")
    ap.add_argument("-o", "--output", default="hits.txt",
                    help="Output TXT file (default: hits.txt)")
    ap.add_argument("--sqlite", metavar="DB", help="Also write to SQLite DB")
    ap.add_argument("--no-progress", action="store_true",
                    help="Disable progress bar")
    ap.add_argument("--no-cffi", action="store_true",
                    help="Disable curl_cffi browser fingerprint")
    ap.add_argument("--timeout", type=int, default=25, help="HTTP timeout (default: 25)")
    ap.add_argument("--delay-min", type=float, default=0.4, help="Min delay between requests (s)")
    ap.add_argument("--delay-max", type=float, default=1.2, help="Max delay between requests (s)")
    args = ap.parse_args()

    # Load dorks
    if args.dork:
        dorks = [args.dork]
    else:
        dorks = load_dorks(args.file)
    if not dorks:
        print("[!] No dorks provided. Use -f or -d.", file=sys.stderr)
        sys.exit(1)

    # Engines to run
    if args.engine == "all":
        engines = ["ddg", "bing", "brave", "yandex"]
    else:
        engines = [args.engine]

    # Truncate output
    Path(args.output).write_text(
        f"# DorkForge v1.0 | engines={','.join(engines)} | "
        f"dorks={len(dorks)} | pages/dork={args.pages}\n\n"
    )

    # Build work list (one entry per dork × engine)
    work = []
    for d in dorks:
        for e in engines:
            work.append((d, e))

    # Print config
    print(f"[*] DorkForge v1.0", file=sys.stderr)
    print(f"[*] Dorks: {len(dorks)} | Engines: {engines} | Total jobs: {len(work)}", file=sys.stderr)
    print(f"[*] Pages/dork: {args.pages} | Workers: {args.workers}", file=sys.stderr)
    print(f"[*] Output: {args.output}" + (f" + {args.sqlite}" if args.sqlite else ""), file=sys.stderr)
    print(f"[*] curl_cffi: {HAVE_CFFI and not args.no_cffi} | tqdm: {HAVE_TQDM}", file=sys.stderr)
    print(file=sys.stderr)

    # Client is shared across workers (session reuse)
    client = Client(use_cffi=not args.no_cffi, timeout=args.timeout)

    progress = Progress(total=len(work), enabled=not args.no_progress)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(
                process_dork,
                (d, e, client, args.pages),
            ): (d, e)
            for (d, e) in work
        }
        for fut in concurrent.futures.as_completed(futures):
            d, e = futures[fut]
            try:
                dork, engine, urls = fut.result()
            except Exception as exc:
                dork, engine, urls = d, e, [f"ERROR: {exc}"]

            errors = sum(1 for u in urls if u.startswith("ERROR:"))
            clean_urls = [u for u in urls if not u.startswith("ERROR:")]

            write_output(args.output, engine, dork, clean_urls)
            if args.sqlite:
                write_sqlite(args.sqlite, engine, dork, clean_urls)

            progress.update(len(clean_urls), errors=errors)

    progress.close()


if __name__ == "__main__":
    main()
