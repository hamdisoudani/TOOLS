// DorkForge Harvester - Background Service Worker
// Coordinates search queue + extraction across browser tabs

const QUEUE_KEY = 'df_queue';
const STATE_KEY = 'df_state';
const SETTINGS_KEY = 'df_settings';

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'URLS_EXTRACTED') {
    handleExtractedUrls(msg.payload, sender);
    sendResponse({ ok: true });
    return false;
  }
  if (msg.type === 'GET_STATE') {
    chrome.storage.local.get([STATE_KEY], (data) => {
      sendResponse({ ok: true, state: data[STATE_KEY] || defaultState() });
    });
    return true;
  }
  if (msg.type === 'GET_QUEUE') {
    chrome.storage.local.get([QUEUE_KEY], (data) => {
      sendResponse({ ok: true, queue: data[QUEUE_KEY] || [] });
    });
    return true;
  }
  if (msg.type === 'CLEAR_QUEUE') {
    chrome.storage.local.set({ [QUEUE_KEY]: [] });
    sendResponse({ ok: true });
    return false;
  }
  if (msg.type === 'EXPORT_URLS') {
    exportUrls(msg.payload).then((result) => {
      sendResponse({ ok: true, ...result });
    });
    return true;
  }
  if (msg.type === 'ENQUEUE_DORKS') {
    enqueueDorks(msg.dorks, msg.engine).then((result) => {
      sendResponse({ ok: true, ...result });
    });
    return true;
  }
  if (msg.type === 'PAUSE_HARVEST') {
    updateState({ paused: true });
    sendResponse({ ok: true });
    return false;
  }
  if (msg.type === 'RESUME_HARVEST') {
    updateState({ paused: false });
    drainQueue();
    sendResponse({ ok: true });
    return false;
  }
});

function defaultState() {
  return {
    running: false,
    paused: false,
    total_extracted: 0,
    total_dorks_processed: 0,
    current_engine: null,
    current_dork: null,
    last_error: null,
    session_start: null
  };
}

function defaultSettings() {
  return {
    pages_per_dork: 3,           // 1-10 (Google paginates via start=)
    delay_between_tabs_ms: 4500,  // human pace
    delay_between_dorks_ms: 2500,
    extract_strategy: 'a_href',   // 'a_href' | 'cite_tag' | 'both'
    extensions_filter: ['php', 'asp', 'aspx', 'jsp', 'cfm', 'cgi'],
    must_have_param: true,        // require ?param= in URL
    auto_paginate: true,
    auto_close_tabs: true
  };
}

function updateState(patch) {
  chrome.storage.local.get([STATE_KEY], (data) => {
    const cur = data[STATE_KEY] || defaultState();
    const next = { ...cur, ...patch };
    chrome.storage.local.set({ [STATE_KEY]: next });
  });
}

async function handleExtractedUrls(payload, sender) {
  // payload: { urls: string[], engine: string, dork: string, page: number }
  chrome.storage.local.get([QUEUE_KEY], async (data) => {
    const urls = data[QUEUE_KEY] || [];
    const filtered = filterUrls(payload.urls, await getSettings());
    const enriched = filtered.map((u) => ({
      url: u,
      engine: payload.engine,
      dork: payload.dork,
      page: payload.page,
      extracted_at: Date.now(),
      tab_id: sender.tab ? sender.tab.id : null
    }));
    urls.push(...enriched);
    chrome.storage.local.set({ [QUEUE_KEY]: urls });

    const state = await getState();
    updateState({ total_extracted: (state.total_extracted || 0) + enriched.length });

    if (enriched.length > 0) {
      console.log(`[DF] +${enriched.length} URLs from ${payload.engine} page ${payload.page}`);
    }
  });
}

function filterUrls(rawUrls, settings) {
  const seen = new Set();
  const out = [];
  for (const u of rawUrls) {
    let clean = u;
    try {
      const parsed = new URL(u);
      // Strip hash
      parsed.hash = '';
      // Normalize host (lowercase)
      parsed.hostname = parsed.hostname.toLowerCase();
      clean = parsed.toString();
    } catch (e) {
      continue;  // skip malformed
    }

    // HTML-entity decode (Bing wraps & as &amp; in cite tags sometimes)
    clean = clean.replace(/&amp;/g, '&').replace(/&#38;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');

    // Build a dedup key: lowercase path + sorted lowercase query keys
    let dedupKey;
    try {
      const p = new URL(clean);
      const pathLower = p.pathname.toLowerCase();
      const params = Array.from(p.searchParams.entries())
        .map(([k, v]) => [k.toLowerCase(), v])
        .sort((a, b) => a[0].localeCompare(b[0]));
      const queryNorm = params.map(([k, v]) => `${k}=${v}`).join('&');
      dedupKey = `${p.hostname}${pathLower}?${queryNorm}`;
    } catch (e) {
      dedupKey = clean.toLowerCase();
    }
    if (seen.has(dedupKey)) continue;
    seen.add(dedupKey);

    // extension filter (case-insensitive on path)
    if (settings.extensions_filter && settings.extensions_filter.length) {
      const path = (() => { try { return new URL(clean).pathname.toLowerCase(); } catch (e) { return ''; } })();
      const hasExt = settings.extensions_filter.some((ext) => path.endsWith('.' + ext.toLowerCase()));
      if (!hasExt) continue;
    }

    // require query param
    if (settings.must_have_param) {
      try {
        if (!new URL(clean).search) continue;
      } catch (e) {
        continue;
      }
    }

    out.push(clean);
  }
  return out;
}

async function getSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get([SETTINGS_KEY], (data) => {
      resolve({ ...defaultSettings(), ...(data[SETTINGS_KEY] || {}) });
    });
  });
}

