#!/usr/bin/env python3
"""
Parametric Dork Generator v2.0 — mass URL harvest
Goal: produce URL lists with query parameters (for sqldumper)
Strategy: target known vulnerable parameter names across common site verticals
"""
import sys
import argparse
from pathlib import Path
from itertools import product

# ─── Parameter catalog ───────────────────────────────────────────────────────
# Format: (param_name, vulnerable_pattern, common_php_pages)
# These are the parameters most likely to be passed to SQL unsanitized
PARAMS = [
    # IDs (classic)
    "id", "ID", "Id", "page_id", "post_id", "article_id", "news_id",
    "item_id", "product_id", "cat_id", "category_id", "user_id", "uid",
    "order_id", "orderid", "order", "oid", "pid", "cid", "rid",
    "tid", "fid", "nid", "mid", "bid", "eid", "gid", "lid",
    # Categories
    "cat", "category", "c", "categorie", "categorie_id", "catid", "categoria",
    # Search
    "q", "s", "search", "searchword", "keyword", "k", "kw", "query",
    "search_query", "searchTerm", "searchterm",
    # Page
    "page", "p", "pagenum", "page_id", "pID", "start", "offset",
    # View / show
    "view", "v", "show", "display", "mode", "type", "action", "do",
    # File / include
    "file", "filename", "filepath", "path", "dir", "folder", "include",
    "page", "template", "tmpl", "pg", "cont", "content",
    # Sort / order
    "sort", "sortby", "orderby", "order_by", "order", "sort_order",
    # Date
    "year", "month", "day", "date", "from", "to", "start_date", "end_date",
    # User
    "user", "username", "uname", "u", "login", "name", "email",
    # Product / shop
    "product", "item", "sku", "art", "artnum", "manufacturer", "vendor",
    "brand", "model", "ref", "reference", "code",
    # Forum / board (phpBB, vBulletin, SMF)
    "forum", "topic", "thread", "threadid", "f", "t", "p", "topicid",
    "board", "boardid", "b", "post", "postid", "msg", "message",
    # News / blog
    "story", "story_num", "newsid", "artid", "blogid", "entry", "entryid",
    # Locale / language (often concat'd into queries)
    "lang", "language", "locale", "l", "lan",
    # Admin
    "admin", "adm", "mod", "module", "modul", "section", "sec",
    # Generic
    "var", "val", "value", "data", "input", "arg", "argument", "param",
    "field", "key", "code", "no", "num", "number", "n",
]

# ─── Site verticals (inurl: terms) ───────────────────────────────────────────
VERTICALS = {
    "ecommerce": [
        "shop", "store", "product", "products", "item", "catalog",
        "category", "cart", "checkout", "order", "buy",
    ],
    "hotel": [
        "hotel", "hotels", "booking", "reservation", "reserv", "room",
        "rooms", "stay", "accommodation", "property", "lodging",
    ],
    "realestate": [
        "property", "properties", "real-estate", "realestate", "listing",
        "listings", "house", "apartment", "rent", "sale", "agent",
    ],
    "job": [
        "job", "jobs", "career", "careers", "employment", "vacancy",
        "vacancies", "position", "positions", "recruitment", "hiring",
    ],
    "news": [
        "news", "article", "articles", "story", "stories", "blog",
        "post", "posts", "press", "media", "magazine", "publication",
    ],
    "forum": [
        "forum", "forums", "community", "discussion", "thread",
        "topic", "board", "group",
    ],
    "directory": [
        "directory", "listing", "listings", "company", "business",
        "profile", "profiles", "member", "members", "classified",
    ],
    "education": [
        "course", "courses", "school", "university", "training",
        "student", "lesson", "class", "program", "study", "degree",
    ],
    "health": [
        "doctor", "clinic", "hospital", "patient", "appointment",
        "medical", "health", "treatment", "medicine", "pharmacy",
    ],
    "travel": [
        "flight", "flights", "airline", "ticket", "tour", "tourism",
        "destination", "trip", "voyage", "travel",
    ],
    "restaurant": [
        "restaurant", "menu", "food", "recipe", "order-online", "delivery",
        "reservation", "book-table", "cuisine", "dish",
    ],
    "auto": [
        "car", "auto", "vehicle", "cars", "vehicles", "dealer",
        "showroom", "automotive", "motor", "motorcycle", "bike",
    ],
    "tech": [
        "software", "app", "tool", "tools", "download", "downloads",
        "service", "services", "api", "platform", "tech",
    ],
    "gov": [
        "gov", "government", "ministry", "agency", "department",
        "public", "official", "administration", "municipality",
    ],
    "finance": [
        "bank", "banking", "insurance", "loan", "credit", "finance",
        "investment", "trading", "broker", "mortgage", "payment",
    ],
    "media": [
        "video", "watch", "movie", "movies", "tv", "channel", "stream",
        "music", "song", "album", "artist", "playlist",
    ],
}

