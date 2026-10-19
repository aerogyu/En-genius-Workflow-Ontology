@echo off
rem Offline install (closed network). Run once; it works in the repo root wherever it is started from.
rem Needs Python 3.10 on this PC and the wheels of requirements.lock (the same 90 packages as the Tool ontology repo).
rem The wheels are looked up in this order (the first one found is used):
rem   1. offline\wheels\                                   of this repo
rem   2. offline\wheels_win_amd64_cp310.zip                of this repo (unpacked here with Python's zipfile)
rem   3. %TOOL_ONTO_DIR%\offline\wheels\                   the Tool ontology repo, already unpacked by its own setup
rem   4. %TOOL_ONTO_DIR%\offline\wheels_win_amd64_cp310.zip (unpacked into this repo's offline\)
rem TOOL_ONTO_DIR defaults to the folder next to this repo (scripts\env.bat). Nothing is downloaded.
rem This .bat is ASCII-only on purpose: cmd reads .bat files as cp949 on Korean Windows.
setlocal
cd /d "%~dp0.."
call "%~dp0env.bat"
set "ZIPNAME=wheels_win_amd64_cp310.zip"

set "WHEELS=offline\wheels"
if exist "offline\wheels\" goto :have_wheels
if exist "offline\%ZIPNAME%" goto :unpack_here
set "WHEELS=%TOOL_ONTO_DIR%\offline\wheels"
if exist "%TOOL_ONTO_DIR%\offline\wheels\" goto :have_wheels
if exist "%TOOL_ONTO_DIR%\offline\%ZIPNAME%" goto :unpack_sibling
echo [NG] no wheels found. Put %ZIPNAME% into this repo's offline folder,
echo      or set TOOL_ONTO_DIR in scripts\env.bat to the Tool ontology repo that has offline\wheels.
pause
exit /b 1

:unpack_here
echo [0/4] unpacking offline\%ZIPNAME%
if not exist offline\ mkdir offline
%PYTHON% -m zipfile -e "offline\%ZIPNAME%" offline
if errorlevel 1 goto :unzip_failed
set "WHEELS=offline\wheels"
goto :have_wheels

:unpack_sibling
echo [0/4] unpacking %ZIPNAME% of the Tool ontology repo into offline\
if not exist offline\ mkdir offline
%PYTHON% -m zipfile -e "%TOOL_ONTO_DIR%\offline\%ZIPNAME%" offline
if errorlevel 1 goto :unzip_failed
set "WHEELS=offline\wheels"
goto :have_wheels

:unzip_failed
echo [NG] could not unpack the wheels zip - is Python 3.10 on PATH? See PYTHON in scripts\env.bat
pause
exit /b 1

:have_wheels
if not exist "%WHEELS%\" goto :no_wheels_dir
echo [wheels] %WHEELS%

echo [1/4] creating .venv with: %PYTHON%
%PYTHON% -m venv .venv
if errorlevel 1 goto :venv_failed

echo [2/4] upgrading pip/setuptools/wheel from the wheels folder (no network)
.venv\Scripts\python -m pip install --no-index --find-links "%WHEELS%" --upgrade pip setuptools wheel
if errorlevel 1 goto :pip_failed

echo [3/4] installing runtime packages (requirements.lock, no network)
.venv\Scripts\python -m pip install --no-index --no-deps --find-links "%WHEELS%" -r requirements.lock
if errorlevel 1 goto :install_failed

echo [4/4] doctor  (the project code itself is not installed; the scripts set PYTHONPATH=src)
.venv\Scripts\python -m engenius_wf doctor
if errorlevel 1 goto :doctor_ng
echo.
echo Done. Next: scripts\build.bat (double-click: builds the textbook example and opens the flow picture),
echo       then scripts\selftest.bat. Writing guide: docs\02 ; in-house guide: README_offline.md
pause
exit /b 0

:no_wheels_dir
echo [NG] the wheels folder is missing after unpacking: %WHEELS%
pause
exit /b 1

:venv_failed
echo [NG] venv creation failed. Set PYTHON in scripts\env.bat, e.g. set PYTHON=py -3.10
pause
exit /b 1

:pip_failed
echo [NG] pip upgrade failed - see the lines above.
pause
exit /b 1

:install_failed
echo [NG] package install failed - see the lines above. Are the wheels complete for this Python (3.10, 64-bit)?
pause
exit /b 1

:doctor_ng
echo [NG] doctor reported a problem - see the lines above. A missing Java [--] is fine at this point.
pause
exit /b 1
