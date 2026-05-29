@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   투네이션 디시 모니터링 - 수집 시작
echo ============================================
echo.

REM 처음 한 번만: 필요한 프로그램 설치
if not exist ".installed" (
    echo [처음 실행] 필요한 프로그램을 설치합니다. 잠시만 기다려주세요...
    python -m pip install -r requirements.txt
    echo done > .installed
    echo.
)

REM 데이터베이스 주소 입력 (env.txt 파일에서 읽음)
if exist "env.txt" (
    for /f "usebackq tokens=1,* delims==" %%a in ("env.txt") do set %%a=%%b
)

echo 디시인사이드에서 글을 수집하고 있습니다...
echo (2~5분 정도 걸려요)
echo.
python run.py

echo.
echo ============================================
echo   완료! 웹 대시보드에서 확인하세요.
echo ============================================
echo.
pause