# ─── Filetypes (most vulnerable to SQLi) ─────────────────────────────────────
FILETYPES = ["php", "asp", "aspx", "jsp", "cfm", "cgi", "do", "action"]

# ─── URL patterns with parameters ────────────────────────────────────────────
URL_PATTERNS = [
    # Standard ?param= patterns (most common for SQLi)
    'inurl:"?{p}=" inurl:.{ext}',
    'inurl:"?{p}="',
    'inurl:"{p}=" inurl:.{ext}',
    'inurl:"{p}="',
    # Double-param (often concat'd)
    'inurl:"?{p}=&{p2}=" inurl:.{ext}',
    # File with parameter (vulnerable to LFI/SQLi combo)
    'inurl:".{ext}?{p}="',
    'inurl:".{ext}?{p}=&{p2}="',
    # Path-based params
    'inurl:"/{p}/" inurl:.{ext}',
    # Site operator
    'inurl:".{ext}" inurl:"?{p}="',
]


def gen_basic_params():
    """Basic param-only dorks (no vertical) — max yield"""
    out = []
    for p in PARAMS:
        # Standalone ?param= dorks (these work in Bing)
        out.append(f'inurl:"?{p}="')
        out.append(f'inurl:"?{p}=" inurl:.php')
        out.append(f'inurl:"?{p}=" inurl:.asp')
        out.append(f'inurl:"?{p}=" inurl:.aspx')
    return out


def gen_vertical_param(vertical, params, exts=("php", "asp", "aspx")):
    """Vertical + param combo dorks — high signal, lower volume"""
    out = []
    for kw in VERTICALS.get(vertical, []):
        for p in params:
            for ext in exts:
                # Vertical keyword in URL + param + ext
                out.append(f'inurl:"{kw}" inurl:"?{p}=" inurl:.{ext}')
                out.append(f'inurl:"{kw}.{ext}?{p}="')
    return out


def gen_param_combos():
    """Multi-param combos (often concat'd into single query)"""
    out = []
    pairs = [
        ("id", "cat"), ("id", "page"), ("page", "cat"), ("id", "view"),
        ("cat", "page"), ("id", "action"), ("id", "do"), ("view", "id"),
        ("id", "type"), ("id", "mode"), ("page", "id"), ("cat", "id"),
    ]
    for p1, p2 in pairs:
        for ext in ("php", "asp", "aspx", "jsp"):
            out.append(f'inurl:"?{p1}=&{p2}=" inurl:.{ext}')
            out.append(f'inurl:".{ext}?{p1}=&{p2}="')
    return out


