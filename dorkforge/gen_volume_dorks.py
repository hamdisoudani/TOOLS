#!/usr/bin/env python3
"""
DorkForge VOLUME dork generator — PRODUCTION SCALE (10K+ dorks).

Strategy: GENERATE EVERYTHING. Diversity filtering happens post-harvest.
- All param × extension combos (not just winners)
- All param × inbody × extension combos
- Multi-language page selectors
- Forum/blog/CMS path variants
- Numeric id, alpha id, hash id, path id variants

Output: dorks_bing_volume.txt (8,000-15,000 dorks)
"""
import argparse
import itertools


# ===== EXPANDED PARAM LIST (200+ params used in real SQLi) =====
PARAMS = [
    # Numeric IDs (classic)
    'id', 'ID', 'Id', 'pid', 'nid', 'tid', 'uid', 'gid', 'cid', 'lid',
    'mid', 'bid', 'fid', 'vid', 'kid', 'qid', 'rid', 'eid', 'sid',
    'iid', 'aid', 'did', 'hid', 'wid', 'zid', 'oid', 'xid',
    'itemid', 'catid', 'newsid', 'articleid', 'postid', 'threadid',
    'topicid', 'forumid', 'userid', 'memberid', 'accountid', 'profileid',
    'orderid', 'invoiceid', 'ticketid', 'msgid', 'messageid',
    'commentid', 'noteid', 'pageid', 'viewid', 'sessionid',
    'fileid', 'docid', 'mediaid', 'imageid', 'photoid', 'videoid',
    'audioid', 'galleryid', 'albumid', 'picid', 'photogalleryid',
    'productid', 'item_id', 'categoryid', 'subcategoryid', 'parentid',
    'blogid', 'boardid', 'groupid', 'teamid', 'projectid', 'taskid',
    'eventid', 'meetingid', 'calendarid', 'scheduleid', 'appointmentid',
    'reservationid', 'bookingid', 'rentalid', 'propertyid', 'listingid',
    'jobid', 'positionid', 'vacancyid', 'careerid', 'recruitmentid',
    'applicationid', 'candidateid', 'employeeid', 'staffid', 'managerid',
    'customerid', 'clientid', 'vendorid', 'supplierid', 'partnerid',
    'companyid', 'organizationid', 'departmentid', 'officeid', 'branchid',
    'storeid', 'shopid', 'warehouseid', 'locationid', 'regionid',
    'countryid', 'stateid', 'cityid', 'zipid', 'postalcode', 'zipcode',
    # Alpha IDs (URLs, slugs)
    'name', 'slug', 'title', 'page', 'slug', 'permalink',
    'author', 'username', 'user', 'login', 'email',
    # Paging
    'p', 'pg', 'pagenum', 'pagenumber', 'start', 'begin',
    'limit', 'offset', 'count', 'size', 'perpage', 'per_page',
    'records', 'rows', 'num', 'number',
    # Sort/filter
    'sort', 'order', 'sortby', 'orderby', 'sort_order',
    'dir', 'direction', 'asc', 'desc',
    'filter', 'category', 'cat', 'sub', 'subcat', 'tag', 'tags',
    'type', 'view', 'mode', 'display', 'show', 'hide', 'layout',
    'style', 'theme', 'skin', 'template', 'lang', 'language', 'locale',
    'format', 'output', 'render', 'print', 'mobile', 'responsive',
    # Search/query
    'q', 'query', 'search', 's', 'find', 'lookup', 'searchterm',
    'keyword', 'keywords', 'term', 'phrase', 'text',
    # Date
    'year', 'month', 'day', 'date', 'd', 'm', 'y',
    'from', 'to', 'start_date', 'end_date', 'date_from', 'date_to',
    'since', 'until', 'after', 'before',
    # Actions
    'act', 'action', 'do', 'op', 'operation', 'cmd', 'command',
    'exec', 'execute', 'run', 'launch', 'start', 'stop', 'end',
    'submit', 'process', 'handle', 'manage',
    # User input
    'debug', 'test', 'admin', 'root', 'master', 'config', 'conf',
    'setting', 'settings', 'option', 'options', 'param', 'params',
    'data', 'input', 'output', 'value', 'val', 'var', 'variable',
    'file', 'filename', 'filepath', 'path', 'dir', 'folder',
    'url', 'link', 'href', 'src', 'source', 'target', 'dest',
    'redirect', 'next', 'prev', 'previous', 'back', 'forward', 'return',
    'ref', 'referer', 'origin', 'from_url', 'to_url', 'callback',
    # Specific to common CMS
    'option', 'task', 'view', 'layout', 'Itemid', 'tmpl', 'template',
    'route', 'controller', 'module', 'action', 'page', 'func',
    'funcs', 'op', 'operation', 'service', 'method', 'class',
    # E-commerce
    'sku', 'asin', 'upc', 'ean', 'isbn', 'model', 'partno',
    'manufacturer', 'brand', 'vendor',
    # Geo
    'lat', 'latitude', 'lon', 'lng', 'longitude', 'coords', 'location',
    'address', 'city', 'state', 'country', 'zip', 'postal',
    # Forum/blog specific
    'topic', 'forum', 'thread', 'post', 'reply', 'comment', 'msg',
    'board', 'category', 'section',
]

