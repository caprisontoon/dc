"""
PC 로컬에서 대시보드를 띄웁니다. (브라우저에서 http://127.0.0.1:5000 열림)
이 화면의 "지금 수집하기" 버튼으로 PC에서 직접 수집할 수 있어요.
"""
import threading
import webbrowser

from dotenv import load_dotenv
load_dotenv()

from api.index import app

if __name__ == "__main__":
    print("=" * 50)
    print("  대시보드 주소: http://127.0.0.1:5000")
    print("  (이 창은 켜두세요. 닫으면 대시보드가 꺼져요)")
    print("=" * 50)
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000)
