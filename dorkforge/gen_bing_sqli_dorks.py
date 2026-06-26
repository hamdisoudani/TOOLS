#!/usr/bin/env python3
"""
Generate proper Bing dorks for SQLi URL harvesting.

Uses Microsoft-supported Bing advanced search operators:
  https://support.microsoft.com/en-us/bing/advanced-search-keywords
  https://support.microsoft.com/en-us/bing/advanced-search-options

KEY RULES:
- Bing uses MAX 10 terms per query (extra terms ignored)
- Use "inbody:" to find query params in page content (more reliable than inurl:)
- Use "contains:" for sites linking to specific file types
- Use "ext:" for filename extension filter
- Use "-" / "NOT" to exclude spam domains
- Use "site:" to target specific TLDs or limit scope
- Use "loc:" for country targeting
- Use "language:" for language filter

OUTPUT: dorks_bing_sqli.txt — dorks that maximize URLs with query parameters
"""
import argparse
from pathlib import Path

# SQLi-prone query parameters (the actual "?" patterns we want in URLs)
# These appear in URL as ?id=1, ?cat=2, etc.
SQLI_PARAMS = [
    # Tier 1: classic SQLi params (most likely vulnerable)
    "id", "ID", "Id", "uid", "UID", "pid", "PID", "cid", "CID", "tid", "TID",
    "fid", "FID", "rid", "RID", "lid", "LID", "bid", "BID", "eid", "EID",
    "gid", "GID", "mid", "MID", "nid", "NID", "oid", "OID", "aid", "AID",
    "kid", "KID", "jid", "JID", "wid", "WID", "xid", "XID", "yid", "YID",
    # Tier 2: common web params
    "cat", "category", "page", "view", "show", "display", "item", "items",
    "product", "products", "prod", "pro", "p", "post", "blog", "article",
    "news", "newsid", "artid", "topic", "thread", "forum", "fid", "board",
    "section", "sec", "chapter", "ch", "episode", "ep", "season", "se",
    "track", "song", "album", "artist", "movie", "film", "video", "vid",
    "gallery", "photo", "image", "img", "pic", "download", "dl", "file",
    "doc", "document", "attachment", "attach", "upload", "form", "input",
    "data", "value", "content", "body", "html", "text", "txt", "msg",
    "message", "comment", "desc", "description", "title", "name", "label",
    "user", "username", "usr", "account", "acc", "member", "mem", "profile",
    "prof", "userid", "user_id", "userId", "uid",
    "search", "q", "s", "query", "keyword", "kw", "term", "phrase",
    "filter", "sort", "order", "orderby", "sortby", "dir", "direction",
    "from", "to", "start", "end", "begin", "finish", "first", "last",
    "prev", "next", "back", "forward", "limit", "offset", "skip", "take",
    "date", "year", "month", "day", "time", "hour", "minute", "second",
    "start_date", "end_date", "from_date", "to_date",
    "lang", "language", "locale", "lc", "l",
    "type", "kind", "mode", "format", "fmt", "style", "template", "tpl",
    "theme", "skin", "layout", "design", "color", "colour", "size",
    "action", "act", "do", "op", "cmd", "command", "exec", "execute", "run",
    "func", "function", "method", "call", "process", "proc", "handler",
    "load", "read", "get", "fetch", "pull", "show", "display", "render",
    "include", "require", "import", "src", "source", "path", "dir", "folder",
    "file", "filename", "filepath", "uri", "url", "link", "href", "ref",
    "redirect", "redir", "return", "returnurl", "next", "prev", "back",
    "callback", "cb", "returnto", "goto", "jump", "forward", "continue",
    "ref", "referer", "referrer", "origin", "from",
    "img", "image", "pic", "photo", "thumb", "thumbnail", "avatar",
    "file", "download", "attachment", "doc", "docid", "docId",
    "sid", "session", "sessionid", "ssid", "token", "auth", "key", "apikey",
    "api_key", "access_token", "csrf", "nonce", "state",
    "xml", "json", "rss", "atom", "feed", "api", "endpoint", "service",
    # CMS-specific
    "p", "page_id", "cat", "category_id", "tag", "tag_id", "author", "author_id",
    "s", "search", "post", "p", "page", "attachment_id", "year", "monthnum",
    # Forum-specific
    "t", "topic", "f", "forum", "u", "user", "p", "post", "thread", "msg",
    # Forum software (vBulletin, phpBB, SMF, MyBB, XenForo, Discourse)
    "threadid", "postid", "userid", "forumid",
    # E-commerce
    "product_id", "category_id", "manufacturer_id", "vendor_id", "order_id",
    "customer_id", "cart_id", "wishlist_id", "compare_id", "review_id",
    # CMS platforms
    "node", "nid", "taxonomy", "term", "vid",
    # Webapp
    "id", "userId", "profileId", "accountId", "sessionId", "orderId",
    "itemId", "pageId", "postId", "commentId",
    # Common
    "debug", "test", "admin", "root", "config", "settings", "prefs",
    "tab", "panel", "section", "subsection", "group", "gid",
    "step", "phase", "stage", "level", "rank", "position", "pos",
    "row", "col", "column", "field", "key", "val", "value", "var",
]

