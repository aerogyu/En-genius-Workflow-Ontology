@echo off
rem Freeze (release) the current version of one contract: writes _released\<contract>\<version>.json in the YAML folder.
rem This is the engineer's approval record (HITL): date + reason only, no names. After this, changing that contract
rem without raising its version is an error (V02).
rem Do not write names or job titles in the reason: it is refused (V06) and nothing is written.
rem   Double-click                         -> folder data\real\workflows; asks for the contract key and the reason
rem   Drag a YAML folder onto this file    -> that folder; asks for the contract key and the reason
rem   scripts\release.bat <yaml folder> <contract key> <reason ...>
rem The example folders are not used by default (they are repo files). To practise, copy one and drag the copy.
rem This .bat is ASCII-only on purpose: cmd reads .bat files as cp949 on Korean Windows.
setlocal
set "WF_CALLER_DIR=%CD%"
cd /d "%~dp0.."
call "%~dp0env.bat"
if not exist .venv\Scripts\python.exe goto :no_venv
.venv\Scripts\python scripts\bat_helper.py release %*
set RC=%errorlevel%
echo.
if "%RC%"=="0" echo [release] RESULT: OK  (rc=0) - frozen (or already frozen)
if "%RC%"=="1" echo [release] RESULT: REFUSED  (rc=1) - see the message above
if "%RC%"=="2" echo [release] RESULT: STOPPED  (rc=2) - nothing changed
if not "%RC%"=="0" if not "%RC%"=="1" if not "%RC%"=="2" echo [release] RESULT: rc=%RC%
pause
exit /b %RC%

:no_venv
echo [NG] .venv not found - run scripts\setup_offline.bat first (README_offline.md)
pause
exit /b 2
