@echo off
rem TOOL ID candidates: matches the tool names in _plan.yaml against the Tool ontology (survey.ttl, read only) and writes a CSV.
rem An engineer reads the CSV and writes tool_id / label_at_link into _plan.yaml by hand - the build never fills them in.
rem   Drag a YAML folder together with survey.ttl onto this file  (survey.ttl = ...\engenius-tool-ontology\output\<run id>\survey.ttl)
rem   Drag survey.ttl alone   -> folder data\real\workflows if it exists, else workflows\examples\textbook
rem   Double-click            -> practice: example folder + the synthetic example catalog
rem   scripts\link_tools.bat <yaml folder> <survey.ttl> [more .ttl]
rem CSV -> output\<time>_<folder name>_tool_candidates.csv  (built from in-house names: keep it in-house)
rem This .bat is ASCII-only on purpose: cmd reads .bat files as cp949 on Korean Windows.
setlocal
set "WF_CALLER_DIR=%CD%"
cd /d "%~dp0.."
call "%~dp0env.bat"
if not exist .venv\Scripts\python.exe goto :no_venv
.venv\Scripts\python scripts\bat_helper.py link-tools %*
set RC=%errorlevel%
echo.
if "%RC%"=="0" echo [link-tools] RESULT: OK  (rc=0) - CSV written
if "%RC%"=="1" echo [link-tools] RESULT: ERRORS  (rc=1) - the YAML folder has errors (run check.bat)
if "%RC%"=="2" echo [link-tools] RESULT: STOPPED  (rc=2) - no survey.ttl given
if not "%RC%"=="0" if not "%RC%"=="1" if not "%RC%"=="2" echo [link-tools] RESULT: rc=%RC%
pause
exit /b %RC%

:no_venv
echo [NG] .venv not found - run scripts\setup_offline.bat first (README_offline.md)
pause
exit /b 2
