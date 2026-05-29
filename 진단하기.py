"""
진단용 스크립트: 디시 접속 상태와 HTML 파싱 결과를 출력합니다.
"""
import sys
import requests
from bs4 import BeautifulSoup

from config import HEADERS, GALLERIES
from collector import _search_url, _parse_post_list

print("=" * 60)
print("  디시 접속/파싱 진단")
print("=" * 60)

for g in GALLERIES:
    gid = g["id"]
    btype = g.get("board_type", "board")
    url = _search_url(gid, btype, "투네")
    print(f"\n[{g['name']}]  ({btype})")
    print(f"URL: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
    except Exception as e:
        print(f"  ❌ 접속 실패: {e}")
        continue

    print(f"  HTTP 상태: {r.status_code}  (200이면 정상)")
    print(f"  받은 HTML 길이: {len(r.text)} 글자")

    html = r.text
    soup = BeautifulSoup(html, "lxml")

    has_gall_list = soup.find("table", class_="gall_list") is not None
    n_ub = len(soup.find_all("tr", class_=lambda c: c and "ub-content" in c))
    print(f"  'gall_list' 테이블 발견: {has_gall_list}")
    print(f"  'ub-content' 행 개수: {n_ub}")

    posts = _parse_post_list(html, gid)
    print(f"  → 파싱된 글 개수: {len(posts)}")
    for p in posts[:3]:
        print(f"     · #{p['post_no']} {p['title'][:40]}")

    # HTML 저장 (디버깅용)
    fname = f"debug_{gid}.html"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  💾 HTML을 {fname} 에 저장했어요")

print("\n" + "=" * 60)
print("위 결과 전체를 캡처해서 보내주세요!")
print("=" * 60)
input("\n엔터 키를 누르면 닫힙니다...")
