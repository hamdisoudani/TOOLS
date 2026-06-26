# TOOLS — dinzab's security toolkit

Single source of truth for our custom security tools. Build it once, push it here, pull it from any machine.

## What's in here

### 🔍 [DorkForge](./dorkforge/) — SQLi URL Harvester
- Multi-engine (Bing/DuckDuckGo/Brave/Yandex) parametric dork executor
- Tkinter GUI v3.1 — dark hacker terminal theme
- Data-driven dork generator (1,130 curated high-yield dorks)
- Post-harvest yield analyzer — learns which dorks actually produce SQLi targets
- Multi-pass URL filter (SERP/spam/dork-pollution/diversity/scripted-tier)
- Outputs ready for SQLiDumper crawler

### 🎯 [DSV3 Automation](./dsv3-automation/) — Dork Searcher V3 reverse engineering
- Static RE report on Dork Searcher V3 By CRYP70 (PE analysis, byte-XOR loader, 82.5MB encrypted .rdata)
- PowerShell scripts to launch and capture DSV3 behavior
- Test dork samples + visual test runner

## Workflow

```bash
# Linux side — make changes, test, then:
cd ~/TOOLS
git add -A
git commit -m "what changed"
git push

# Windows side — get latest:
cd C:\Users\<user>\TOOLS
git pull
# Now dorkforge_gui.py is up to date, no file transfer needed
```

## Quick start (Windows)

```powershell
cd C:\Users\<user>\TOOLS\dorkforge
py dorkforge_gui.py
# Click "🎯 TARGETED" → START → "🎯 FORMAT FOR SQLiDUMPER" → drop into SQLiDumper
```

## Tools policy

These are **defensive security tools** built for:
- Authorized penetration testing
- Bug bounty research
- Capture-the-flag (CTF) competitions
- Security training and education

**Do not use for unauthorized access.** All dork patterns, sample inputs, and configurations are public knowledge from Microsoft/Google documentation — we add the curation, automation, and filtering layer.

No exploit payloads. No credentials. No real targets in the repo.

## Repo ownership

- GitHub: https://github.com/hamdisoudani/TOOLS
- Author: dinzab
- Build: 2026-06-26
