@echo off
cd /d "%~dp0"
if exist "env.txt" (
    for /f "usebackq tokens=1,* delims==" %%a in ("env.txt") do set %%a=%%b
)
pip install -r requirements.txt -q
start "" http://127.0.0.1:5000
python serve.py
pause
