// DorkForge Harvester - Content Script
// Runs on search engine result pages. Extracts URLs and posts to background.

(function () {
  'use strict';

  const ENGINE = detectEngine();
  const DEBOUNCE_MS = 1200;
  const MAX_RUNTIME_MS = 25000;  // safety cap

  if (!ENGINE) return;

  // Debounced extraction + send
  let debounceTimer = null;
  let sent = false;  // only send once per page load
  const startTime = Date.now();

  const observer = new MutationObserver(() => {
    if (sent) return;
    if (Date.now() - startTime > MAX_RUNTIME_MS) {
      observer.disconnect();
      return;
    }
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(tryExtract, DEBOUNCE_MS);
  });

  observer.observe(document.body, { childList: true, subtree: true });
  // Also try on initial load after small delay
  setTimeout(tryExtract, 2500);

  function detectEngine() {
    const host = location.hostname;
    if (host.includes('google.')) return 'google';
    if (host.includes('bing.com')) return 'bing';
    if (host.includes('duckduckgo.com')) return 'ddg';
    if (host.includes('yahoo.com')) return 'yahoo';
    if (host.includes('startpage.com')) return 'startpage';
    return null;
  }

  function tryExtract() {
    if (sent) return;
    const rawUrls = extractUrls();
    // Decode HTML entities on raw URLs (cite tags often have &amp;)
    const urls = rawUrls.map(decodeEntities).filter(Boolean);
    if (urls.length === 0) return;

    sent = true;
    const dork = extractDork();
    const page = extractPageNumber();
    console.log(`[DF] Extracted ${urls.length} URLs from ${ENGINE} (dork="${dork.slice(0, 50)}...", page=${page})`);
    chrome.runtime.sendMessage({
      type: 'URLS_EXTRACTED',
      payload: {
        urls,
        engine: ENGINE,
        dork,
        page
      }
    });
  }

  function extractDork() {
    try {
      const u = new URL(location.href);
      return u.searchParams.get('q') || u.searchParams.get('p') || u.searchParams.get('query') || '';
    } catch (e) {
      return '';
    }
  }

  function extractPageNumber() {
    try {
      const u = new URL(location.href);
      const start = parseInt(u.searchParams.get('start') || '0', 10);
      const first = parseInt(u.searchParams.get('first') || '1', 10);
      const b = parseInt(u.searchParams.get('b') || '1', 10);
      const pg = parseInt(u.searchParams.get('page') || '1', 10);
      const s = parseInt(u.searchParams.get('s') || '0', 10);
      if (start) return Math.floor(start / 10) + 1;
      if (first) return Math.floor((first - 1) / 10) + 1;
      if (b) return Math.floor((b - 1) / 10) + 1;
      if (pg) return pg;
      if (s) return Math.floor(s / 30) + 1;
      return 1;
    } catch (e) {
      return 1;
    }
  }

  function extractUrls() {
    const out = new Set();
    try {
      if (ENGINE === 'google') {
        // Modern Google result anchors (2024-2026 layout)
        // Selector strategy: any anchor inside a result block, with several layout fallbacks
        const sel = [
          'div.g a[href^="http"]:not([role="button"])',
          'div.yuRUbf > a[href^="http"]',
          'div[jscontroller] a[href^="http"]:not([role="button"])',
          'h3 + div a[href^="http"]',
          'a[data-ved][href^="http"]:not([role="button"])',
          'div.kCrYT > a[href^="http"]',
          'div.MUxGbd a[href^="http"]',
          'div.v5yQqb a[href^="http"]',
          'div.ZINbbc a[href^="http"]'
        ].join(', ');
        document.querySelectorAll(sel).forEach((a) => {
          const href = a.href;
          if (isResultHref(href)) out.add(href);
        });
        // Fallback: cite tags (sometimes wrap the display URL)
        document.querySelectorAll('cite').forEach((c) => {
          const u = c.textContent.trim();
          if (u) out.add(ensureScheme(decodeEntities(u)));
        });
      } else if (ENGINE === 'bing') {
        document.querySelectorAll('li.b_algo h2 a[href], li.b_algo a.tilk[href]').forEach((a) => {
          if (isResultHref(a.href)) out.add(a.href);
        });
        // cite tag fallback (Bing often wraps URL in <cite>)
        document.querySelectorAll('li.b_algo cite').forEach((c) => {
          const u = c.textContent.trim();
          if (u) out.add(ensureScheme(u));
        });
      } else if (ENGINE === 'ddg') {
        document.querySelectorAll('a.result__a[href], a.result__url[href]').forEach((a) => {
          if (isResultHref(a.href)) out.add(a.href);
        });
        document.querySelectorAll('a.result__snippet').forEach((a) => {
          // snippet links sometimes have URLs
        });
      } else if (ENGINE === 'yahoo') {
        document.querySelectorAll('div.dd.algo a.d-ib.fz-20.lh-26.fw-b, h3.title a[href]').forEach((a) => {
          if (isResultHref(a.href)) out.add(a.href);
        });
      } else if (ENGINE === 'startpage') {
        document.querySelectorAll('a.w-gl__result-title, a.w-gl__result-url').forEach((a) => {
          if (isResultHref(a.href)) out.add(a.href);
        });
      }
    } catch (e) {
      console.error('[DF] extract error', e);
    }
    return Array.from(out);
  }

  function isResultHref(href) {
    if (!href) return false;
    // Skip search engine internal links
    const skip = ['google.com/search', 'google.com/preferences', 'google.com/advanced_search',
      'accounts.google', 'support.google', 'maps.google', 'bing.com/account', 'bing.com/profile',
      'duckduckgo.com/settings', 'duckduckgo.com/?q=', 'duckduckgo.com/html',
      'login.yahoo.com', 'login.live.com'];
    if (skip.some((s) => href.includes(s))) return false;
    // Skip javascript: / mailto: / anchors
    if (!/^https?:\/\//i.test(href)) return false;
    return true;
  }

  function ensureScheme(u) {
    if (/^https?:\/\//i.test(u)) return u;
    return 'http://' + u;
  }

  // Decode HTML entities that often appear in cite tags / textContent of result snippets
  function decodeEntities(s) {
    if (!s) return s;
    return s
      .replace(/&amp;/g, '&')
      .replace(/&#38;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/&nbsp;/g, ' ')
      .trim();
  }
})();