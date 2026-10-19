@echo off
rem LinkML schema -> schema\generated\ (terms.json, wfo_file.schema.json, wfo.shacl.ttl, wfo.owl.ttl, lint.txt).
rem Run it after editing schema\wfo.yaml; the build itself only reads schema\generated\ (linkml is imported here only).
rem   Double-click                      -> regenerate
rem   scripts\schema.bat --check        -> only report whether schema\generated\ matches schema\wfo.yaml (drift)
rem Then run scripts\selftest.bat.
rem This .bat is ASCII-only on purpose: cmd reads .bat files as cp949 on Korean Windows.
setlocal
cd /d "%~dp0.."
call "%~dp0env.bat"
if not exist .venv\Scripts\python.exe goto :no_venv
.venv\Scripts\python -m engenius_wf schema %*
set RC=%errorlevel%
echo.
echo [schema] rc=%RC%  -- 0 ok, 1 lint errors or drift (see above)
pause
exit /b %RC%

:no_venv
echo [NG] .venv not found - run scripts\setup_offline.bat first (README_offline.md)
pause
exit /b 2
