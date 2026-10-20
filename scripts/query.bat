@echo off
rem Competency queries q01-q08 (queries\*.rq) on a build output, each result shown as a table. Read only: writes nothing.
rem   Double-click                          -> the latest good build output (output\<run> that has workflow.ttl)
rem   Drag a build output folder (output\<run>, or its workflow.ttl) onto this file -> that output
rem   Drag it together with a Tool ontology survey.ttl -> q07 / q08 (cross queries) get the survey columns filled in
rem   scripts\query.bat [output\<run>] [survey.ttl ...] [q01 q02 ...]
rem The tables hold names from the YAML files: keep them in-house (README_offline.md section 8).
rem This .bat is ASCII-only on purpose: cmd reads .bat files as cp949 on Korean Windows.
setlocal
set "WF_CALLER_DIR=%CD%"
cd /d "%~dp0.."
call "%~dp0env.bat"
if not exist .venv\Scripts\python.exe goto :no_venv
.venv\Scripts\python scripts\bat_helper.py query %*
set RC=%errorlevel%
echo.
if "%RC%"=="0" echo [query] RESULT: OK  (rc=0)
if "%RC%"=="1" echo [query] RESULT: ERRORS  (rc=1) - not a finished build output (run build.bat first)
if "%RC%"=="2" echo [query] RESULT: STOPPED  (rc=2) - argument (see the [NG] line above)
if not "%RC%"=="0" if not "%RC%"=="1" if not "%RC%"=="2" echo [query] RESULT: rc=%RC%
pause
exit /b %RC%

:no_venv
echo [NG] .venv not found - run scripts\setup_offline.bat first (README_offline.md)
pause
exit /b 2
