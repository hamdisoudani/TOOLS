#!/usr/bin/env python3
"""
DorkForge PROD dork generator — PRODUCTION PHASE.

Builds on v3.1 yield data. Strategy:
- Take HIGH-YIELD base dorks from v3.1 analysis
- Expand each with ALL related param/keyword/extension variants
- Filter out dorks > 10 terms (Bing limit)
- Output: dorks_bing_prod.txt (3,000-5,000 dorks)
"""
import argparse
import itertools

# ===== HIGH-YIELD BASE DORKS (v3.1 winners, sorted by scripted yield) =====
BASE_DORKS = [
    # Tier S: 5-7x scripted yield (proven winners)
    'contains:asp inurl:"?nid="',
    'contains:asp inurl:"?id="',
    'contains:asp inurl:"?product="',
    'contains:jsp inurl:"?userid="',
    'contains:php inurl:"?nid="',
    'contains:php inurl:"?tid="',
    'contains:asp inurl:"?exec="',
    'contains:asp inurl:"?thread="',
    'contains:asp inurl:"?video="',
    'contains:jsp inurl:"?nid="',
    'contains:php inurl:"?photo="',
    'contains:php inurl:"?thread="',
    'contains:asp inurl:"?userid="',
    'contains:asp inurl:"?booking_id="',
    'contains:asp inurl:"?cat="',
    'contains:php inurl:"?product="',
    'contains:php inurl:"?page="',
    'contains:php inurl:"?cat="',
    'contains:jsp inurl:"?id="',
    'contains:jsp inurl:"?page="',
    'contains:jsp inurl:"?tid="',
    'contains:aspx inurl:"?id="',
    'contains:aspx inurl:"?nid="',
    'contains:aspx inurl:"?tid="',
    'contains:aspx inurl:"?cat="',
    'contains:cfm inurl:"?id="',
    'contains:cfm inurl:"?nid="',
    'contains:cgi inurl:"?id="',
    'contains:cgi inurl:"?nid="',
    # Tier A: 3-4x scripted yield
    'contains:php inurl:"?userid="',
    'contains:php inurl:"?booking_id="',
    'contains:php inurl:"?video="',
    'contains:php inurl:"?pid="',
    'contains:php inurl:"?article="',
    'contains:php inurl:"?news_id="',
    'contains:php inurl:"?item="',
    'contains:php inurl:"?doc="',
    'contains:php inurl:"?file="',
    'contains:php inurl:"?download="',
    'contains:php inurl:"?img="',
    'contains:php inurl:"?p="',
    'contains:php inurl:"?post="',
    'contains:php inurl:"?story="',
    'contains:php inurl:"?q="',
    'contains:php inurl:"?search="',
    'contains:asp inurl:"?pid="',
    'contains:asp inurl:"?uid="',
    'contains:asp inurl:"?article="',
    'contains:asp inurl:"?news_id="',
    'contains:asp inurl:"?item="',
    'contains:asp inurl:"?doc="',
    'contains:asp inurl:"?file="',
    'contains:asp inurl:"?download="',
    'contains:asp inurl:"?p="',
    'contains:asp inurl:"?post="',
    'contains:asp inurl:"?q="',
    'contains:asp inurl:"?search="',
    'contains:asp inurl:"?act="',
    'contains:asp inurl:"?do="',
    'contains:asp inurl:"?cmd="',
    'contains:asp inurl:"?cmd=',
    'contains:jsp inurl:"?cat="',
    'contains:jsp inurl:"?pid="',
    'contains:jsp inurl:"?q="',
    'contains:jsp inurl:"?search="',
    'contains:jsp inurl:"?article="',
    'contains:jsp inurl:"?doc="',
    'contains:jsp inurl:"?file="',
    'contains:jsp inurl:"?download="',
    'contains:jsp inurl:"?act="',
    'contains:jsp inurl:"?do="',
    'contains:aspx inurl:"?q="',
    'contains:aspx inurl:"?userid="',
    'contains:aspx inurl:"?cat="',
    'contains:aspx inurl:"?act="',
    'contains:aspx inurl:"?do="',
    'contains:aspx inurl:"?pid="',
    'contains:aspx inurl:"?uid="',
    'contains:aspx inurl:"?p="',
    'contains:aspx inurl:"?file="',
    'contains:aspx inurl:"?download="',
    'contains:cfm inurl:"?tid="',
    'contains:cfm inurl:"?cat="',
    'contains:cfm inurl:"?pid="',
    'contains:cfm inurl:"?userid="',
    'contains:cgi inurl:"?tid="',
    'contains:cgi inurl:"?cat="',
    'contains:cgi inurl:"?pid="',
    'contains:cgi inurl:"?userid="',
]

# Additional high-yield expansion params not yet tested in v3.1
EXPANSION_PARAMS = [
    'article_id', 'blog_id', 'board_id', 'topic_id', 'forum_id',
    'user_id', 'member_id', 'account_id', 'profile_id', 'customer_id',
    'order_id', 'invoice_id', 'ticket_id', 'msg_id', 'message_id',
    'comment_id', 'note_id', 'page_id', 'view_id', 'session_id',
    'lang', 'language', 'locale', 'country', 'region',
    'keyword', 'query', 'term', 'phrase', 'name',
    'email', 'phone', 'mobile', 'contact',
    'year', 'month', 'day', 'date', 'date_from', 'date_to',
    'start', 'end', 'from', 'to', 'limit', 'offset', 'sort', 'order',
    'filter', 'category', 'subcat', 'subcategory', 'tag', 'tags',
    'mode', 'view', 'display', 'show', 'hide', 'action', 'act', 'op',
    'debug', 'test', 'admin', 'root', 'master', 'config',
    'file_id', 'doc_id', 'media_id', 'image_id', 'video_id', 'audio_id',
    'gallery_id', 'album_id', 'photo_id', 'pic_id',
    'newsid', 'articleid', 'productid', 'userid', 'orderid',
]

