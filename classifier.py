"""
Claude API로 글의 관련성·감정·태그 판정.
"""

import json
import logging
import os
import time

import anthropic
from dotenv import load_dotenv

from config import MAX_COMMENTS

load_dotenv()
logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(".env에 ANTHROPIC_API_KEY가 없습니다.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


SYSTEM_PROMPT = (
    "너는 디시인사이드 게시글 분류 도우미야. "
    "지시한 JSON 형식으로만 답해. 다른 말은 절대 하지 마."
)

USER_PROMPT_TMPL = """\
다음은 디시인사이드 게시글이야.
"투네이션"은 한국의 스트리머 후원 플랫폼 toon.at 의 서비스 이름이야.

이 글이 후원 플랫폼 투네이션(toon.at)에 관한 글인지 판정하고,
감정과 주제 태그를 분류해줘.

반드시 아래 JSON만 출력해 (코드블록 없이):
{{
  "is_relevant": true | false,
  "sentiment": "긍정" | "중립" | "부정",
  "summary": "한 줄 요약 (40자 이내)",
  "topic_tags": ["수수료", "정산", "버그", "비교", "홍보", "사건" 등에서 0~3개]
}}

제목: {title}

본문:
{body}

상위 댓글:
{top_comments}
"""


def _build_prompt(post: dict, comments: list[dict]) -> str:
    title = (post.get("title") or "")[:200]
    body = (post.get("body") or "")[:1500]
    top = comments[:MAX_COMMENTS]
    top_comments_text = "\n".join(
        f"- {c.get('author', '?')}: {(c.get('body') or '')[:200]}"
        for c in top
    ) or "(댓글 없음)"
    return USER_PROMPT_TMPL.format(title=title, body=body, top_comments=top_comments_text)


def classify(post: dict, comments: list[dict], retries: int = 2) -> dict:
    """
    단일 글 분류.
    반환: {post_id, is_relevant, sentiment, summary, topic_tags}
    """
    client = _get_client()
    prompt = _build_prompt(post, comments)

    for attempt in range(retries + 1):
        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            data = json.loads(raw)
            return {
                "post_id": post["id"],
                "is_relevant": bool(data.get("is_relevant", False)),
                "sentiment": data.get("sentiment", "중립"),
                "summary": data.get("summary", ""),
                "topic_tags": data.get("topic_tags", []),
            }
        except json.JSONDecodeError:
            logger.warning("[%s] JSON 파싱 실패 (시도 %d): %s", post["id"], attempt + 1, raw[:200])
            if attempt < retries:
                time.sleep(2 ** attempt)
        except anthropic.APIError as e:
            logger.error("[%s] API 오류: %s", post["id"], e)
            if attempt < retries:
                time.sleep(2 ** attempt)

    # 모든 재시도 실패 시 기본값
    return {
        "post_id": post["id"],
        "is_relevant": True,
        "sentiment": "중립",
        "summary": "",
        "topic_tags": [],
    }


def classify_all(posts_with_comments: list[tuple[dict, list[dict]]]) -> list[dict]:
    results = []
    for post, comments in posts_with_comments:
        clf = classify(post, comments)
        logger.info(
            "[%s] relevant=%s sentiment=%s — %s",
            post["id"], clf["is_relevant"], clf["sentiment"], clf["summary"][:40],
        )
        results.append(clf)
        time.sleep(0.5)  # API rate limit 여유
    return results