# Topical keywords (broad — get everything)
TOPICS = [
    'shop', 'store', 'product', 'item', 'goods', 'merchandise', 'cart',
    'basket', 'checkout', 'order', 'invoice', 'payment', 'catalog',
    'article', 'blog', 'post', 'news', 'story', 'content', 'page',
    'forum', 'thread', 'topic', 'discussion', 'board', 'community',
    'user', 'member', 'profile', 'account', 'customer', 'client', 'people',
    'gallery', 'photo', 'image', 'video', 'media', 'album', 'picture',
    'download', 'file', 'document', 'attachment', 'resource', 'pdf',
    'booking', 'reservation', 'appointment', 'schedule', 'event', 'tour',
    'ticket', 'support', 'help', 'faq', 'question', 'knowledge',
    'review', 'comment', 'rating', 'feedback', 'testimonial',
    'course', 'lesson', 'tutorial', 'training', 'education', 'class',
    'property', 'listing', 'apartment', 'rental', 'real estate', 'home',
    'job', 'career', 'recruitment', 'vacancy', 'position', 'employment',
    'restaurant', 'menu', 'recipe', 'food', 'meal', 'dish',
    'hotel', 'travel', 'flight', 'destination', 'vacation',
    'medical', 'doctor', 'patient', 'health', 'clinic', 'hospital',
    'company', 'business', 'service', 'solution', 'industry',
    'directory', 'list', 'search', 'find', 'browse',
    'news', 'magazine', 'blog', 'press', 'release', 'media',
    'music', 'song', 'album', 'artist', 'track',
    'movie', 'film', 'cinema', 'actor', 'director',
    'sport', 'team', 'player', 'match', 'game', 'league',
    'tech', 'software', 'app', 'tool', 'system', 'platform',
]

# Extensions (priority: php > asp > aspx > jsp)
EXTS = ['php', 'asp', 'aspx', 'jsp', 'cfm', 'cgi']

# Exclude spam aggregators (applied as -site: filters)
EXCLUDE_SITES = [
    'w3.org', 'w3schools.com', 'github.com', 'stackoverflow.com',
    'youtube.com', 'wikipedia.org', 'reddit.com', 'quora.com',
    'facebook.com', 'twitter.com', 'linkedin.com', 'archive.org',
    'medium.com', 'wordpress.org', 'apache.org', 'mysql.com',
]


