@echo off
rem Self-check after an install or update: doctor -> pytest -> offline\selftest_<commit>.txt + offline\selftest_<commit>.log
rem   .txt = PASS/FAIL, installed commit, doctor [OK]/[NG] lines, test counts, failed test NAMES only - no data values: may go outside.
rem   .log = the whole output - stays in-house.
rem Tests that need Java / Fuseki or the sibling repo's synthetic survey.ttl skip themselves. About a minute.
rem The commit is the first line of offline\installed_commit.txt (else git on the dev PC, else "unknown").
rem Only the repo's own examples are used - data\real is not read.
rem This .bat is ASCII-only on purpose: cmd reads .bat files as cp949 on Korean Windows.
setlocal
cd /d "%~dp0.."
call "%~dp0env.bat"
if not exist .venv\Scripts\python.exe goto :no_venv
.venv\Scripts\python scripts\bat_helper.py selftest
set RC=%errorlevel%
echo.
echo [selftest] rc=%RC%  -- 0 PASS, 1 FAIL (bring the .txt named above to the dev PC; the .log stays in-house)
pause
exit /b %RC%

:no_venv
echo [NG] .venv not found - run scripts\setup_offline.bat first (README_offline.md)
pause
exit /b 2
