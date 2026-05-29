@echo off
cd /d "%~dp0"
if exist "env.txt" (
    for /f "usebackq tokens=1,* delims==" %%a in ("env.txt") do set %%a=%%b
)
python diag.py
pause