# Unique params (lowercase, dedup) - prefer lowercase for case-insensitive Bing matching
PARAMS = sorted(set(p.lower() for p in SQLI_PARAMS))

# Vertical keywords (for inbody: search to find sites in specific sectors)
VERTICALS = {
    "ecommerce": ["shop", "store", "product", "cart", "buy", "price", "order", "checkout"],
    "hotel": ["hotel", "booking", "reservation", "room", "checkin", "checkout", "guesthouse"],
    "realestate": ["property", "realestate", "apartment", "rent", "sale", "listing", "house"],
    "job": ["job", "career", "vacancy", "employment", "hiring", "recruit"],
    "news": ["news", "article", "press", "media", "magazine", "newspaper"],
    "education": ["school", "university", "college", "course", "student", "faculty"],
    "health": ["clinic", "doctor", "hospital", "patient", "medical", "health"],
    "forum": ["forum", "thread", "post", "topic", "discussion", "community"],
    "directory": ["directory", "listing", "catalog", "index", "guide"],
    "travel": ["travel", "tour", "flight", "trip", "vacation", "tourism"],
    "restaurant": ["restaurant", "menu", "food", "dining", "cuisine", "chef"],
    "auto": ["car", "auto", "vehicle", "dealer", "motors"],
    "tech": ["software", "download", "app", "tech", "techcrunch"],
    "government": ["gov", "government", "ministry", "department", "agency", "municipality"],
    "finance": ["bank", "finance", "loan", "insurance", "credit", "investment"],
    "media": ["movie", "music", "video", "stream", "watch", "listen"],
}

# File extensions (for ext: filter)
EXTS = ["php", "asp", "aspx", "jsp", "cfm", "cgi", "pl", "py", "rb", "do", "action"]

# CMS patterns (already-known vulnerable patterns)
CMS_PATTERNS = {
    "wordpress": [
        "inurl:wp-content",
        "inurl:wp-includes",
        "inurl:wp-admin",
        "inurl:/wp-json/",
        "inurl:wordpress",
    ],
    "joomla": [
        "inurl:com_content",
        "inurl:com_virtuemart",
        "inurl:option=com_",
        "inurl:index.php?option=com_",
        "inurl:joomla",
    ],
    "drupal": [
        "inurl:drupal",
        "inurl:node/",
        "inurl:taxonomy/term",
        "inurl:sites/default/files",
    ],
    "vbulletin": [
        "inurl:showthread.php",
        "inurl:forumdisplay.php",
        "inurl:member.php",
        "inurl:vbulletin",
    ],
    "phpbb": [
        "inurl:viewtopic.php",
        "inurl:viewforum.php",
        "inurl:phpbb",
    ],
    "smf": [
        "inurl:index.php?topic=",
        "inurl:index.php?board=",
        "inurl:smf",
    ],
    "mybb": [
        "inurl:showthread.php",
        "inurl:forumdisplay.php",
        "inurl:mybb",
    ],
    "discuz": [
        "inurl:forumdisplay.php",
        "inurl:viewthread.php",
        "inurl:discuz",
    ],
    "magento": [
        "inurl:magento",
        "inurl:catalog/product/view",
        "inurl:checkout/cart",
    ],
    "opencart": [
        "inurl:index.php?route=product",
        "inurl:opencart",
    ],
    "oscommerce": [
        "inurl:oscommerce",
        "inurl:product_info.php",
    ],
    "prestashop": [
        "inurl:prestashop",
        "inurl:index.php?id_product",
    ],
}

