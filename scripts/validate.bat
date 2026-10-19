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
echo [validate] rc=%RC%  -- 0 all files pass, 1 some file breaks its contract (see the lines above), 2 stopped (nothing to check)
pause
exit /b %RC%

:no_venv
echo [NG] .venv not found - run scripts\setup_offline.bat first (README_offline.md)
pause
exit /b 2