# High-yield topical keywords (e-commerce + content + forums)
TOPICAL_KEYWORDS = [
    'shop', 'store', 'product', 'item', 'goods', 'merchandise',
    'cart', 'basket', 'checkout', 'order', 'invoice', 'payment',
    'article', 'blog', 'post', 'news', 'story', 'content',
    'forum', 'thread', 'topic', 'discussion', 'board', 'community',
    'user', 'member', 'profile', 'account', 'customer', 'client',
    'gallery', 'photo', 'image', 'video', 'media', 'album',
    'download', 'file', 'document', 'attachment', 'resource',
    'booking', 'reservation', 'appointment', 'schedule', 'event',
    'ticket', 'support', 'help', 'faq', 'question',
    'review', 'comment', 'rating', 'feedback', 'testimonial',
    'course', 'lesson', 'tutorial', 'training', 'education',
    'property', 'real estate', 'listing', 'apartment', 'rental',
    'job', 'career', 'recruitment', 'vacancy', 'position',
    'restaurant', 'menu', 'recipe', 'food', 'meal',
    'hotel', 'travel', 'flight', 'tour', 'destination',
    'medical', 'doctor', 'patient', 'health', 'clinic',
]

# Extensions (priority order: asp > php > aspx > jsp > cfm > cgi)
EXTS = ['asp', 'php', 'aspx', 'jsp', 'cfm', 'cgi']

# Sites/paths that should be excluded (SEO spam aggregators)
EXCLUDE_PATTERNS = [
    '-site:w3.org', '-site:github.com', '-site:stackoverflow.com',
    '-site:wordpress.org', '-site:youtube.com', '-site:wikipedia.org',
    '-site:medium.com', '-site:reddit.com', '-site:quora.com',
    '-site:facebook.com', '-site:twitter.com', '-site:linkedin.com',
    '-site:archive.org', '-site:sourceforge.net', '-site:apache.org',
]


def build_dorks():
    """Build the production dork list from base + expansions."""
    dorks = set()

    # Layer 1: All base dorks (86 from v3.1)
    for d in BASE_DORKS:
        dorks.add(d)

    # Layer 2: Topical keywords + high-yield param combos
    for kw in TOPICAL_KEYWORDS[:30]:  # top 30 keywords
        for param in ['id', 'nid', 'tid', 'cat', 'product', 'page']:
            for ext in EXTS[:4]:  # asp, php, aspx, jsp
                d = f'inbody:{kw} inurl:"?{param}=" ext:{ext}'
                dorks.add(d)
                # contains: variant
                d = f'inbody:{kw} contains:{ext} inurl:"?{param}="'
                dorks.add(d)

    # Layer 3: Expansion params × all extensions (rare anti-spam combos)
    for param in EXPANSION_PARAMS:
        for ext in EXTS[:4]:
            d = f'contains:{ext} inurl:"?{param}="'
            dorks.add(d)

    # Layer 4: inbody combos with unusual params
    for kw in TOPICAL_KEYWORDS[:20]:
        for param in EXPANSION_PARAMS[:30]:
            for ext in ['asp', 'php']:
                d = f'inbody:{kw} contains:{ext} inurl:"?{param}="'
                dorks.add(d)

    # Layer 5: Top base dorks × exclusion filters
    top5 = BASE_DORKS[:5]
    for base in top5:
        for excl in EXCLUDE_PATTERNS[:5]:
            d = f'{base} {excl}'
            dorks.add(d)

    # Filter: max 10 terms per Bing query
    valid = []
    for d in dorks:
        terms = len(d.split())
        if terms <= 10:
            valid.append(d)

    return sorted(set(valid))


def main():
    ap = argparse.ArgumentParser(description='DorkForge PROD dork generator')
    ap.add_argument('-o', '--output', default='dorks_bing_prod.txt',
                    help='Output dork file')
    ap.add_argument('--limit', type=int, default=0,
                    help='Limit total dorks (0 = no limit)')
    args = ap.parse_args()

    print('[*] DorkForge PROD dork generator')
    print('[*] Base = 86 v3.1 winners + expansion params × all extensions')
    print()

    dorks = build_dorks()
    if args.limit and args.limit < len(dorks):
        dorks = dorks[:args.limit]

    with open(args.output, 'w') as f:
        for d in dorks:
            f.write(d + '\n')

    print(f'[+] Saved → {args.output} ({sum(len(d) + 1 for d in dorks)} bytes)')
    print(f'[+] Total dorks: {len(dorks)}')
    print()
    print('[+] LAYER BREAKDOWN:')
    print(f'    L1 (base v3.1 winners)    :   {len(BASE_DORKS)} dorks')
    print(f'    L2-5 (expansions)         : {len(dorks) - len(BASE_DORKS)} dorks')
    print()
    print('[+] Sample dorks:')
    for d in dorks[:5]:
        print(f'    {d}')
    print('    ...')
    for d in dorks[-5:]:
        print(f'    {d}')


if __name__ == '__main__':
    main()