# Spam domains to exclude (apply universally)
SPAM_EXCLUDE = " ".join([
    "-site:csdn.net", "-site:blog.csdn.net", "-site:juejin.cn", "-site:cnblogs.com",
    "-site:zhuanlan.zhihu.com", "-site:segmentfault.com", "-site:oschina.net",
    "-site:medium.com", "-site:github.com", "-site:gist.github.com",
    "-site:stackoverflow.com", "-site:stackexchange.com", "-site:quora.com",
    "-site:reddit.com", "-site:youtube.com", "-site:facebook.com",
    "-site:twitter.com", "-site:x.com", "-site:linkedin.com",
    "-site:kalilinuxtutorials.com", "-site:gbhackers.com", "-site:hackersonlineclub.com",
    "-site:dorksearch.com", "-site:boxpiper.com", "-site:learngoogle.com",
    "-site:benjitrapp.github.io", "-site:semrush.com", "-site:ahrefs.com",
    "-site:mangools.com", "-site:moz.com", "-site:link-assistant.com",
    "-site:marketingminer.com", "-site:googleguide.com", "-site:coursehero.com",
    "-site:pastebin.com", "-site:paste2.org", "-site:hastebin.com",
    "-site:exploit-db.com", "-site:cvedetails.com", "-site:cve.mitre.org",
    "-site:acunetix.com", "-site:pentest-tools.com", "-site:owasp.org",
    "-site:yandex.com", "-site:duckduckgo.com", "-site:google.com",
    "-site:wordpress.com", "-site:blogspot.com", "-site:wixsite.com",
    "-site:weebly.com", "-site:squarespace.com", "-site:shopify.com",
    "-site:drive.google.com", "-site:docs.google.com", "-site:dropbox.com",
    "-site:mega.nz", "-site:scribd.com", "-site:slideshare.net",
    "-site:scribdassets.com", "-site:researchgate.net", "-site:academia.edu",
    "-site:semanticscholar.org", "-site:scholar.google.com",
    "-site:baidu.com", "-site:baike.baidu.com", "-site:tieba.baidu.com",
    "-site:weibo.com", "-site:bilibili.com", "-site:douban.com",
])


def dork_param_inurl(param, ext=None, exclude=False):
    """Classic inurl: with optional ext and optional spam exclusion."""
    parts = [f'inurl:"?{param}="']
    if ext:
        parts.append(f"ext:{ext}")
    dork = " ".join(parts)
    if exclude:
        dork += " " + SPAM_EXCLUDE
    return dork


def dork_param_inbody(param, ext=None, exclude=False):
    """Use inbody: to find ?param= strings in page text (often more URLs than inurl:)."""
    parts = [f'inbody:"?{param}="']
    if ext:
        parts.append(f"ext:{ext}")
    dork = " ".join(parts)
    if exclude:
        dork += " " + SPAM_EXCLUDE
    return dork


def dork_param_inurl_vertical(param, vertical, exclude=True):
    """Param + vertical context."""
    if vertical not in VERTICALS or not VERTICALS[vertical]:
        return None
    kw = VERTICALS[vertical][0]  # First (most relevant) keyword
    parts = [f"inbody:{kw}", f'inurl:"?{param}="']
    dork = " ".join(parts)
    if exclude:
        dork += " " + SPAM_EXCLUDE
    return dork


def dork_cms_pattern(cms, pattern_key, exclude=True):
    """CMS-specific pattern."""
    if cms not in CMS_PATTERNS:
        return None
    pattern = CMS_PATTERNS[cms][pattern_key]
    # Add common SQLi param
    parts = [pattern, "inbody:id="]
    dork = " ".join(parts)
    if exclude:
        dork += " " + SPAM_EXCLUDE
    return dork


def dork_contains_ext(ext, param="id", exclude=True):
    """contains: with ext (finds sites with links to that file type)."""
    parts = [f"contains:.php", f'inurl:"?{param}="']  # placeholder
    # Actually contains: takes file type
    dork = f"contains:{ext} inurl:\"?{param}=\""
    if exclude:
        dork += " " + SPAM_EXCLUDE
    return dork


