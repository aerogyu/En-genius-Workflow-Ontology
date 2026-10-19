@echo off
rem Local settings for this PC. Every other script calls this file first (so it has no pause of its own).
rem This .bat is ASCII-only on purpose: cmd reads .bat files as cp949 on Korean Windows.
rem FUSEKI_HOME : folder of the unpacked apache-jena-fuseki-6.2.0 zip (only the SHACL / Fuseki tests use it)
rem JAVA_HOME   : folder of the unpacked JDK 21 zip (contains bin\java.exe)
if "%FUSEKI_HOME%"=="" set "FUSEKI_HOME=C:\EnGenius\tools\apache-jena-fuseki-6.2.0"
if "%JAVA_HOME%"=="" set "JAVA_HOME=C:\EnGenius\tools\jdk-21.0.12.1+1"
rem PYTHON : interpreter used by setup_offline.bat to create .venv (default: python on PATH). e.g. set PYTHON=py -3.10
if "%PYTHON%"=="" set PYTHON=python
rem TOOL_ONTO_DIR : the sibling Tool ontology repo. setup_offline.bat reuses its offline\wheels (same requirements.lock).
if "%TOOL_ONTO_DIR%"=="" set "TOOL_ONTO_DIR=%~dp0..\..\engenius-tool-ontology"
rem WF_NO_OPEN : set it to 1 if build.bat should not open workflow.html in the browser after a good build.
rem The code is run from the repo folder (src\), not installed as a package: config\, schema\, workflows\, data\ are found relative to it.
set "PYTHONPATH=%~dp0..\src"
rem Python UTF-8 mode: YAML, schema and config files are UTF-8 with Korean text. Without this, Python on a Korean Windows
rem (code page 949) reads them as cp949: the schema command fails and tests\conftest.py stops the test run on purpose.
set PYTHONUTF8=1