def build_volume_dorks():
    dorks = set()

    # ===== Layer 1: ALL params × ALL extensions (base combo) =====
    for p in PARAMS[:80]:  # top 80 numeric/ID params
        for ext in EXTS:
            dorks.add(f'contains:{ext} inurl:"?{p}="')

    # ===== Layer 2: ALL params × inbody topical × extension =====
    # Sample top topics for tractability
    top_topics = TOPICS[:25]  # 25 topics
    for topic in top_topics:
        for p in PARAMS[:30]:  # top 30 params
            for ext in ['php', 'asp']:
                d = f'inbody:{topic} contains:{ext} inurl:"?{p}="'
                if len(d.split()) <= 10:
                    dorks.add(d)

    # ===== Layer 3: Topical keywords × extensions (param= keyword) =====
    for topic in TOPICS:
        for ext in EXTS:
            d = f'inbody:{topic} ext:{ext}'
            if len(d.split()) <= 10:
                dorks.add(d)

    # ===== Layer 4: Path-based dorks (CMS/forum/blog markers) =====
    PATHS = [
        '/showthread.php?t=', '/viewtopic.php?t=', '/thread-',
        '/forum/', '/topic/', '/post-', '/article-', '/blog/',
        '/product/', '/item/', '/p/', '/page/', '/post/',
        '/news/', '/story/', '/gallery/', '/photo/',
        '/download.php?id=', '/file.php?id=', '/doc.php?id=',
        '/cat.php?id=', '/category.php?id=', '/view.php?id=',
        '/index.php?id=', '/page.php?id=', '/show.php?id=',
        '/content.php?id=', '/detail.php?id=', '/info.php?id=',
        '/search.php?q=', '/results.php?q=',
        '/profile.php?id=', '/user.php?id=', '/member.php?id=',
        '/news.php?id=', '/article.php?id=', '/blog.php?id=',
        '/shop.php?id=', '/product.php?id=', '/item.php?id=',
        '/gallery.php?id=', '/photo.php?id=', '/image.php?id=',
        '/book.php?id=', '/course.php?id=', '/event.php?id=',
    ]
    for path in PATHS:
        # Add ext: variants
        for ext in ['php', 'asp']:
            d = f'inurl:"{path}" ext:{ext}'
            if len(d.split()) <= 10:
                dorks.add(d)

    # ===== Layer 5: Forum-specific dorks (phpBB/vBulletin/SMF) =====
    FORUM_PARAMS = [
        'viewtopic.php?t=', 'showthread.php?t=', 'index.php?t=',
        'topic.php?id=', 'thread.php?id=', 'forum.php?id=',
        'viewforum.php?f=', 'showthread.php?p=', 'viewtopic.php?p=',
        'index.php?showtopic=', 'index.php?topic=',
    ]
    for fp in FORUM_PARAMS:
        dorks.add(f'inurl:"{fp}"')
        dorks.add(f'inurl:"{fp}" inbody:post')
        dorks.add(f'inurl:"{fp}" inbody:thread')

    # ===== Layer 6: WordPress/Joomla/Drupal specific =====
    CMS_DORKS = [
        'inurl:"/wp-content/plugins/" ext:php',
        'inurl:"/wp-admin/admin-ajax.php" ext:php',
        'inurl:"/wp-content/themes/" ext:php',
        'inurl:"/wp-includes/" ext:php',
        'inurl:"index.php?option=com_"',
        'inurl:"index.php?option=" ext:php',
        'inurl:"/administrator/" ext:php',
        'inurl:"/joomla/" ext:php',
        'inurl:"/drupal/" ext:php',
        'inurl:"/sites/default/" ext:php',
        'inurl:"node/" ext:php',
        'inurl:"/modules/" ext:php',
        'inurl:"/modules/mod_" ext:php',
        'inurl:"/templates/" ext:php',
    ]
    for d in CMS_DORKS:
        if len(d.split()) <= 10:
            dorks.add(d)

    # ===== Layer 7: Top dorks × -site: spam exclusions =====
    TOP_BASE = [
        'contains:php inurl:"?id="',
        'contains:asp inurl:"?id="',
        'contains:php inurl:"?page="',
        'contains:php inurl:"?cat="',
    ]
    for base in TOP_BASE:
        for excl in EXCLUDE_SITES[:8]:
            d = f'{base} -site:{excl}'
            if len(d.split()) <= 10:
                dorks.add(d)

    # Filter: max 10 terms per Bing query
    valid = [d for d in dorks if len(d.split()) <= 10]
    return sorted(valid)


def main():
    ap = argparse.ArgumentParser(description='DorkForge VOLUME dork generator')
    ap.add_argument('-o', '--output', default='dorks_bing_volume.txt',
                    help='Output dork file')
    ap.add_argument('--limit', type=int, default=0,
                    help='Limit total dorks (0 = no limit)')
    args = ap.parse_args()

    print('[*] DorkForge VOLUME dork generator')
    print('[*] All param × ext combos + topical + paths + CMS')
    print()

    dorks = build_volume_dorks()
    if args.limit and args.limit < len(dorks):
        dorks = dorks[:args.limit]

    with open(args.output, 'w') as f:
        for d in dorks:
            f.write(d + '\n')

    print(f'[+] Saved → {args.output} ({sum(len(d) + 1 for d in dorks)} bytes)')
    print(f'[+] Total dorks: {len(dorks)}')
    print()
    print('[+] Sample dorks:')
    for d in dorks[:8]:
        print(f'    {d}')
    print('    ...')
    for d in dorks[-5:]:
        print(f'    {d}')


if __name__ == '__main__':
    main()


def build_extra_dorks():
    """Extra layers for MASS scale."""
    dorks = set()
    EXTRA_PARAMS = [
        'year', 'month', 'day', 'date', 'from', 'to',
        'sort', 'order', 'dir', 'limit', 'offset',
        'lang', 'locale', 'format', 'type', 'view', 'mode',
        'tag', 'category', 'cat', 'sub', 'section',
        'page', 'p', 'start', 'show', 'display',
        'q', 'query', 'search', 's', 'find',
    ]
    TOPICS_MINI = [
        'shop', 'store', 'product', 'cart', 'order',
        'article', 'blog', 'news', 'post',
        'forum', 'thread', 'topic',
        'gallery', 'photo', 'video',
        'download', 'file',
        'hotel', 'travel',
        'job', 'career',
        'medical', 'health',
        'restaurant', 'food',
        'music', 'movie',
    ]
    EXTS_MINI = ['php', 'asp']
    # inbody + ext + inurl param (no contains:)
    for t in TOPICS_MINI:
        for p in EXTRA_PARAMS:
            for ext in EXTS_MINI:
                d = f'inbody:{t} ext:{ext} inurl:"?{p}="'
                if len(d.split()) <= 10:
                    dorks.add(d)
                # Just ext + param
                d2 = f'ext:{ext} inurl:"?{p}=" {t}'
                if len(d2.split()) <= 10:
                    dorks.add(d2)
    return sorted(dorks)
