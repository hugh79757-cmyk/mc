"""
frontmatter_utils.py — 통합 frontmatter 처리 유틸 (Phase 26)

chain_drafter.py 에 분산되어 있던 frontmatter 관련 함수
(_ensure_frontmatter / _ensure_frontmatter_closer / _build_frontmatter /
_extract_description) 의 단일 진실 공급원(single source of truth).

기존 기능을 완전히 보존하며 이 모듈로 이전한다. chain_drafter.py 의
기존 이름들은 이 모듈을 호출하는 thin wrapper 로 유지된다 (테스트 호환).

보안 (Phase 26 threat register):
  - T-26-01: post 메타데이터 검증 (비 dict 입력 거부)
  - T-26-02: 입력 크기 상한 (과도한 메모리 사용 방지)
"""

import re

# T-26-02: 입력 크기 상한 — 정상 초안(수십 KB)을 크게 상회하는 값.
# 이 상한을 넘는 입력은 프론트매터 처리 전에 거부한다.
MAX_FRONTMATTER_INPUT_CHARS = 1_000_000  # 1MB


def extract_description(body: str, max_len: int = 150) -> str:
    """body 첫 문단에서 description 추출, max_len 자 제한."""
    body = body.strip()
    if not body:
        return ""
    # 첫 번째 문단 (빈 줄 또는 H2 전까지)
    para = body.split("\n\n")[0].strip()
    # 첫 1-2 문장 (마침표/물음표/느낌표로 분리)
    sentences = re.split(r'(?<=[.!?])\s+', para)
    desc = sentences[0] if sentences else para
    if len(desc) < 30 and len(sentences) > 1:
        desc = " ".join(sentences[:2])
    # 따옴표 이스케이프
    desc = desc.replace('"', '\\"').replace("'", "\\'")
    # max_len 자 제한
    if len(desc) > max_len:
        desc = desc[:max_len - 3] + "..."
    return desc


def build_frontmatter(post: dict, body: str) -> str:
    """post dict + body로 완전한 Hugo 마크다운 문자열 조립.

    frontmatter를 코드에서 직접 생성하여 AI의 FM 누수 문제를 구조적으로 방지.
    """
    title = (post.get("title") or "").replace('"', '\\"')
    tags = post.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    tags_str = ", ".join(f'"{t}"' for t in (tags or []))
    cats = (post.get("category_guess") or post.get("category") or "일반").replace('"', '\\"')

    # description: body 첫 1-2문장에서 추출 (AI가 생성한 description 보존)
    desc = extract_description(body)

    fm = (
        f"---\n"
        f'title: "{title}"\n'
        f'description: "{desc}"\n'
        f"draft: true\n"
        f"tags: [{tags_str}]\n"
        f'categories: ["{cats}"]\n'
        f"featureimage: \"\"\n"
        f"---\n\n"
    )
    return fm + body


def ensure_frontmatter_closer(draft_md: str) -> str:
    """frontmatter closer가 없으면 보정."""
    if not draft_md.startswith("---"):
        return draft_md
    end = draft_md.find("---", 3)
    if end != -1:
        return draft_md
    # closer 없음: 첫 빈 줄 앞에 closer 삽입
    rest = draft_md[3:].lstrip("\n")
    lines = rest.split("\n")
    for i, line in enumerate(lines):
        if not line.strip():
            fm = "\n".join(lines[:i])
            body = "\n".join(lines[i:])
            return "---\n" + fm + "\n---\n" + body
    # 빈 줄 없으면 전체를 frontmatter로 간주
    return "---\n" + rest + "\n---\n"


def ensure_frontmatter(draft_md: str, post: dict) -> str:
    """
    draft_md에 frontmatter가 없으면 build_frontmatter()로 생성.
    ---가 있는 경우는 AI가 FM을 생성한 경우 → 그대로 보존 (fallback).
    Phase 24: 단순화 — 더블 FM 병합 로직 제거, FM 생성은 build_frontmatter()에 위임.
    """
    # T-26-02: 입력 크기 상한 (DoS 완화)
    if draft_md and len(draft_md) > MAX_FRONTMATTER_INPUT_CHARS:
        raise ValueError(
            f"draft_md가 허용 상한({MAX_FRONTMATTER_INPUT_CHARS}자)을 초과했습니다"
        )
    if not draft_md or not draft_md.strip():
        return draft_md

    # T-26-01: 메타데이터 검증 — post는 반드시 dict (주입성 frontmatter 방지)
    if not isinstance(post, dict):
        raise ValueError("post는 dict 여야 합니다")

    # 이미 frontmatter가 있으면 (---로 열리고 닫힘) 보존
    if draft_md.strip().startswith("---"):
        end = draft_md.find("---", 3)
        if end != -1 and "title:" in draft_md[3:end]:
            return draft_md  # 정상 FM → 보존
        # FM이 있지만 깨진 경우 → body로 간주하고 build_frontmatter로 재생성
        body = draft_md
        if end != -1:
            # ---...--- 블록 제거
            body = draft_md[end + 3:].lstrip("\n")
        return build_frontmatter(post, body)

    # FM 없음 → build_frontmatter로 생성
    return build_frontmatter(post, draft_md)
