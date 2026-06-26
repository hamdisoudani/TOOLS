#!/usr/bin/env python3
"""
DorkForge VOLUME URL filter — for SQLiDumper at scale.

Goal: 10K+ URLs that look injectable. Don't drop "spammy" looking URLs
because SQLiDumper will test them anyway. Just keep URLs that:
- Have a numeric OR id-like parameter (= most likely injectable)
- Are on a scripted extension (.php/.asp/.aspx/.jsp)
- Aren't from known aggregator domains (w3schools etc)
- Aren't CDNs (cloudfront, googleapis, etc)
- Have http or https scheme

Drops: images, CSS, JS, generic landing pages.
"""
import re
import sys
import argparse
from urllib.parse import urlparse, parse_qs

# Scripted extensions (URLs we want)
SCRIPTED_EXTS = ('.php', '.asp', '.aspx', '.jsp', '.cfm', '.cgi', '.do', '.action')

# Known aggregator / CDN / brand domains to drop (Bing SEO spam)
DROP_DOMAINS = {
    # Educational/tutorials (Bing SERP pollution)
    'w3schools.com',
    'w3school.com.cn', 'w3.org', 'tutorialspoint.com', 'w3resource.com',
    'javatpoint.com', 'geeksforgeeks.org', 'stackoverflow.com', 'stackexchange.com',
    'github.com', 'github.io', 'gitlab.com', 'bitbucket.org',
    # Social/wikis
    'facebook.com', 'twitter.com', 'linkedin.com', 'youtube.com',
    'reddit.com', 'quora.com', 'medium.com', 'wordpress.com',
    'wikipedia.org', 'wikimedia.org', 'wikihow.com', 'fandom.com',
    # Microsoft
    'microsoft.com', 'msdn.com', 'docs.microsoft.com', 'learn.microsoft.com',
    'office.com', 'outlook.com', 'live.com', 'azure.com',
    # Apple
    'apple.com', 'support.apple.com', 'developer.apple.com',
    # Google
    'google.com', 'googleapis.com', 'googleusercontent.com', 'gstatic.com',
    'youtube.com', 'ytimg.com', 'googlevideo.com',
    # Amazon
    'amazon.com', 'amazonaws.com', 'cloudfront.net', 'aws.amazon.com',
    # Other
    'archive.org', 'sourceforge.net', 'apache.org', 'php.net',
    'mysql.com', 'postgresql.org', 'nginx.org', 'apachefriends.org',
    'wix.com', 'squarespace.com', 'shopify.com', 'webflow.com',
    'cpanel.com', 'whmcs.com', 'plesk.com', 'softaculous.com',
    'paypal.com', 'stripe.com', 'squareup.com', 'braintreepayments.com',
    'cloudflare.com', 'akamai.com', 'akamaiedge.net', 'fastly.net',
    'jetpack.com', 'yoast.com', 'wpengine.com', 'kinsta.com',
    'godaddy.com', 'namecheap.com', 'hostgator.com', 'bluehost.com',
    'digitalocean.com', 'herokuapp.com', 'vercel.app', 'netlify.app',
    'wordpress.org', 'joomla.org', 'drupal.org', 'magento.com',
}

# URL re for matching params
URL_RE = re.compile(r'^https?://[^\s<>"\'\s]+$', re.IGNORECASE)


def is_drop_domain(url):
    """Check if URL is from a known aggregator/CDN."""
    try:
        host = urlparse(url).netloc.lower()
        for d in DROP_DOMAINS:
            if host == d or host.endswith('.' + d):
                return True
    except Exception:
        return True
    return False


def has_numeric_or_id_param(url):
    """URL must have at least one ?param=value or ?param= pattern.
    Numeric OR alpha-numeric ID pattern (3+ chars).
    Drops empty ?param (no =) and obvious listings (?page=home)."""
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return False
        # Look for ?X= or &X= patterns
        params = parse_qs(parsed.query, keep_blank_values=True)
        for name in params.keys():
            if not name or len(name) < 1:
                continue
            # Has value
            values = params[name]
            if not values:
                continue
            v = values[0] if values else ''
            # Pure numeric ID = highest yield
            if v.isdigit():
                return True
            # Alpha-numeric ID (3+ chars, contains at least one digit OR all alpha)
            if len(v) >= 3 and (any(c.isdigit() for c in v) or v.replace('-', '').replace('_', '').isalnum()):
                # Exclude obvious non-IDs
                if v.lower() in ('true', 'false', 'none', 'null', 'yes', 'no'):
                    continue
                return True
    except Exception:
        return False
    return False