def dork_inbody_param_combo(p1, p2, exclude=True):
    """Two params in body (e.g. id + cat)."""
    parts = [f'inbody:"?{p1}="', f'inbody:"?{p2}="']
    dork = " ".join(parts)
    if exclude:
        dork += " " + SPAM_EXCLUDE
    return dork


def generate_all():
    """Generate all dorks."""
    dorks = set()

    # === TIER 1: inurl: with param + ext (most reliable for finding actual params in URLs) ===
    for param in PARAMS:
        # inurl with ext filter (no spam exclusion to keep dorks short)
        for ext in EXTS[:5]:  # php, asp, aspx, jsp, cfm
            dorks.add(f'inurl:"?{param}=" ext:{ext}')
        # Plain inurl (no ext)
        dorks.add(f'inurl:"?{param}="')

    # === TIER 2: inbody: with param (finds sites where ?param= appears in page text) ===
    for param in PARAMS[:60]:  # top 60 params only
        dorks.add(f'inbody:"?{param}="')

    # === TIER 3: Param + vertical context (smaller pool but more targeted) ===
    verticals_to_use = ["ecommerce", "hotel", "realestate", "job", "news",
                        "education", "health", "forum", "directory", "travel",
                        "restaurant", "auto", "government", "finance", "media"]
    for vertical in verticals_to_use:
        for param in PARAMS[:30]:  # top 30 params per vertical
            for kw in VERTICALS[vertical][:2]:  # top 2 keywords per vertical
                dorks.add(f'inbody:{kw} inurl:"?{param}="')

    # === TIER 4: CMS-specific (known vulnerable patterns) ===
    for cms in CMS_PATTERNS:
        for pattern in CMS_PATTERNS[cms]:
            for param in ["id", "page", "cat", "post", "thread", "topic", "product"]:
                dorks.add(f'{pattern} inbody:"?{param}="')

    # === TIER 5: Param combos (suggests filtering → more complex URL) ===
    param_pairs = [
        ("id", "cat"), ("id", "page"), ("cat", "page"), ("page", "id"),
        ("id", "view"), ("cat", "id"), ("product", "id"), ("item", "id"),
        ("user", "id"), ("post", "id"), ("thread", "id"), ("topic", "id"),
    ]
    for p1, p2 in param_pairs:
        dorks.add(f'inurl:"?{p1}=" inurl:"&{p2}="')
        dorks.add(f'inbody:"?{p1}=" inbody:"&{p2}="')

    # === TIER 6: contains: with file extension (finds sites linking to scripts) ===
    for ext in EXTS[:3]:
        for param in ["id", "page", "cat"]:
            dorks.add(f"contains:.{ext} inurl:\"?{param}=\"")

    # === TIER 7: Spam-excluded variants (smaller pool, cleaner results) ===
    for param in PARAMS[:30]:  # top 30 only
        dorks.add(f'inurl:"?{param}=" ' + SPAM_EXCLUDE)
        dorks.add(f'inbody:"?{param}=" ' + SPAM_EXCLUDE)

    # === TIER 8: Extension-specific high-value dorks ===
    for ext in EXTS:
        for param in ["id", "page", "cat", "view"]:
            dorks.add(f"ext:{ext} inurl:\"?{param}=\"")

    # Filter: Bing max 10 terms
    final = []
    for d in dorks:
        terms = d.split()
        if len(terms) > 10:
            # Truncate: keep first 10
            final.append(" ".join(terms[:10]))
        else:
            final.append(d)
    return sorted(set(final))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="dorks_bing_sqli.txt",
                    help="output file (one dork per line)")
    ap.add_argument("--no-spam", action="store_true",
                    help="don't add spam-exclude variants (smaller dork set)")
    args = ap.parse_args()

    dorks = generate_all()
    if args.no_spam:
        # Remove any dork with -site: term
        dorks = [d for d in dorks if "-site:" not in d]

    out = Path(args.output)
    out.write_text("\n".join(dorks) + "\n", encoding="utf-8")
    print(f"[+] Generated {len(dorks)} Bing dorks → {out}")
    print(f"[+] File size: {out.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()