"""
Claude API로 글의 관련성과 감정을 분류합니다.
"""
import json
import logging
import time

import anthropic

import db
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, BODY_CHAR_LIMIT, COMMENT_LIMIT

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """\
다음은 디시인사이드 게시글이야. "투네이션"은 스트리머 후원 플랫폼 toon.at의 이름이야.
이 글이 후원 플랫폼 투네이션에 관한 글이 맞는지 판정해줘.
JSON으로만 답해 (다른 텍스트 없이):
{{
  "is_relevant": true,
  "sentiment": "긍정",
  "summary": "한 줄 요약 (40자 이내)",
  "topic_tags": ["수수료", "정산", "버그", "비교", "이벤트", "업데이트"]
}}
sentiment는 "긍정" | "중립" | "부정" 중 하나.
topic_tags는 0~3개.

제목: {title}
본문:
{body}
상위 댓글:
{comments}"""


def _build_prompt(post: dict, comments: list[dict]) -> str:
    title = post.get("title", "")
    body = (post.get("body") or "")[:BODY_CHAR_LIMIT]
    top_comments = comments[:COMMENT_LIMIT]
    comments_text = "\n".join(
        f"- {c['author']}: {c['body'][:200]}" for c in top_comments
    ) or "(댓글 없음)"
    return PROMPT_TEMPLATE.format(title=title, body=body, comments=comments_text)


def classify_post(post: dict, comments: list[dict], client: anthropic.Anthropic) -> dict:
    prompt = _build_prompt(post, comments)
    for attempt in range(3):
        try:
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            # JSON 블록 추출
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                raise ValueError("JSON 없음")
            result = json.loads(raw[json_start:json_end])

            return {
                "post_id": post["id"],
                "is_relevant": int(bool(result.get("is_relevant", False))),
                "sentiment": result.get("sentiment", "중립"),
                "summary": result.get("summary", ""),
                "topic_tags": json.dumps(result.get("topic_tags", []), ensure_ascii=False),
            }
        except Exception as e:
            logger.warning(f"분류 실패 (시도 {attempt+1}/3) [{post['id']}]: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    # 3번 실패 시 기본값 (중립/관련 없음으로 처리)
    return {
        "post_id": post["id"],
        "is_relevant": 0,
        "sentiment": "중립",
        "summary": "분류 실패",
        "topic_tags": "[]",
    }


def run_classifier(posts: list[dict]):
    """수집된 글 목록 분류 후 DB 저장."""
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    for post in posts:
        pid = post["id"]
        # 이미 분류된 글 건너뜀
        with db.get_conn() as conn:
            exists = conn.execute(
                "SELECT 1 FROM classifications WHERE post_id=?", (pid,)
            ).fetchone()
        if exists:
            continue

        # DB에서 댓글 불러오기
        with db.get_conn() as conn:
            comments = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM comments WHERE post_id=? ORDER BY id LIMIT ?",
                    (pid, COMMENT_LIMIT),
                ).fetchall()
            ]

        # DB에 본문 없으면 posts에서 가져옴
        if not post.get("body"):
            with db.get_conn() as conn:
                row = conn.execute("SELECT body FROM posts WHERE id=?", (pid,)).fetchone()
                if row:
                    post["body"] = row["body"]

        result = classify_post(post, comments, client)
        db.save_classification(result)
        logger.info(
            f"분류 완료 [{pid}] relevant={result['is_relevant']} "
            f"sentiment={result['sentiment']} | {result['summary']}"
        )
        time.sleep(0.5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db.init_db()
    with db.get_conn() as conn:
        posts = [
            dict(r)
            for r in conn.execute(
                """SELECT p.* FROM posts p
                   LEFT JOIN classifications c ON p.id=c.post_id
                   WHERE c.post_id IS NULL LIMIT 20"""
            ).fetchall()
        ]
    print(f"미분류 글 {len(posts)}개 처리 시작")
    run_classifier(posts)