def gen_shop_specific():
    """Known vulnerable e-commerce platforms"""
    out = []
    # PrestaShop
    out.append('inurl:"/product.php?id="')
    out.append('inurl:"/category.php?id="')
    out.append('inurl:"/cms.php?id="')
    # OpenCart
    out.append('inurl:"index.php?route=product/product"')
    out.append('inurl:"index.php?route=product/category"')
    out.append('inurl:"index.php?route=information/information"')
    out.append('inurl:"index.php?route=common/home" inurl:"&product_id="')
    # Magento
    out.append('inurl:"/catalog/product/view/id/"')
    out.append('inurl:"/catalog/category/view/id/"')
    # WooCommerce (WordPress)
    out.append('inurl:"/product/" inurl:"/?add-to-cart="')
    out.append('inurl:"/?s=" inurl:"/wp-content/"')
    out.append('inurl:"/wp-content/plugins/" inurl:"?id="')
    # osCommerce / Zen Cart
    out.append('inurl:"/product_info.php?products_id="')
    out.append('inurl:"/index.php?cPath="')
    out.append('inurl:"/index.php?main_page="')
    # Custom PHP shops
    out.append('inurl:"/shop.php?id="')
    out.append('inurl:"/item.php?id="')
    out.append('inurl:"/detail.php?id="')
    out.append('inurl:"/view.php?id="')
    out.append('inurl:"/show.php?id="')
    out.append('inurl:"/page.php?id="')
    out.append('inurl:"/content.php?id="')
    out.append('inurl:"/news.php?id="')
    out.append('inurl:"/article.php?id="')
    out.append('inurl:"/post.php?id="')
    out.append('inurl:"/topic.php?id="')
    out.append('inurl:"/thread.php?id="')
    out.append('inurl:"/forum.php?id="')
    out.append('inurl:"/category.php?id="')
    out.append('inurl:"/products.php?id="')
    # ASP/.NET shops
    out.append('inurl:"/product.aspx?id="')
    out.append('inurl:"/default.aspx?id="')
    out.append('inurl:"/item.aspx?id="')
    out.append('inurl:"/view.aspx?id="')
    out.append('inurl:"/show.aspx?id="')
    out.append('inurl:"/details.aspx?id="')
    out.append('inurl:"/news.aspx?id="')
    out.append('inurl:"/article.aspx?id="')
    out.append('inurl:"/catalog.aspx?id="')
    # JSP shops
    out.append('inurl:".jsp?id="')
    out.append('inurl:".jsp?cat="')
    out.append('inurl:".jsp?page="')
    return out


def gen_cms_specific():
    """Known vulnerable CMS param patterns"""
    out = []
    # WordPress
    out.append('inurl:"/wp-content/" inurl:"?p="')
    out.append('inurl:"/wp-content/plugins/" inurl:"?file="')
    out.append('inurl:"/?p=" inurl:"/wp-"')
    out.append('inurl:"/?page_id=" inurl:"/wp-"')
    out.append('inurl:"/?cat=" inurl:"/wp-"')
    out.append('inurl:"/?s=" inurl:"/wp-"')
    out.append('inurl:"/?author=" inurl:"/wp-"')
    out.append('inurl:"/?tag=" inurl:"/wp-"')
    out.append('inurl:"/?attachment_id=" inurl:"/wp-"')
    # Joomla
    out.append('inurl:"/index.php?option=com_content" inurl:"&id="')
    out.append('inurl:"/index.php?option=com_" inurl:"&id="')
    out.append('inurl:"/index.php?option=com_" inurl:"&catid="')
    out.append('inurl:"/index.php?option=com_" inurl:"&Itemid="')
    out.append('inurl:"/index.php?option=com_" inurl:"&view="')
    out.append('inurl:"/index.php?option=com_virtuemart" inurl:"&product_id="')
    out.append('inurl:"/index.php?option=com_k2" inurl:"&id="')
    out.append('inurl:"/index.php?option=com_") inurl:"&task="')
    # Drupal
    out.append('inurl:"/node/" inurl:"?page="')
    out.append('inurl:"/taxonomy/term/" inurl:"?page="')
    # phpBB
    out.append('inurl:"/viewtopic.php?id="')
    out.append('inurl:"/viewforum.php?f="')
    out.append('inurl:"/posting.php?mode="')
    out.append('inurl:"/memberlist.php?mode="')
    out.append('inurl:"/profile.php?mode=" inurl:"&u="')
    out.append('inurl:"/search.php?keywords="')
    # vBulletin
    out.append('inurl:"/showthread.php?t="')
    out.append('inurl:"/forumdisplay.php?f="')
    out.append('inurl:"/member.php?u="')
    out.append('inurl:"/search.php?do="')
    out.append('inurl:"/newthread.php?do="')
    # SMF
    out.append('inurl:"/index.php?topic="')
    out.append('inurl:"/index.php?board="')
    out.append('inurl:"/index.php?action=profile" inurl:"&u="')
    out.append('inurl:"/index.php?action=post" inurl:"&topic="')
    # MyBB
    out.append('inurl:"/showthread.php?tid="')
    out.append('inurl:"/forumdisplay.php?fid="')
    # IPB / Invision
    out.append('inurl:"/index.php?showtopic="')
    out.append('inurl:"/index.php?showforum="')
    # Discuz / XMB / others
    out.append('inurl:"/forumdisplay.php?fid="')
    out.append('inurl:"/viewthread.php?tid="')
    return out


