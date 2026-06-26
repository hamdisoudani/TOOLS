# VISUAL TEST PLAN — Dork Searcher V3 By CRYP70

## What We're Doing

Run the binary with **50 dorks** from DorkSmith's EU matrix and **screenshot the result**. The whole point: confirm it's a working dork dispatcher before sinking more time into RE.

## Goal

Determine visually:
1. Does the GUI open at all? (some packs crash on Win 11)
2. Does it have a file picker for the dork list?
3. Does it support a search engine selector (Google/Bing/DDG/Yandex)?
4. Does it support a `site:.tld` filter?
5. Does it show a progress counter / results count?
6. What URL pattern does it construct?
7. Does it open tabs in default browser?

## Files Ready in `\\<shared>\dorksmith\dsv3_test\`

| File | Purpose |
|---|---|
| `test_50_dorks.txt` | 50 dorks, one per line, inurl:"<kw>.<ext>?<param>=" format |
| `run_visual_test.bat` | One-click setup (copies exe + dorks, launches) |
| `run_dsv3_test.ps1` | Deep capture (process tree, netstat, child PIDs) — optional, for after visual |

## Steps (5 minutes)

### Step 1 — Set up the test folder
Open PowerShell on Windows and run:
```powershell
$dst = "C:\Users\<user>\Desktop\dsv3_test"
New-Item -ItemType Directory -Path $dst -Force | Out-Null
Copy-Item \\<shared>\dorksmith\dsv3_test\test_50_dorks.txt $dst\
# Copy the exe
$rar = "\\<shared>\dorksmith\eu\dorksearcher_v3\Dork Searcher V3 By CRYP70.rar"
# (or the already-extracted one at C:\Users\<user>\Desktop\DorkSearcherV3\)
# Easiest: use the already-extracted exe
Copy-Item "C:\Users\<user>\Desktop\DorkSearcherV3\DorkSearched.exe" $dst\
```

### Step 2 — Launch and screenshot
```powershell
cd C:\Users\<user>\Desktop\dsv3_test
Start-Process .\DorkSearched.exe
# Wait for the GUI to appear (3-5 seconds for the 86MB unpack)
Start-Sleep 5
# Take a screenshot of the full screen
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bmp.Save("$dst\screenshot_01_gui.png")
Write-Host "Screenshot saved to $dst\screenshot_01_gui.png"
```

### Step 3 — Load dorks file via the GUI
1. **Click the file picker / "Load" / "Import" / "Open" button** in the GUI
2. Navigate to `C:\Users\<user>\Desktop\dsv3_test\test_50_dorks.txt`
3. Open it
4. Take another screenshot → `screenshot_02_loaded.png`

### Step 4 — Set options (if available)
Look for any of these in the GUI and screenshot each:
- Search engine dropdown (Google / Bing / DDG / Yandex)
- Site:TLD filter input
- Proxy field (we expect to leave blank — confirming "no proxy" claim)
- Delay between queries (ms)
- Number of threads / parallel tabs
- Result count / counter
- Save-to-file option

### Step 5 — Start the search
Click the **Start / Search / Run / Scan** button.

Watch the screen — it should:
- Show a progress bar / counter
- Open Chrome/Firefox/Edge tabs (one per dork)
- Each tab: `https://www.google.com/search?q=inurl%3A%22xxx%22`

### Step 6 — Screenshot the result
Save as `screenshot_03_running.png` and `screenshot_04_done.png`.

### Step 7 — Also screenshot the browser
After 10-20 seconds, ALT+TAB to your browser. You should see:
- 50 new tabs (or batches of them)
- Each is a Google search results page
- URL bar shows `google.com/search?q=inurl%3A%22...%22`

Screenshot → `screenshot_05_browser_tabs.png`

### Step 8 — Also: close the binary & take a final
Save the **Desktop** screenshot showing all the open tabs → `screenshot_06_final.png`

---

## What to Send Back

Upload **all 6 screenshots** to:
`\\<shared>\dorksmith\dsv3_test\screenshots\`

(Just drop them in the folder from File Explorer — the shared dir maps to my Linux box)

---

## Quick Sanity Check (2-min version)

If you just want a quick "does it work at all":
```powershell
cd C:\Users\<user>\Desktop\dsv3_test
.\DorkSearched.exe
# Wait 5 sec
# Screenshot the GUI
# Try to load the dorks file
# Click Start
# See if browser opens tabs
```

---

## What If It Crashes / Doesn't Open

Some possibilities:
- **AV blocked it** (the RAR has the "disable AV" notice for a reason) — try right-click → "Run anyway" or whitelist `C:\Users\<user>\Desktop\dsv3_test\`
- **Missing VC++ runtime** — install `vc_redist.x86.exe` from Microsoft
- **Missing .NET** — usually not the issue for native exe
- **Windows SmartScreen** — click "More info" → "Run anyway"

If it still fails, take a screenshot of the error and send it.

---

## After The Test

Once we have the screenshots, I'll be able to:
1. Identify the URL pattern it uses
2. Map the GUI controls to internal function calls
3. Cross-reference with the binary analysis (we have the .text section already mapped)
4. Build a DorkSmith mode that does the same thing
