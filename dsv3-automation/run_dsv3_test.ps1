# run_dsv3_test.ps1
# Test Dork Searcher V3 By CRYP70 with 10 dorks from DorkSmith EU matrix
# Captures: process tree, network connections, browser launches, child processes

$ErrorActionPreference = "Continue"
$logFile = "\\<shared>\dorksmith\dsv3_test\run_log.txt"
"" | Out-File $logFile

function Log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    Write-Host $line
    $line | Out-File $logFile -Append
}

Log "=== DorkSearcher V3 Test Started ==="

# 1. Verify files exist
$dorkFile = "C:\Users\<user>\Desktop\dsv3_test\test_10_dorks.txt"
$exeFile = "C:\Users\<user>\Desktop\dsv3_test\DorkSearched.exe"
$exePath = "C:\Users\<user>\Desktop\dsv3_test"

if (-not (Test-Path $dorkFile)) {
    Log "ERROR: dork file not found at $dorkFile"
    Log "Copy test_10_dorks.txt from \\<shared>\dorksmith\dsv3_test\ to $dorkFile"
    exit 1
}
if (-not (Test-Path $exeFile)) {
    Log "ERROR: DorkSearched.exe not found at $exeFile"
    exit 1
}

# 2. Hash the exe
$hash = Get-FileHash $exeFile -Algorithm SHA256
Log "DorkSearched.exe SHA256: $($hash.Hash)"
Log "DorkSearched.exe Size: $((Get-Item $exeFile).Length) bytes"

# 3. Count dorks
$dorks = Get-Content $dorkFile | Where-Object { $_ -notmatch '^\s*#' -and $_.Trim() -ne '' }
Log "Dork count: $($dorks.Count)"
Log "First 3 dorks:"
$dorks | Select-Object -First 3 | ForEach-Object { Log "  $_" }

# 4. Snapshot network connections BEFORE launch
Log ""
Log "=== Pre-launch netstat ==="
$netstatBefore = netstat -ano | Select-String "ESTABLISHED|TIME_WAIT|CLOSE_WAIT" | Out-String
$netstatBefore | Out-File $logFile -Append

# 5. Snapshot running processes
$procsBefore = Get-Process | Select-Object Id, ProcessName, Path | Sort-Object ProcessName
Log "=== Pre-launch process count: $($procsBefore.Count) ==="
$procsBefore | Where-Object { $_.Path -like "*chrome*" -or $_.Path -like "*firefox*" -or $_.Path -like "*edge*" -or $_.ProcessName -like "Dork*" } | Out-File $logFile -Append

# 6. Start a background process monitor (polls every 500ms)
$monitorRunning = $true
$monitorScript = {
    param($pid, $logPath, $shouldRun)
    $myLog = $logPath + ".monitor.txt"
    "" | Out-File $myLog
    $knownPids = @()
    while ($true) {
        try {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if (-not $proc) { break }
            $childProcs = Get-CimInstance Win32_Process -Filter "ParentProcessId=$pid" -ErrorAction SilentlyContinue
            foreach ($cp in $childProcs) {
                $entry = "$($cp.ProcessId) $($cp.Name) $($cp.CommandLine)"
                if ($entry -notin $knownPids) {
                    $knownPids += $entry
                    "[$(Get-Date -Format 'HH:mm:ss.fff')] CHILD: $entry" | Out-File $myLog -Append
                }
            }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    "monitor ended" | Out-File $myLog -Append
}

# 7. Launch the dork searcher
Log ""
Log "=== Launching DorkSearched.exe ==="
$proc = Start-Process -FilePath $exeFile -WorkingDirectory $exePath -PassThru
$procId = $proc.Id
Log "Launched with PID: $procId"

# Start monitor in background
$monitorJob = Start-Job -ScriptBlock $monitorScript -ArgumentList $procId, $logFile
Log "Monitor job started: $($monitorJob.Id)"

# 8. Wait for user to interact (or timeout after 60s)
Log "Waiting 60 seconds for the app to do its thing..."
Start-Sleep -Seconds 60

# 9. Check if still running
$stillRunning = Get-Process -Id $procId -ErrorAction SilentlyContinue
if ($stillRunning) {
    Log "DorkSearched.exe is STILL running (PID $procId)"
} else {
    Log "DorkSearched.exe has EXITED"
}

# 10. Snapshot connections AFTER
Log ""
Log "=== Post-launch netstat (top 50 lines) ==="
$netstatAfter = netstat -ano | Select-String "ESTABLISHED" | Select-Object -First 50
$netstatAfter | Out-File $logFile -Append

# 11. Check for browser launches
$browserProcs = Get-Process | Where-Object {
    $_.ProcessName -match "^(chrome|firefox|msedge|brave|opera|iexplore)$" -and
    $_.StartTime -gt (Get-Date).AddMinutes(-2)
}
Log ""
Log "=== Browser processes launched in last 2 min ==="
if ($browserProcs.Count -gt 0) {
    $browserProcs | Select-Object Id, ProcessName, MainWindowTitle, StartTime | Format-Table -AutoSize | Out-File $logFile -Append
    Log "Found $($browserProcs.Count) browser instances"
} else {
    Log "No browser processes detected"
}

# 12. Wait for monitor to finish
Stop-Job $monitorJob -PassThru | Wait-Job | Out-Null
Receive-Job $monitorJob | Out-Null

# 13. Dump monitor log
$monLog = $logFile + ".monitor.txt"
Log ""
Log "=== Child process monitor log ==="
if (Test-Path $monLog) {
    Get-Content $monLog | Out-File $logFile -Append
} else {
    Log "No monitor log found"
}

# 14. Kill the dork searcher if still running
if ($stillRunning) {
    Log "Killing DorkSearched.exe..."
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}

# 15. Final process list of just DorkSearched-related
Log ""
Log "=== Final process tree (DorkSearched + children) ==="
$dorkProcs = Get-Process | Where-Object { $_.ProcessName -match "Dork" -or $_.MainWindowTitle -match "dork" }
if ($dorkProcs) {
    $dorkProcs | Select-Object Id, ProcessName, MainWindowTitle | Format-Table -AutoSize | Out-File $logFile -Append
}

# 16. Get all browser URLs that were open
Log ""
Log "=== Open browser windows/tabs ==="
$browserWindows = Get-Process | Where-Object { $_.ProcessName -match "chrome|firefox|msedge" -and $_.MainWindowTitle }
if ($browserWindows) {
    $browserWindows | Select-Object Id, ProcessName, MainWindowTitle | Format-Table -AutoSize | Out-File $logFile -Append
}

Log ""
Log "=== Test Complete ==="
Log "Log file: $logFile"
Log "Monitor log: $monLog"
