# DorkForge PRODUCTION Harvest Summary

**Date:** 2026-06-26 16:21-16:35 UTC
**Run:** Production phase
**Dorks:** 3,078
**Pages/dork:** 3
**Workers:** 15
**Engine:** Bing
**Wall time:** 13m 25s
**Errors:** 0

## Yield
| Metric | v3.1 | v3.1-PROD | Change |
|---|---:|---:|---:|
| Raw URLs | 16,457 | 46,044 | **+180%** |
| Unique URLs | 6,324 | 8,186 | +29% |
| Real targets | 504 | 620 | +23% |
| Scripted targets | 158 | 269 | **+70%** |
| Scripted/dork | 0.157 | 0.087 | -45% |
| format_final URLs | 269 | 447 | +66% |
| SCRIPTED tier (post-filter) | 185 | 308 | +66% |

## Top 10 dorks (this run)
1. `contains:php inurl:"?nid="` — 14x scripted
2. `contains:php inurl:"?news_id="` — 10x scripted (NEW)
3. `contains:asp inurl:"?nid="` — 8x scripted
4. `contains:php inurl:"?gallery_id="` — 7x scripted (NEW)
5. `contains:asp inurl:"?id="` — 7x scripted
6. `contains:asp inurl:"?sort="` — 7x scripted (NEW)
7. `contains:php inurl:"?image_id="` — 6x scripted (NEW)
8. `contains:php inurl:"?tid="` — 6x scripted
9. `contains:jsp inurl:"?invoice_id="` — 5x scripted (NEW)
10. `contains:asp inurl:"?thread="` — 5x scripted

## NEW params that worked
- `news_id`, `gallery_id`, `image_id`, `invoice_id`, `pic_id`
- `sort`, `hide`, `act`, `cmd`, `view`, `display`

## How to use
```bash
# Production harvest (regenerate dorks first)
py gen_prod_dorks.py -o dorks_bing_prod.txt
py dorkforge.py -f dorks_bing_prod.txt -e bing -p 3 -w 15 -o harvest.txt --sqlite harvest.db

# Filter + format
py format_final.py -i harvest.txt -o final.txt
py dork_yield_analyzer.py -i harvest.txt -o yield/

# Round 2: use only high-yield dorks with deeper pages
py dorkforge.py -f yield/high_yield_dorks.txt -e bing -p 4 -w 15 -o round2.txt
```
