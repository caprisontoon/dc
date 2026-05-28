# 디시인사이드 투네이션 모니터

디시인사이드 주요 갤러리에서 **투네이션(toon.at)** 관련 글과 댓글을 자동으로 수집해서,
로컬 HTML 대시보드 한 곳에서 보는 개인용 도구.

---

## 처음 한 번만 — 셋업

코딩 안 해본 분도 그대로 따라하시면 됩니다.

### 1) Python 설치 확인

터미널(맥은 "터미널", 윈도우는 "PowerShell")에서:

```bash
python --version
```

3.10 이상이면 OK. 없으면 https://www.python.org/downloads/ 에서 설치.

### 2) 가상환경 만들기 (선택이지만 권장)

```bash
cd dc
python -m venv .venv
# 맥/리눅스
source .venv/bin/activate
# 윈도우
.venv\Scripts\activate
```

### 3) 라이브러리 설치

```bash
pip install -r requirements.txt
```

### 4) API 키 넣기

```bash
cp .env.example .env
```

`.env` 파일을 메모장/VS Code 등으로 열어서 `ANTHROPIC_API_KEY=` 뒤에
본인 API 키를 붙여넣으세요.

- API 키 발급: https://console.anthropic.com/

---

## 매일 사용

```bash
python run.py
```

끝나면 `output/dashboard.html` 파일이 만들어집니다. 더블클릭해서 브라우저로 열면 끝.

대시보드에서 갤러리/감정/관련성/정렬/검색 필터를 쓸 수 있어요.

---

## 폴더 구성

| 파일 | 역할 |
|------|------|
| `config.py` | 갤러리 목록, 키워드, API 키 같은 설정 |
| `db.py` | SQLite 데이터베이스 관리 |
| `collector.py` | 갤러리 검색 결과에서 글 ID 수집 |
| `fetcher.py` | 글 본문 + 댓글 가져오기 |
| `classifier.py` | Claude API로 진짜 관련 글인지 + 감정 분류 |
| `dashboard.py` | DB → HTML 대시보드 생성 |
| `run.py` | 위 4개를 순서대로 한 번에 실행 |
| `templates/dashboard.html.j2` | 대시보드 HTML 템플릿 |
| `data/monitor.db` | 수집된 데이터 (자동 생성) |
| `output/dashboard.html` | 결과물 (자동 생성) |

---

## 단계별로 테스트해보고 싶을 때

전체를 한 번에 돌리지 않고 한 단계씩 확인하려면:

```bash
# 트위치 갤러리만 수집 결과 콘솔 출력 (DB 저장 X)
python collector.py

# 대시보드만 다시 그리기 (이미 DB에 데이터가 있을 때)
python dashboard.py
```

---

## 자주 묻는 것

### Q. 한 번 돌리면 얼마나 걸려요?
처음엔 신규 글이 많아 10~20분, 이후엔 매일 1~5분.

### Q. 비용은?
Claude API로 글 100개 분류해도 월 $1~3 수준.

### Q. 갤러리가 안 잡혀요
`config.py`의 `GALLERIES` 목록에서 `id` 값이 디시 실제 갤러리 ID와 같은지 확인하세요.
디시 갤러리 페이지 URL에서 `?id=...` 부분이 그 갤러리의 ID입니다.

마이너 갤러리(`gall.dcinside.com/mgallery/...`)는 `is_minor: True`,
일반 갤러리(`gall.dcinside.com/board/...`)는 `is_minor: False`로 맞춰주세요.

### Q. 댓글이 안 들어와요
디시는 댓글을 별도 AJAX로 부르는데 가끔 응답 형식이 바뀝니다.
`fetcher.py`의 `fetch_comments` 함수를 확인하세요.

### Q. 차단당한 것 같아요 (403/429)
`.env`의 `REQUEST_SLEEP_SECONDS`를 더 크게 (3~5초) 설정하세요.

### Q. 매일 자동 실행하고 싶어요
- **윈도우**: 작업 스케줄러에서 `python C:\경로\run.py` 매일 실행 등록
- **맥**: `crontab -e` 로 `0 9 * * * cd /경로 && /경로/.venv/bin/python run.py` 등록

---

## 안 하는 것

- 글 자동 작성 / 댓글 작성
- 로그인이 필요한 갤러리 접근
- 디시 외 사이트
- 대규모/상업적 수집 — 개인 모니터링 용도로만 쓰세요