def has_scripted_ext(url):
    """URL must point to a scripted page (or be a path with a scripted file).
    Accepts: .php?, .asp?, .aspx?, .jsp?, .cfm?, .cgi?, .do?, .action?
    Also: index.php?id=1, /path/file.php, etc.
    
    IMPORTANT: The script ext must be in the PATH portion, NOT in a query parameter
    value. e.g., /page.php?id=foo is valid; /search?text=page.php is NOT valid.
    """
    url_lower = url.lower().replace('&amp;', '&')
    # Get path portion (everything before ?)
    path = url_lower.split('?')[0]
    for ext in SCRIPTED_EXTS:
        # SCRIPTED_EXTS already has the dot (e.g. '.php')
        # Direct match: path ends with .ext
        if path.endswith(ext):
            return True
        # Mid-path match: /something/file.ext (must be followed by / or end)
        if ext + '/' in path:
            return True
        # .ext followed by ? or & in path only (not in query value)
        if ext + '?' in path or ext + '&' in path:
            return True
    return False


def is_injectable_target(url):
    """Master check."""
    if not URL_RE.match(url):
        return False
    if is_drop_domain(url):
        return False
    if not has_scripted_ext(url):
        return False
    if not has_numeric_or_id_param(url):
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description='DorkForge VOLUME filter (10K+ URLs for SQLiDumper)')
    ap.add_argument('-i', '--input', required=True, help='Input URL list (raw harvest output)')
    ap.add_argument('-o', '--output', required=True, help='Output filtered URL list')
    ap.add_argument('--max-per-domain', type=int, default=50,
                    help='Max URLs per domain (default 50, 0=unlimited)')
    ap.add_argument('--no-dedup', action='store_true',
                    help='Skip dedup (keep all matches)')
    ap.add_argument('--loose', action='store_true',
                    help='Loose mode: accept any ?param= pattern (not just numeric)')
    args = ap.parse_args()

    print(f'[*] Reading {args.input}...')
    raw_urls = []
    with open(args.input) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or not line.startswith('http'):
                continue
            # Parse: strip any " - " suffix from dork output
            line = line.split(' - ')[0].strip()
            if line.startswith('http'):
                # Normalize HTML-encoded ampersand
                line = line.replace('&amp;', '&')
                raw_urls.append(line)

    print(f'[+] {len(raw_urls)} raw URLs')

    # Filter
    seen = set()
    domain_count = {}
    filtered = []
    drop_stats = {'no_ext': 0, 'no_param': 0, 'drop_domain': 0, 'dup': 0, 'max_domain': 0}

    for url in raw_urls:
        if args.loose:
            # Loose mode: skip numeric/ID param check
            if not URL_RE.match(url):
                continue
            if is_drop_domain(url):
                drop_stats['drop_domain'] += 1
                continue
            if not has_scripted_ext(url):
                drop_stats['no_ext'] += 1
                continue
        else:
            if not is_injectable_target(url):
                # Identify why
                if is_drop_domain(url):
                    drop_stats['drop_domain'] += 1
                elif not has_scripted_ext(url):
                    drop_stats['no_ext'] += 1
                elif not has_numeric_or_id_param(url):
                    drop_stats['no_param'] += 1
                continue
        # Dedup
        if not args.no_dedup:
            # Dedup by host + path + sorted query
            try:
                p = urlparse(url)
                key = (p.netloc, p.path, tuple(sorted(p.query.split('&'))))
                if key in seen:
                    drop_stats['dup'] += 1
                    continue
                seen.add(key)
            except Exception:
                pass
        # Per-domain cap
        if args.max_per_domain > 0:
            try:
                host = urlparse(url).netloc.lower()
                if host in domain_count and domain_count[host] >= args.max_per_domain:
                    drop_stats['max_domain'] += 1
                    continue
                domain_count[host] = domain_count.get(host, 0) + 1
            except Exception:
                pass
        filtered.append(url)

    print(f'[+] {len(filtered)} URLs after filter (target: 10K+)')
    print(f'[+] Drop stats: {drop_stats}')
    print()
    print(f'[+] Unique domains: {len(set(urlparse(u).netloc for u in filtered))}')

    # Write
    with open(args.output, 'w') as f:
        f.write(f'# DorkForge VOLUME filter — for SQLiDumper\n')
        f.write(f'# Source: {args.input}\n')
        f.write(f'# Filter: scripted ext (.php/.asp/etc) + numeric/ID param + no spam\n')
        f.write(f'# Generated: 2026-06-26\n')
        f.write(f'# Total URLs: {len(filtered)}\n')
        f.write(f'#\n')
        for url in filtered:
            f.write(url + '\n')
    print(f'[+] Wrote {args.output}')


if __name__ == '__main__':
    main()
