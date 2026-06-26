# DorkForge v1.0

Multi-engine dork executor with real progress bar, threaded workers, and SQLite sink.

Built 2026-06-26 to replace the dead "Dork Searcher V3 By CRYP70" competitor tool that dinzab was testing.

---

## Features

| Feature | Flag | Default |
|---|---|---|
| Dorks from file | `-f dorks.txt` | — |
| Dorks from stdin | `cat dorks.txt \| python3 dorkforge.py` | — |
| Single dork inline | `-d "inurl:php?id="` | — |
| Engine selector | `-e {ddg\|bing\|brave\|yandex\|all}` | `ddg` |
| Pages per dork | `-p N` | `5` |
| Concurrent workers | `-w N` | `10` |
| Live progress bar | (auto when TTY) | on |
| No progress | `--no-progress` | — |
| TXT output | `-o hits.txt` | `hits.txt` |
| SQLite sink | `--sqlite hits.db` | — |
| Skip curl_cffi | `--no-cffi` | uses Safari iOS fingerprint |
| HTTP timeout | `--timeout 25` | 25s |
| Min delay | `--delay-min 0.4` | 0.4s |
| Max delay | `--delay-max 1.2` | 1.2s |

## Engines

| Engine | URL | Results/page | Status |
|---|---|---|---|
| `ddg` | `https://html.duckduckgo.com/html/` | ~10 | ✅ Works (needs `kl=us-en` param) |
| `bing` | `https://www.bing.com/search` | ~10 | ✅ Works (~188 URLs / 10 dorks in 4s) |
| `brave` | `https://search.brave.com/search` | ~20 | ⚠️ Often 429 rate-limited from datacenter IPs |
| `yandex` | `https://yandex.com/search/` | ~10 | ⚠️ Often shows "Verification" (captcha) |

`all` mode runs all 4 engines × N dorks in parallel.

## Usage examples

```bash
# Basic: 50 dorks, 5 pages each, 10 workers, DDG
python3 dorkforge.py -f dorks.txt -p 5 -w 10 -o hits.txt

# Bing, deeper: 10 dorks × 2 pages
python3 dorkforge.py -f dorks.txt -e bing -p 2 -w 5 -o bing_hits.txt

# All engines × 1 page = 4 jobs per dork
python3 dorkforge.py -f dorks.txt -e all -p 1 -w 20 -o all_hits.txt --sqlite all_hits.db

# Single dork, verbose
python3 dorkforge.py -d 'inurl:"hotel.?check_in="' -e bing -p 3 -w 1

# No progress bar (for scripts/CI)
python3 dorkforge.py -f dorks.txt --no-progress -o hits.txt

# stdin
cat dorks.txt | python3 dorkforge.py -e ddg -p 3 -w 10 -o hits.txt
```

## Output format

### TXT (append mode)
```
# DorkForge v1.0 | engines=bing | dorks=10 | pages/dork=2

## dork: inurl:"hotel.?check_in="
https://www.booking.com/
https://app.marriott.com/JnltmtDecyb
https://www.booking.com/hotel/index.html
...

## dork: inurl:"booking.?check_out="
https://partner.booking.com/en-gb/help/...
...
```

### SQLite
```sql
CREATE TABLE hits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT CURRENT_TIMESTAMP,
    engine TEXT NOT NULL,
    dork TEXT NOT NULL,
    url TEXT NOT NULL,
    UNIQUE(engine, url)
);

-- Query:
SELECT engine, COUNT(DISTINCT url) AS urls, COUNT(DISTINCT dork) AS dorks FROM hits GROUP BY engine;
SELECT * FROM hits WHERE dork LIKE '%booking%';
```

## Architecture (how it works)

```
                  ┌──────────────┐
                  │ dorkforge.py │
                  └──────┬───────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
    ┌──────────────┐         ┌──────────────┐
    │ Client       │         │ Scraper      │
    │ (curl_cffi,  │────────▶│ per-engine   │
    │ safari iOS   │         │ extraction   │
    │ fingerprint) │         └──────┬───────┘
    └──────────────┘                │
                                    ▼
                            ┌──────────────┐
                            │ URL filter   │
                            │ (excludes    │
                            │ search engs) │
                            └──────┬───────┘
                                   ▼
                          ┌────────────────┐
                          │ TXT + SQLite   │
                          │ output         │
                          └────────────────┘
```

- **Threading**: `concurrent.futures.ThreadPoolExecutor` with N workers, each worker handles one dork
- **Impersonation**: `curl_cffi` with `safari17_2_ios` (TLS fingerprint matches iOS Safari)
- **Retry**: 3 retries per page with exponential backoff on 429/503/blocked
- **Block detection**: short page (<800 bytes), or markers like "unusual traffic", "captcha", "are you a human"
- **Dedup**: per-dork local set + SQLite `UNIQUE(engine, url)` constraint

## Known limitations

- **Google is intentionally excluded** — datacenter IPs are blocked
- **Brave + Yandex often captcha** from datacenter IPs (the user has a residential Windows RDP if needed)
- **Single proxy rotation not yet implemented** — uses single egress IP (Linux sandbox AWS us-east-1)
- **No JS rendering** — relies on server-rendered HTML. Bing/DDG mostly work; some engines need JS

## Future ideas (v1.1)

- [ ] Proxy rotation (port `proxies/` rotation from dork-hunter)
- [ ] Custom user-agent pool
- [ ] CSV/JSON output
- [ ] Resume from checkpoint
- [ ] Engine-specific query formatters (Bing `inurl:` → use site:filter instead since Bing's inurl is broken)
- [ ] AsyncIO variant for higher concurrency

## Files

- `dorkforge.py` — main tool (one file, ~20KB)
- `README.md` — this file
- `smoke/` — test dork files and outputs
- `PLAYBOOK.md` (parent dir) — Linux↔Windows ops playbook