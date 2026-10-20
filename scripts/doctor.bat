@echo off
rem Environment check: Python 3.10+, UTF-8 mode, Java, packages, forbidden packages, generated schema files, config files.
rem This .bat is ASCII-only on purpose: cmd reads .bat files as cp949 on Korean Windows.
setlocal
cd /d "%~dp0.."
call "%~dp0env.bat"
if not exist .venv\Scripts\python.exe goto :no_venv
.venv\Scripts\python -m engenius_wf doctor
set RC=%errorlevel%
echo.
if "%RC%"=="0" echo [doctor] RESULT: OK  (rc=0) - [--] Java is fine: only the SHACL / Fuseki tests need it
if "%RC%"=="1" echo [doctor] RESULT: NG  (rc=1) - see the [NG] line above
if not "%RC%"=="0" if not "%RC%"=="1" echo [doctor] RESULT: rc=%RC%
pause
exit /b %RC%

:no_venv
echo [NG] .venv not found - run scripts\setup_offline.bat first (README_offline.md)
pause
exit /b 2
