@echo off
rem Check only (no output files, about a second): use it often while writing the YAML files.
rem   Double-click                        -> data\real\workflows if it exists, else workflows\examples\textbook (practice)
rem   Drag a YAML folder (or one of its .yaml files) onto this file -> that folder
rem   Drag the folder together with a Tool ontology survey.ttl     -> also checks the TOOL IDs (X codes)
rem   scripts\check.bat <yaml folder> [catalog.ttl ...]
rem This .bat is ASCII-only on purpose: cmd reads .bat files as cp949 on Korean Windows.
setlocal
set "WF_CALLER_DIR=%CD%"
cd /d "%~dp0.."
call "%~dp0env.bat"
if not exist .venv\Scripts\python.exe goto :no_venv
.venv\Scripts\python scripts\bat_helper.py check %*
set RC=%errorlevel%
echo.
if "%RC%"=="0" echo [check] RESULT: OK  (rc=0) - no errors (warnings may remain); next: build.bat
if "%RC%"=="1" echo [check] RESULT: ERRORS  (rc=1) - fix the lines marked with the arrow
if "%RC%"=="2" echo [check] RESULT: STOPPED  (rc=2)
if not "%RC%"=="0" if not "%RC%"=="1" if not "%RC%"=="2" echo [check] RESULT: rc=%RC%
pause
exit /b %RC%

:no_venv
echo [NG] .venv not found - run scripts\setup_offline.bat first (README_offline.md)
pause
exit /b 2
