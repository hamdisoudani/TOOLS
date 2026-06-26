@echo off
REM Dork Searcher V3 - Visual Test
REM One-click setup + launch + screenshot

set DST=C:\Users\<user>\Desktop\dsv3_test
mkdir "%DST%\screenshots" 2>nul

echo ============================================
echo  Dork Searcher V3 - Visual Test
echo ============================================

REM Check if exe exists at expected location
if not exist "C:\Users\<user>\Desktop\DorkSearcherV3\DorkSearched.exe" (
    echo.
    echo [ERROR] DorkSearched.exe not found at C:\Users\<user>\Desktop\DorkSearcherV3\
    echo.
    echo Extract it first from:
    echo \\<shared>\dorksmith\eu\dorksearcher_v3\
    echo.
    echo Password: adrikadi
    echo.
    pause
    exit /b 1
)

REM Copy dorks file
copy /Y "\\<shared>\dorksmith\dsv3_test\test_50_dorks.txt" "%DST%\" >nul
echo [OK] Copied 50 dorks to %DST%\test_50_dorks.txt

REM Copy exe
copy /Y "C:\Users\<user>\Desktop\DorkSearcherV3\DorkSearched.exe" "%DST%\" >nul
echo [OK] Copied DorkSearched.exe to %DST%\

echo.
echo ============================================
echo  Launching in 3 seconds...
echo ============================================
echo.
echo  When the GUI opens:
echo    1. Click "Load" / "Import" / "Open" in the GUI
echo    2. Pick: %DST%\test_50_dorks.txt
echo    3. Click "Start" / "Search" / "Run"
echo    4. Watch Chrome/Firefox open tabs
echo.
echo  Take screenshots and save to:
echo    %DST%\screenshots\
echo.
echo ============================================
echo.

timeout /t 3 /nobreak >nul

cd /d "%DST%"
start "" DorkSearched.exe

echo [OK] Launched. The GUI should be visible now.
echo.
echo Press any key to exit this window (binary keeps running)...
pause >nul
