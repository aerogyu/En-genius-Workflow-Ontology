@echo off
rem Check real data files (JSON) against their contracts: drag one or more .json files onto this file.
rem   The contracts come from the latest build output (output\<run>\contracts\). To use another build,
rem   drag that output folder together with the .json files.
rem   scripts\validate.bat [output\<run>] <data.json ...>
rem   JSON envelope: {"contract": "<key>", "version": "0.1.0", "data": {...}} - see contracts\<key>\<version>.example.json
rem This .bat is ASCII-only on purpose: cmd reads .bat files as cp949 on Korean Windows.
setlocal
set "WF_CALLER_DIR=%CD%"
cd /d "%~dp0.."
call "%~dp0env.bat"
if not exist .venv\Scripts\python.exe goto :no_venv
.venv\Scripts\python scripts\bat_helper.py validate %*
set RC=%errorlevel%
echo.
if "%RC%"=="0" echo [validate] RESULT: OK  (rc=0) - all files pass
if "%RC%"=="1" echo [validate] RESULT: FAIL  (rc=1) - some file breaks its contract (see the lines above)
if "%RC%"=="2" echo [validate] RESULT: STOPPED  (rc=2) - nothing to check
if not "%RC%"=="0" if not "%RC%"=="1" if not "%RC%"=="2" echo [validate] RESULT: rc=%RC%
pause
exit /b %RC%

:no_venv
echo [NG] .venv not found - run scripts\setup_offline.bat first (README_offline.md)
pause
exit /b 2
