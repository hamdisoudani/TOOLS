@echo off
REM DorkForge v1.0 installer — drop in any folder, double-click to install
REM Copies dorkforge files from this folder to C:\Users\%USERNAME%\dorkforge\

setlocal
set DEST=%USERPROFILE%\dorkforge
set HERE=%~dp0

if not exist "%HERE%\dorkforge.py" (
    echo ERROR: dorkforge.py not found in %HERE%
    echo Make sure you have these files in the same folder:
    echo   dorkforge.py
    echo   dorkforge_gui.py
    echo.
    pause
    exit /b 1
)

echo ===========================================
echo   DorkForge v1.0 - Windows Installer
echo ===========================================
echo.
echo Source: %HERE%
echo Target: %DEST%
echo.

if not exist "%DEST%" mkdir "%DEST%"

echo Copying dorkforge.py ...
copy /Y "%HERE%\dorkforge.py" "%DEST%\" >nul
if errorlevel 1 goto :err

if exist "%HERE%\dorkforge_gui.py" (
    echo Copying dorkforge_gui.py ...
    copy /Y "%HERE%\dorkforge_gui.py" "%DEST%\" >nul
)

if exist "%HERE%\dorkforge_README.md" (
    echo Copying dorkforge_README.md ...
    copy /Y "%HERE%\dorkforge_README.md" "%DEST%\" >nul
)

if exist "%HERE%\dorkforge_dorks_50.txt" (
    echo Copying dorkforge_dorks_50.txt ...
    copy /Y "%HERE%\dorkforge_dorks_50.txt" "%DEST%\" >nul
)

if exist "%HERE%\dorkforge_eu50.txt" (
    echo Copying dorkforge_eu50.txt ...
    copy /Y "%HERE%\dorkforge_eu50.txt" "%DEST%\" >nul
)

if exist "%HERE%\dorkforge_eu50.sqlite" (
    echo Copying dorkforge_eu50.sqlite ...
    copy /Y "%HERE%\dorkforge_eu50.sqlite" "%DEST%\" >nul
)

echo.
echo ===========================================
echo   DONE
echo ===========================================
echo.
echo Files installed to: %DEST%
echo.
echo Next steps:
echo   1. Install Python deps:
echo      py -m pip install requests curl_cffi tqdm
echo.
echo   2. Test CLI:
echo      cd %DEST%
echo      py dorkforge.py -d "inurl:hotel.?check_in=" -e bing -p 1 -w 1 -o test.txt
echo.
echo   3. Launch GUI:
echo      py dorkforge_gui.py
echo.
pause
exit /b 0

:err
echo.
echo ERROR: Copy failed. See messages above.
pause
exit /b 1