def gen_classic_dorks():
    """The classic Google Dork Bible list — proven winners"""
    return [
        # SQLi classics
        'inurl:"?id=" inurl:".php"',
        'inurl:"?id=" inurl:".asp"',
        'inurl:"?id=" inurl:".aspx"',
        'inurl:"?id=" inurl:".jsp"',
        'inurl:"?cat=" inurl:".php"',
        'inurl:"?cat=" inurl:".asp"',
        'inurl:"?cat=" inurl:".aspx"',
        'inurl:"?cat=" inurl:".jsp"',
        'inurl:"?page=" inurl:".php"',
        'inurl:"?page=" inurl:".asp"',
        'inurl:"?page=" inurl:".aspx"',
        'inurl:"?view=" inurl:".php"',
        'inurl:"?show=" inurl:".php"',
        'inurl:"?item=" inurl:".php"',
        'inurl:"?product=" inurl:".php"',
        'inurl:"?news=" inurl:".php"',
        'inurl:"?article=" inurl:".php"',
        'inurl:"?topic=" inurl:".php"',
        'inurl:"?thread=" inurl:".php"',
        'inurl:"?forum=" inurl:".php"',
        'inurl:"?search=" inurl:".php"',
        'inurl:"?q=" inurl:".php"',
        'inurl:"?s=" inurl:".php"',
        'inurl:"?query=" inurl:".php"',
        'inurl:"?keyword=" inurl:".php"',
        'inurl:"?file=" inurl:".php"',
        'inurl:"?path=" inurl:".php"',
        'inurl:"?dir=" inurl:".php"',
        'inurl:"?folder=" inurl:".php"',
        'inurl:"?include=" inurl:".php"',
        'inurl:"?template=" inurl:".php"',
        'inurl:"?page_id=" inurl:"/wp-"',
        'inurl:"?post_id=" inurl:".php"',
        'inurl:"?user=" inurl:".php"',
        'inurl:"?username=" inurl:".php"',
        'inurl:"?email=" inurl:".php"',
        'inurl:"?login=" inurl:".php"',
        'inurl:"?name=" inurl:".php"',
        'inurl:"?action=" inurl:".php"',
        'inurl:"?do=" inurl:".php"',
        'inurl:"?module=" inurl:".php"',
        'inurl:"?mod=" inurl:".php"',
        'inurl:"?lang=" inurl:".php"',
        'inurl:"?locale=" inurl:".php"',
        'inurl:"?type=" inurl:".php"',
        'inurl:"?sort=" inurl:".php"',
        'inurl:"?order=" inurl:".php"',
        'inurl:"?by=" inurl:".php"',
        'inurl:"?date=" inurl:".php"',
        'inurl:"?year=" inurl:".php"',
        'inurl:"?month=" inurl:".php"',
        'inurl:"?day=" inurl:".php"',
        # Google Dork Bible volume 2
        'inurl:"products.php?cat="',
        'inurl:"products.php?cat=" inurl:.php',
        'inurl:"products.php?id="',
        'inurl:"product.php?cat="',
        'inurl:"product.php?id="',
        'inurl:"news.php?id="',
        'inurl:"news.php?cat="',
        'inurl:"news.php?lang="',
        'inurl:"article.php?id="',
        'inurl:"article.php?lang="',
        'inurl:"topic.php?id="',
        'inurl:"thread.php?id="',
        'inurl:"forum.php?id="',
        'inurl:"category.php?id="',
        'inurl:"category.php?cat="',
        'inurl:"gallery.php?id="',
        'inurl:"image.php?id="',
        'inurl:"photo.php?id="',
        'inurl:"media.php?id="',
        'inurl:"file.php?id="',
        'inurl:"download.php?id="',
        'inurl:"content.php?id="',
        'inurl:"detail.php?id="',
        'inurl:"info.php?id="',
        'inurl:"view.php?id="',
        'inurl:"show.php?id="',
        'inurl:"read.php?id="',
        'inurl:"print.php?id="',
        'inurl:"page.php?id="',
        'inurl:"home.php?id="',
        'inurl:"index.php?id="',
        'inurl:"default.php?id="',
        'inurl:"main.php?id="',
        'inurl:"test.php?id="',
        # ASP classic
        'inurl:"detail.asp?id="',
        'inurl:"show.asp?id="',
        'inurl:"view.asp?id="',
        'inurl:"content.asp?id="',
        'inurl:"news.asp?id="',
        'inurl:"article.asp?id="',
        'inurl:"product.asp?id="',
        'inurl:"item.asp?id="',
        'inurl:"category.asp?id="',
        'inurl:"page.asp?id="',
        'inurl:"forum.asp?id="',
        'inurl:"topic.asp?id="',
        # ASPX classic
        'inurl:"detail.aspx?id="',
        'inurl:"show.aspx?id="',
        'inurl:"view.aspx?id="',
        'inurl:"content.aspx?id="',
        'inurl:"news.aspx?id="',
        'inurl:"article.aspx?id="',
        'inurl:"product.aspx?id="',
        'inurl:"item.aspx?id="',
        'inurl:"category.aspx?id="',
        'inurl:"page.aspx?id="',
        'inurl:"default.aspx?id="',
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", required=True, help="output file path")
    ap.add_argument("--verticals", nargs="*", default=list(VERTICALS.keys()),
                    help="which verticals to include")
    ap.add_argument("--no-basic", action="store_true", help="skip basic param dorks")
    ap.add_argument("--no-cms", action="store_true", help="skip CMS-specific dorks")
    ap.add_argument("--no-shops", action="store_true", help="skip shop-specific dorks")
    ap.add_argument("--no-combos", action="store_true", help="skip param-combo dorks")
    args = ap.parse_args()

    all_dorks = set()
    all_dorks.update(gen_classic_dorks())

    if not args.no_basic:
        all_dorks.update(gen_basic_params())
    if not args.no_cms:
        all_dorks.update(gen_cms_specific())
    if not args.no_shops:
        all_dorks.update(gen_shop_specific())
    if not args.no_combos:
        all_dorks.update(gen_param_combos())

    for v in args.verticals:
        if v in VERTICALS:
            # Only top 20 params per vertical to keep dork count manageable
            for p in PARAMS[:20]:
                for ext in ("php", "asp", "aspx"):
                    for kw in VERTICALS[v][:5]:
                        all_dorks.add(f'inurl:"{kw}" inurl:"?{p}=" inurl:.{ext}')

    # Dedup + sort
    dorks = sorted(all_dorks)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(dorks) + "\n", encoding="utf-8")
    print(f"[+] {len(dorks)} dorks written to {out}")
    print(f"[+] Verticals: {args.verticals}")
    print(f"[+] Estimated URL yield (Bing, 2 pages/dork): {len(dorks) * 20} URLs")
    print(f"[+] Estimated unique: ~{len(dorks) * 10} URLs")


if __name__ == "__main__":
    main()
