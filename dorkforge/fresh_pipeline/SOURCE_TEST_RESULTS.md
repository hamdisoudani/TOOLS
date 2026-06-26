# Fresh URL Sources — Live Test Results (2026-06-26 17:30 UTC)

Tested from Linux sandbox (74.241.x.x — Azure datacenter IP).

## ✅ WORKS WITHOUT AUTH

| Source | Endpoint | Yield | Notes |
|--------|----------|-------|-------|
| **NVD CVE 2.0** | `services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=sql%20injection` | **21,180 SQLi CVEs** | 30-day filter → 1,997 SQLi CVEs → 157 domains from refs (mostly vendor sites) |
| **CISA KEV** | `cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` | **1,629 actively-exploited CVEs** | 145 added in 2026, daily fresh |
| **URLScan.io** | `urlscan.io/api/v1/search/?q=task.url:php?id` | 17 results (limited) | Need account for full queries |
| **URLhaus** | `urlhaus.abuse.ch/downloads/text/` | 191 URLs with .php/.asp | Mostly malware delivery, not natural SQLi targets |
| **Wayback CDX** | `web.archive.org/cdx/search/cdx` | Works (no auth) | Historical only, mostly old |

## ❌ NEEDS AUTH

- **FOFA** — needs account + API key (free tier: 50 queries/month)
- **Quake (360)** — needs account + JS challenge
- **Censys** — needs API ID + secret
- **Shodan** — needs API key
- **BinaryEdge** — needs API key
- **Onyphe** — needs API key
- **GitHub code search** — needs PAT for >60 req/hr

## ⚠️ BLOCKED FROM DATACENTER

- **Bing + fresh filter** — Cloudflare CAPTCHA challenge
- **Google** — blocked entirely
- **Yandex** — needs CAPTCHA solve

## 🔑 THE TRUTH

**From a residential IP (your Windows RDP), the following will work:**
- Bing without CAPTCHA
- Google (full search)
- Yandex (mostly works)
- DDG (mostly works)
- Brave (mostly works)

**The pipeline `fresh_daily.py` is built for Windows RDP.**

## 🎯 RECOMMENDED SETUP

1. **Run `fresh_daily.py` from Windows RDP** (residential IP) — 300 dorks × p=2 = 600 jobs × ~30s each = ~5 min → 5K-20K fresh URLs
2. **Drop results into SQLiDumper** same day
3. **Daily cron** — runs `fresh_daily.py` automatically each morning
4. **Dedup vs yesterday** — only NEW URLs get tested
5. **Combined with NVD/CISA**: nightly scan of new CVEs → push referenced domains

## 📊 ESTIMATED YIELD (from residential IP)

| Source | Per Day | Quality |
|--------|---------|---------|
| Bing (300 dorks × p=2) | 5K-15K URLs | Mixed (need filter) |
| Google (200 dorks × p=3) | 3K-10K URLs | Better quality |
| Yandex (100 dorks × p=2) | 2K-5K URLs | Chinese sites |
| **TOTAL RAW** | **10K-30K URLs** | |
| After scripted+param filter (40%) | **4K-12K clean URLs** | |

## 🚀 NEXT STEPS

1. Run `fresh_daily.py` from Windows now (5 min)
2. Compare yield vs current 2,104 URLs from Linux harvest
3. If better → make daily cron
4. If still not 10K → add more Bing/Google dork types in same script

