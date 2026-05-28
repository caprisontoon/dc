"""
Claude API로 글이 정말 투네이션 관련인지, 그리고 감정/요약/태그를 판정.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from anthropic import Anthropic

from config import (
    ANTHROPIC_API_KEY,
    CLASSIFIER_MAX_BODY_CHARS,
    CLASSIFIER_TOP_COMMENTS,
    CLAUDE_MODEL,
)

log = logging.getLogger(__name__)

PROMPT_TEMPLATE = """다음은 디시인사이드 게시글이야.
"투네이션(toon.at)"은 스트리머 후원/도네이션 플랫폼이야.
이 글이 후원 플랫폼 "투네이션"에 관한 글인지 판정해줘.

주의사항:
- "투네이트", "투네 사이클" 같이 글자만 비슷한 다른 단어면 is_relevant=false
- 후원/결제/정산/수수료/도네/방송 후원 등 맥락이 있으면 is_relevant=true
- 감정은 글 작성자와 댓글 전반의 톤을 종합해서 판정

JSON으로만 답해. 다른 설명 절대 붙이지 마.
{{
  "is_relevant": true 또는 false,
  "sentiment": "긍정" 또는 "중립" 또는 "부정",
  "summary": "한 줄 요약 (40자 이내)",
  "topic_tags": ["수수료", "정산", "버그", "비교", "광고", "후원", "이벤트" 등에서 0~3개]
}}

---
제목: {title}

본문:
{body}

상위 댓글:
{top_comments}
"""


def _truncate(text: str, n: int) -> str:
    if not text:
        return ""
    if len(text) <= n:
        return text
    return text[:n] + " …(이하 생략)"


def _format_comments(comments: list[dict]) -> str:
    if not comments:
        return "(댓글 없음)"
    lines = []
    for i, c in enumerate(comments[:CLASSIFIER_TOP_COMMENTS], start=1):
        body = (c.get("body") or "").replace("\n", " ").strip()
        lines.append(f"{i}. {body}")
    return "\n".join(lines)


def _extract_json(text: str) -> dict[str, Any] | None:
    """모델이 코드블록이나 잡소리를 붙여도 JSON만 추출."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def classify_post(post: dict, comments: list[dict]) -> dict[str, Any]:
    """글 1건 분류. 실패 시 기본값 반환."""
    if not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY가 없어. .env 파일 확인해줘.")
        return _default_result()

    prompt = PROMPT_TEMPLATE.format(
        title=post.get("title") or "",
        body=_truncate(post.get("body") or "", CLASSIFIER_MAX_BODY_CHARS),
        top_comments=_format_comments(comments),
    )

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                block.text for block in resp.content if getattr(block, "text", None)
            )
            parsed = _extract_json(text)
            if parsed is None:
                log.warning("JSON 파싱 실패 (시도 %d): %s", attempt + 1, text[:200])
                continue
            return _normalize(parsed)
        except Exception as e:
            log.warning("Claude API 호출 실패 (시도 %d): %s", attempt + 1, e)
    return _default_result()


def _default_result() -> dict[str, Any]:
    return {
        "is_relevant": False,
        "sentiment": "중립",
        "summary": "(분류 실패)",
        "topic_tags": [],
    }


def _normalize(parsed: dict) -> dict:
    sentiment = parsed.get("sentiment", "중립")
    if sentiment not in ("긍정", "중립", "부정"):
        sentiment = "중립"
    tags = parsed.get("topic_tags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t)[:20] for t in tags[:3]]
    return {
        "is_relevant": bool(parsed.get("is_relevant")),
        "sentiment": sentiment,
        "summary": str(parsed.get("summary") or "")[:80],
        "topic_tags": tags,
    }