async function getState() {
  return new Promise((resolve) => {
    chrome.storage.local.get([STATE_KEY], (data) => {
      resolve(data[STATE_KEY] || defaultState());
    });
  });
}

async function enqueueDorks(dorks, engine) {
  const queue = await new Promise((resolve) => {
    chrome.storage.local.get([QUEUE_KEY], (data) => {
      resolve(data[QUEUE_KEY] || []);
    });
  });

  // Generate a job list (dork × page)
  const settings = await getSettings();
  const jobs = [];
  for (const dork of dorks) {
    for (let page = 0; page < settings.pages_per_dork; page++) {
      jobs.push({ dork, engine, page, status: 'pending' });
    }
  }

  await chrome.storage.session.set({ 'df_jobs': jobs });
  updateState({
    running: true,
    paused: false,
    total_dorks_processed: 0,
    current_engine: engine,
    session_start: Date.now()
  });
  drainQueue();
  return { jobs_queued: jobs.length };
}

async function drainQueue() {
  const state = await getState();
  if (!state.running || state.paused) return;

  const jobs = (await chrome.storage.session.get('df_jobs')).df_jobs || [];
  const next = jobs.find((j) => j.status === 'pending');
  if (!next) {
    updateState({ running: false, current_dork: null });
    console.log('[DF] Queue drained.');
    return;
  }
  next.status = 'in_progress';
  await chrome.storage.session.set({ 'df_jobs': jobs });

  const url = buildSearchUrl(next.dork, next.engine, next.page);
  updateState({ current_dork: next.dork });
  console.log(`[DF] Tab: ${next.engine} p${next.page} → ${next.dork.slice(0, 60)}...`);

  // Open in a real background tab so content script runs with the user's cookies
  const tab = await chrome.tabs.create({ url, active: false });

  // Wait for the tab to finish loading, then give content.js a moment to extract
  chrome.tabs.onUpdated.addListener(function onUpdate(tabId, info) {
    if (tabId === tab.id && info.status === 'complete') {
      chrome.tabs.onUpdated.removeListener(onUpdate);
      setTimeout(async () => {
        // Paginate by changing start param + auto-close
        if (next.page + 1 < settings.pages_per_dork) {
          // handled automatically via page param
        }
        const settings = await getSettings();
        if (settings.auto_close_tabs) {
          try { await chrome.tabs.remove(tab.id); } catch (e) {}
        }
        // mark done
        const j2 = (await chrome.storage.session.get('df_jobs')).df_jobs || [];
        const item = j2.find((x) => x === next || (x.dork === next.dork && x.page === next.page && x.status === 'in_progress'));
        if (item) item.status = 'done';
        await chrome.storage.session.set({ 'df_jobs': j2 });
        const st = await getState();
        updateState({ total_dorks_processed: (st.total_dorks_processed || 0) + 1 });
        // Pace human
        setTimeout(drainQueue, settings.delay_between_tabs_ms);
      }, 3500);
    }
  });
}

function buildSearchUrl(dork, engine, page) {
  // page is 0-indexed
  switch (engine) {
    case 'google':
      // Google uses start= parameter, 10 results per page
      return `https://www.google.com/search?q=${encodeURIComponent(dork)}&start=${page * 10}&num=100`;
    case 'bing':
      // Bing uses first= parameter, 10 results per page (organic)
      return `https://www.bing.com/search?q=${encodeURIComponent(dork)}&first=${page * 10 + 1}&count=50`;
    case 'ddg':
      // DDG HTML version (more reliable for scraping)
      const ddgS = page * 30;
      return `https://html.duckduckgo.com/html/?q=${encodeURIComponent(dork)}&s=${ddgS}&dc=${ddgS + 30}`;
    case 'yahoo':
      return `https://search.yahoo.com/search?p=${encodeURIComponent(dork)}&b=${page * 10 + 1}&pz=10`;
    case 'startpage':
      return `https://www.startpage.com/do/search?q=${encodeURIComponent(dork)}&page=${page + 1}`;
    default:
      return `https://www.google.com/search?q=${encodeURIComponent(dork)}&start=${page * 10}`;
  }
}

async function exportUrls(payload) {
  // payload: { format: 'sqldumper'|'plain'|'json'|'csv', filename?: string, filter?: { tier?: string, limit?: number } }
  const urls = await new Promise((resolve) => {
    chrome.storage.local.get([QUEUE_KEY], (data) => {
      resolve(data[QUEUE_KEY] || []);
    });
  });

  let lines = [];
  const format = payload.format || 'sqldumper';

  if (format === 'sqldumper' || format === 'plain') {
    lines = urls.map((u) => u.url);
  } else if (format === 'json') {
    lines = [JSON.stringify(urls, null, 2)];
  } else if (format === 'csv') {
    lines = ['url,engine,dork,page,extracted_at'];
    for (const u of urls) {
      lines.push([u.url, u.engine, '"' + (u.dork || '').replace(/"/g, '""') + '"', u.page, new Date(u.extracted_at).toISOString()].join(','));
    }
  }

  const content = lines.join('\n');
  const filename = payload.filename || `dorkforge_${format}_${Date.now()}.${format === 'json' ? 'json' : format === 'csv' ? 'csv' : 'txt'}`;

  // Use Data URL approach to trigger a download without service worker fetch
  const dataUrl = 'data:text/plain;charset=utf-8,' + encodeURIComponent(content);
  const downloadId = await chrome.downloads.download({
    url: dataUrl,
    filename: filename,
    saveAs: false
  });

  return { download_id: downloadId, filename, count: urls.length, bytes: content.length };
}

// Initialize settings on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get([SETTINGS_KEY], (data) => {
    if (!data[SETTINGS_KEY]) {
      chrome.storage.local.set({ [SETTINGS_KEY]: defaultSettings() });
    }
  });
});