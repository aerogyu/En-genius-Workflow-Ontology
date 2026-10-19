@echo off
rem Build a workflow folder: all checks + TTL (2 graphs) + contract JSON Schemas + flow picture (workflow.html) + report.txt.
rem   Double-click                        -> data\real\workflows if it exists, else workflows\examples\textbook (practice)
rem   Drag a YAML folder (or one of its .yaml files) onto this file -> that folder
rem   Drag the folder together with a Tool ontology survey.ttl     -> also checks the TOOL IDs (X codes)
rem   scripts\build.bat <yaml folder> [catalog.ttl ...]
rem Output: output\<time>_<folder name>\ ; workflow.html opens in the browser after a good build (WF_NO_OPEN=1 turns that off).
rem Any error -> no output files, rc 1. Messages are Korean (printed by Python); the code list is in docs\02 (writing guide).
rem This .bat is ASCII-only on purpose: cmd reads .bat files as cp949 on Korean Windows.
setlocal
set "WF_CALLER_DIR=%CD%"
cd /d "%~dp0.."
call "%~dp0env.bat"
if not exist .venv\Scripts\python.exe goto :no_venv
.venv\Scripts\python scripts\bat_helper.py build %*
set RC=%errorlevel%
echo.
echo [build] rc=%RC%  -- 0 ok, 1 errors (no output files; fix the lines marked with the arrow), 2 stopped (argument or config)
pause
exit /b %RC%

:no_venv
echo [NG] .venv not found - run scripts\setup_offline.bat first (README_offline.md)
pause
exit /b 2
