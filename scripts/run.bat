@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
if "%~1"=="" (set "CONFIG=configs\config.yaml") else (set "CONFIG=%~1")
python "%CD%\src\main.py" update "%CONFIG%"
exit /b %ERRORLEVEL%
