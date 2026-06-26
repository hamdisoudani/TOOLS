# auto_visual_test.ps1
# One-click automated visual test of Dork Searcher V3
# Copies files, launches, takes 4 screenshots over 60 seconds, dumps everything to the shared dir

$ErrorActionPreference = "Continue"
$DST = "C:\Users\<user>\Desktop\dsv3_test"
$SHOTS = "$DST\screenshots"
$SHARED = "\\<shared>\dorksmith\dsv3_test\screenshots"
$LOG = "$DST\auto_log.txt"

# Ensure dirs
New-Item -ItemType Directory -Path $DST -Force | Out-Null
New-Item -ItemType Directory -Path $SHOTS -Force | Out-Null

function Log($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line
    $line | Out-File $LOG -Append
}

function Take-Screenshot($name) {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
    $path = "$SHOTS\$name"
    $bmp.Save($path)
    $g.Dispose()
    $bmp.Dispose()
    Log "Screenshot saved: $path"
    return $path
}

# 1. Copy files
Log "=== DorkSearcher V3 Auto Visual Test ==="
if (Test-Path "C:\Users\<user>\Desktop\DorkSearcherV3\DorkSearched.exe") {
    Copy-Item "C:\Users\<user>\Desktop\DorkSearcherV3\DorkSearched.exe" $DST -Force
    Log "[OK] Copied DorkSearched.exe"
} else {
    Log "[ERROR] DorkSearched.exe not at C:\Users\<user>\Desktop\DorkSearcherV3\"
    Log "Extract from \\<shared>\dorksmith\eu\dorksearcher_v3\ (pw: adrikadi)"
    exit 1
}
Copy-Item "\\<shared>\dorksmith\dsv3_test\test_50_dorks.txt" $DST -Force
Log "[OK] Copied test_50_dorks.txt"

# 2. Snapshot processes BEFORE
$procsBefore = Get-Process | Select-Object -ExpandProperty ProcessName | Sort-Object -Unique
Log "Process count before launch: $((Get-Process).Count)"

# 3. Launch
Log "Launching DorkSearched.exe..."
$proc = Start-Process -FilePath "$DST\DorkSearched.exe" -WorkingDirectory $DST -PassThru
Log "Launched with PID: $($proc.Id)"

# 4. Wait 5 sec for unpack
Log "Waiting 5 seconds for unpack..."
Start-Sleep -Seconds 5

# 5. Screenshot 1: GUI just opened
Take-Screenshot "01_gui_open.png"

# 6. List all windows visible (to find the DorkSearcher window)
$windows = Get-Process | Where-Object { $_.MainWindowTitle -ne "" -and $_.MainWindowHandle -ne 0 } | Select-Object Id, ProcessName, MainWindowTitle
Log "Visible windows:"
$windows | ForEach-Object { Log "  $($_.ProcessName) | $($_.MainWindowTitle)" } | Out-Null

# 7. Look specifically for DorkSearcher window
$dorkWin = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
if ($dorkWin) {
    Log "DorkSearcher window title: '$($dorkWin.MainWindowTitle)'"
    Log "DorkSearcher window handle: $($dorkWin.MainWindowHandle)"
} else {
    Log "DorkSearcher not found in process list (may have crashed)"
}

# 8. Wait 5 more sec, screenshot the GUI
Log "Waiting 5 more sec..."
Start-Sleep -Seconds 5
Take-Screenshot "02_gui_settled.png"

# 9. Try to use UI automation to find buttons and click them
# This is best-effort - falls back to manual instructions
Log "=== INSTRUCTIONS FOR MANUAL COMPLETION ==="
Log "1. Click 'Load' / 'Import' / 'Open' button in the DorkSearcher GUI"
Log "2. Navigate to: $DST\test_50_dorks.txt"
Log "3. Click 'Start' / 'Search' / 'Run' button"
Log "4. The script will continue taking screenshots automatically"
Log ""

# 10. Take periodic screenshots for 90 seconds
for ($i = 1; $i -le 9; $i++) {
    Start-Sleep -Seconds 10
    Take-Screenshot "03_progress_${i}0s.png"

    # Check browser count
    $chromeCount = (Get-Process chrome -ErrorAction SilentlyContinue | Measure-Object).Count
    $firefoxCount = (Get-Process firefox -ErrorAction SilentlyContinue | Measure-Object).Count
    $msedgeCount = (Get-Process msedge -ErrorAction SilentlyContinue | Measure-Object).Count
    Log "Browsers: chrome=$chromeCount, firefox=$firefoxCount, msedge=$msedgeCount"

    # Check if DorkSearcher is still running
    $stillRunning = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if (-not $stillRunning) {
        Log "DorkSearcher has exited"
        break
    }
}

# 11. Final state
Take-Screenshot "04_final.png"

# 12. List of all visible window titles
Log "=== Final window list ==="
$finalWindows = Get-Process | Where-Object { $_.MainWindowTitle -ne "" } | Select-Object Id, ProcessName, MainWindowTitle
$finalWindows | ForEach-Object {
    Log "  PID=$($_.Id) $($_.ProcessName): $($_.MainWindowTitle)"
}

# 13. Try to get URLs of browser windows (best-effort)
Log "=== Browser windows with URLs ==="
$chrome = Get-Process chrome -ErrorAction SilentlyContinue
$chrome | ForEach-Object {
    if ($_.MainWindowTitle) {
        Log "  chrome.exe (PID $($_.Id)): $($_.MainWindowTitle)"
    }
}

# 14. Copy all logs and screenshots to shared folder
Log "Copying screenshots to $SHARED ..."
if (Test-Path $SHARED) {
    Copy-Item "$SHOTS\*" $SHARED -Force
    Log "[OK] All screenshots copied to $SHARED"
} else {
    Log "[WARN] Shared dir $SHARED not accessible"
}

# 15. Send log too
Copy-Item $LOG $SHARED -Force

Log "=== DONE ==="
Log "Screenshots: $SHOTS\"
Log "Shared copy: $SHARED\"
Log "Log: $LOG"
