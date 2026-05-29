#!/bin/bash
# 맥(Mac) 사용자용 - 더블클릭하면 실행됩니다
cd "$(dirname "$0")"

echo "============================================"
echo "  투네이션 디시 모니터링 - 수집 시작"
echo "============================================"
echo

# 처음 한 번만: 필요한 프로그램 설치
if [ ! -f ".installed" ]; then
    echo "[처음 실행] 필요한 프로그램을 설치합니다. 잠시만 기다려주세요..."
    python3 -m pip install -r requirements.txt
    touch .installed
    echo
fi

# 데이터베이스 주소 입력 (env.txt 파일에서 읽음)
if [ -f "env.txt" ]; then
    export $(grep -v '^#' env.txt | xargs)
fi

echo "디시인사이드에서 글을 수집하고 있습니다..."
echo "(2~5분 정도 걸려요)"
echo
python3 run.py

echo
echo "============================================"
echo "  완료! 웹 대시보드에서 확인하세요."
echo "============================================"
echo
read -p "엔터 키를 누르면 닫힙니다..."
