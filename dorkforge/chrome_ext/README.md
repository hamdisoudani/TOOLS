# DorkForge Harvester — Chrome Extension v0.1

**The simplest path to fresh SQLi URLs:** use YOUR browser, YOUR cookies, YOUR residential IP.

## Why this exists

Every datacenter-based scraper (Bing, DDG, Yandex, custom) hits the same wall: **the IP is burned**. CAPTCHA, 0 results, rate limits.

Dork Searcher V3 (DSV3) proved the workaround: it just opens the user's default browser via `ShellExecuteA` and lets them browse. But DSV3 is manual — one tab per dork, you click through results.

**This extension automates that pattern**:
- Runs in your real Chrome (your cookies, your IP, your fingerprint)
- Opens search results in background tabs
- Extracts URLs natively (no scraping patterns to break)
- Filters by extension + query param at extraction time
- Exports to SQLiDumper-ready `.txt` format
- Paginate 1-10 pages per dork
- Queue 1-1000+ dorks
- Pace human (4.5s per tab)

## Install

1. Open Chrome → `chrome://extensions/`
2. Toggle **Developer mode** ON (top right)
3. Click **Load unpacked**
4. Select this `chrome_ext/` folder
5. Pin the 🔥 icon to your toolbar

## Usage

1. Click the 🔥 icon → paste dorks (one per line)
2. Choose engine (Google recommended for residential IP)
3. Click **▶ Start** — background tabs start popping up
4. Let it run. URLs accumulate in the popup's "URLs" counter.
5. Click **📄 sqldumper.txt** to download `dorkforge_sqldumper_<timestamp>.txt`
6. Load that file in SQLiDumper.

**Default settings** (edit in extension storage):
- 3 pages per dork (10 results each = 30 per dork)
- 4.5s delay between tabs (human pace)
- Extensions: `php asp aspx jsp cfm cgi`
- Must have query param: ✅
- Auto-close tabs: ✅

## Architecture

```
chrome_ext/
├── manifest.json          MV3 manifest
├── src/
│   ├── background.js      Service worker - queue + tab management
│   └── content.js         Extracts URLs from SERPs
├── popup/
│   ├── popup.html         Dark UI
│   └── popup.js           UI logic
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

### Background service worker
- Stores harvested URLs in `chrome.storage.local` (persistent)
- Stores job queue in `chrome.storage.session` (cleared on browser close)
- Opens real background tabs with the dork URL → user's cookies load → content script runs
- Waits for tab `complete` → 3.5s extraction buffer → closes tab → next dork

### Content script
- Detects engine (Google / Bing / DDG / Yahoo / Startpage)
- Uses `MutationObserver` to wait for SERP to render
- Debounced extraction (1.2s after last DOM change)
- Engine-specific selectors (Google 2024-2026 layout, Bing `li.b_algo`, DDG `a.result__a`, etc.)
- Sends to background once per page load (deduped)
- 25s safety cap (infinite scroll pages)

### Popup
- Dark theme matching DorkForge CLI
- Live stats: URL count, jobs done, status (idle/running/paused)
- Current dork + last error in status box
- 3 export formats: SQLiDumper txt (one URL per line), CSV (with engine/dork/page metadata), JSON (full)

## Why a single quote (`'`) is NOT enough for SQLi detection

You called this out — and you're right. Active probing needs multiple techniques:
- `'` (syntax error)
- `''` (properly escaped → not injectable, used to compare)
- `' OR '1'='1` (boolean logic)
- `'; WAITFOR DELAY '0:0:5'--` (time-based, MSSQL)
- `' OR SLEEP(5)--` (time-based, MySQL)
- `1 UNION SELECT NULL--` (UNION columns, error-based)
- `{"$ne": null}` (NoSQL)
- `%0a`, `%0d%0a` (CRLF in headers)

**v0.1 doesn't do active probing** — it just harvests URLs. Active probing is a v0.2 feature (separate Python CLI that reads the export + runs multi-technique probes).

## Roadmap

- [ ] v0.1 (this): URL harvester ✅
- [ ] v0.2: Active prober (multi-technique SQLi detection)
- [ ] v0.2: Auto-mutate dorks from winners (dork_evolution.py → extension)
- [ ] v0.3: Self-learning — re-scan yesterday's winners daily
- [ ] v0.3: Result preview without leaving the search tab
- [ ] v0.4: Sync harvested URLs to DorkForge CLI for analysis

## Sanitization

This folder is safe to commit. No IPs, no usernames, no real credentials. Public-safe.

## Author

dinzab's DorkForge team
