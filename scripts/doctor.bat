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
echo [doctor] rc=%RC%  -- 0 ok ([--] Java is fine: only the SHACL / Fuseki tests need it), 1 some [NG] line above
pause
exit /b %RC%

:no_venv
echo [NG] .venv not found - run scripts\setup_offline.bat first (README_offline.md)
pause
exit /b 2
