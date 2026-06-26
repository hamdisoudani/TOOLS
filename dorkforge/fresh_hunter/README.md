# 🔥 FRESH HUNTER v1.0 — The Ultimate URL Dumper

The most aggressive, multi-source SQLi URL harvester ever built. Combines **7 layers** of sources to deliver **daily-fresh** SQLi-suspect URLs.

## 🎯 WHAT IT DOES

Instead of relying on dork search alone (slow, rate-limited), Fresh Hunter combines:
- **3 search engines** (Bing/Google/Yandex)
- **6 scanner APIs** (FOFA/Quake/Censys/Shodan/ZoomEye/BinaryEdge)
- **6 vulnerability feeds** (NVD/CISA KEV/Exploit-DB/GitHub Advisory/OSV/...)
- **6 community sources** (URLScan/OpenBugBounty/PhishTank/URLhaus/OTX/...)
- **4 CMS-specific** (WP/Joomla/Drupal/Forum)
- **2 archive sources** (Wayback CDX/Common Crawl)
- **1 self-learning layer** (yesterday's URLs, score retention)

Then runs a **5-step pipeline**:
1. Normalize (HTML entities, session params, trailing junk)
2. Drop spam domains (w3schools, social, CDNs)
3. Dedup by host+path+query
4. Score by SQLi-suspicion (scripted ext + injectable param + freshness + source trust)
5. Tier classification (edu/gov / asia / global / other)

## 📊 OUTPUTS

For each run, you get:
- `urls_all_YYYYMMDD_HHMMSS.txt` — every URL with score
- `urls_top_YYYYMMDD_HHMMSS.txt` — top 10K by score (SQLiDumper primary feed)
- `urls_tier_global_*.txt` — non-asia non-gov targets
- `urls_tier_asia_*.txt` — China/Korea/Japan/India/etc (best yield density)
- `urls_tier_edu_gov_*.txt` — .edu/.gov/.mil/.ac (highest value)
- `urls_tier_other_*.txt` — everything else (still useful)
- `stats_*.json` — pipeline statistics
- `source_breakdown_*.json` — how many URLs each source contributed

## 🚀 QUICK START (Windows RDP)

```powershell
# Pull latest from GitHub
cd C:\Users\<user>\TOOLS
git pull origin main

# Install deps (one-time)
pip install requests

# Run basic version (free sources only)
cd dorkforge\fresh_hunter
python fresh_hunter.py --enable-nvd --enable-urlhaus --enable-urlscan

# Run with search engines (needs residential IP — your RDP IS residential)
python fresh_hunter.py --bing-dorks 300 --google-dorks 200 --enable-nvd --enable-urlhaus

# Full power (all sources)
python fresh_hunter.py --bing-dorks 500 --google-dorks 300 --yandex-dorks 200 `
  --enable-fofa --enable-quake --enable-censys --enable-shodan `
  --enable-nvd --enable-cisa --enable-urlscan --enable-urlhaus --enable-phishtank `
  --enable-cms --enable-wayback --enable-self-learn
```

## 🔑 API KEYS (env vars)

Set these to enable scanner sources:
```powershell
$env:FOFA_EMAIL = "your@email.com"
$env:FOFA_KEY = "your_fofa_api_key"

$env:CENSYS_API_ID = "your_id"
$env:CENSYS_API_SECRET = "your_secret"

$env:SHODAN_KEY = "your_shodan_api_key"

$env:GITHUB_TOKEN = "ghp_your_personal_access_token"
```

## 📈 EXPECTED YIELD (per run)

| Sources | Raw URLs | After filter | SQLiDumper ready |
|---------|----------|--------------|------------------|
| NVD + URLhaus + URLScan | ~300 | ~50-100 | 50-100 |
| + Bing (300 dorks) | ~5K | ~1-2K | 1-2K |
| + Google (200 dorks) | ~3K | ~1-2K | 1-2K |
| + FOFA + Quake | ~10K | ~3-5K | 3-5K |
| + CMS targeting | ~15K | ~5-8K | 5-8K |
| + Wayback | ~50K | ~10-15K | 10-15K |
| **All layers (residential IP)** | **100K+** | **30-50K** | **20-30K** |

## 🛠️ CUSTOM DORKS

Edit `sources/bing.py` → `gen_dorks()` to add your own patterns.

## 📅 DAILY CRON (Windows Task Scheduler)

```powershell
# Run at 6 AM daily
schtasks /create /tn "Fresh Hunter Daily" /tr "python C:\Users\<user>\TOOLS\dorkforge\fresh_hunter\fresh_hunter.py --bing-dorks 500 --google-dorks 300 --enable-nvd --enable-urlhaus --enable-urlscan --enable-wayback" /sc daily /st 06:00
```

## 🎯 SQLiDumper INTEGRATION

```powershell
# After Fresh Hunter produces urls_top_*.txt:
copy "C:\Users\<user>\TOOLS\dorkforge\fresh_hunter\fresh_harvest\urls_top_*.txt" "C:\sqldumper\urls.txt"

# Open SQLiDumper → Load URL list → Crawl
# Set threads: 50-100
# Set crawl depth: 3-5 pages
# Run
```

## 📁 DIRECTORY STRUCTURE

```
fresh_hunter/
├── fresh_hunter.py           # Main orchestrator
├── sources/                  # 27 source modules
│   ├── bing.py              # Bing search (needs residential IP)
│   ├── google.py            # Google search (needs residential IP)
│   ├── yandex.py            # Yandex search
│   ├── duckduckgo.py        # DDG (limited)
│   ├── fofa.py              # FOFA scanner (needs key)
│   ├── quake.py             # Quake scanner (needs auth)
│   ├── censys.py            # Censys (needs ID+secret)
│   ├── shodan.py            # Shodan (needs key)
│   ├── zoomeye.py           # ZoomEye (needs key)
│   ├── nvd.py               # NVD CVE 2.0 (free)
│   ├── cisa_kev.py          # CISA KEV (free)
│   ├── exploitdb.py         # Exploit-DB (free)
│   ├── github_advisories.py # GitHub Security (needs PAT)
│   ├── osv.py               # OSV.dev (free)
│   ├── urlscan.py           # URLScan.io (free, limited)
│   ├── openbugbounty.py     # OpenBugBounty (free)
│   ├── phishtank.py         # PhishTank (free)
│   ├── urlhaus.py           # URLhaus (free, hourly)
│   ├── otx.py               # AlienVault OTX (free)
│   ├── cms_wp.py            # WordPress targeting
│   ├── cms_joomla.py        # Joomla targeting
│   ├── cms_drupal.py        # Drupal targeting
│   ├── cms_forum.py         # Forum platforms
│   ├── wayback.py           # Wayback CDX (free, slow)
│   ├── common_crawl.py      # Common Crawl (free, $$$ on Athena)
│   └── self_learn.py        # Yesterday's URLs
└── fresh_harvest/            # Output directory
    ├── urls_all_*.txt
    ├── urls_top_*.txt
    ├── urls_tier_*.txt
    ├── stats_*.json
    └── source_breakdown_*.json
```

