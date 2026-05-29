import requests
from bs4 import BeautifulSoup
from config import HEADERS, GALLERIES
from collector import _search_url, _parse_post_list

print("=" * 60)
for g in GALLERIES:
    gid = g["id"]
    btype = g.get("board_type", "board")
    url = _search_url(gid, btype, "투네")
    print(f"\n[{g['name']}]")
    print(f"URL: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
    except Exception as e:
        print(f"  ERROR: {e}")
        continue
    print(f"  HTTP: {r.status_code}")
    print(f"  HTML length: {len(r.text)}")
    soup = BeautifulSoup(r.text, "lxml")
    print(f"  gall_list found: {soup.find('table', class_='gall_list') is not None}")
    print(f"  ub-content rows: {len(soup.find_all('tr', class_=lambda c: c and 'ub-content' in c))}")
    posts = _parse_post_list(r.text, gid)
    print(f"  parsed posts: {len(posts)}")
    for p in posts[:3]:
        print(f"    - #{p['post_no']} {p['title'][:50]}")
    with open(f"debug_{gid}.html", "w", encoding="utf-8") as f:
        f.write(r.text)
    print(f"  saved: debug_{gid}.html")

print("\n" + "=" * 60)
input("Press Enter to close...")
