# DorkForge v1.0 installer
$ErrorActionPreference = "Stop"
$Base = "https://hopes-till-opposite-chemistry.trycloudflare.com"
$Dest = "$env:USERPROFILE\dorkforge"

Write-Host "[*] DorkForge v1.0 installer"
Write-Host "[*] Source: $Base"
Write-Host "[*] Target: $Dest"

if (!(Test-Path $Dest)) { New-Item -ItemType Directory -Path $Dest | Out-Null }

$files = @("dorkforge.py","dorkforge_gui.py","dorkforge_README.md","install.bat","dorkforge_dorks_50.txt","dorkforge_v1.0.tar.gz")
foreach ($f in $files) {
    $url = "$Base/$f"
    $out = Join-Path $Dest $f
    Write-Host "  [*] Downloading $f ..."
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
        $size = (Get-Item $out).Length
        Write-Host "      OK ($size bytes)"
    } catch {
        Write-Host "      FAIL: $_"
    }
}

Write-Host ""
Write-Host "[*] Done. Files in: $Dest"
Write-Host "[*] Run install.bat to complete setup, or:"
Write-Host "    py $Dest\dorkforge.py -d 'inurl:test' -e bing -p 1"
Write-Host "    py $Dest\dorkforge_gui.py"

# Pause if interactive
if ($Host.Name -eq "ConsoleHost" -and [Environment]::UserInteractive) {
    Write-Host ""
    Read-Host "Press Enter to exit"
}
