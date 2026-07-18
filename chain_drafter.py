"""
chain_drafter.py — 체인 초안 생성 모듈 (Phase 2)

chain_publisher.py 의 인라인 draft_post() / _build_chain_context() 를
이 파일로 분리. prompts.yaml의 draft_system / draft_user 사용.

주요 기능:
  - 단일 포스트 초안 생성 (draft_single_post)
  - 체인 전체 3개 초안 생성 (draft_chain)
  - 초안 파일 output/drafts/{chain_id}/ 저장
  - 운영자 검토 체크포인트 (review_drafts)
"""

import os
import yaml
from pathlib import Path
from datetime import datetime

import mc_paths  # noqa: F401 — side effect: sys.path + 5000 주입
from mc_paths import (
    PROMPTS_PATH, CHAIN_CONFIG_PATH, DRAFTS_DIR,
    get_chain_direction_role, resolve_chain_type
)
from shared.ai_writer import generate
from chain_db import get_chain, get_chain_posts, update_post_draft


# ── 설정 로드 ──────────────────────────────────────────────────────

def _load_prompts() -> dict:
    with open(PROMPTS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_chain_cfg() -> dict:
    with open(CHAIN_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── 체인 컨텍스트 문자열 조립 ──────────────────────────────────────

def _build_prev_context(posts: list[dict], current_step: int) -> str:
    """이전 단계 포스트 정보를 컨텍스트 문자열로 조립."""
    if current_step == 1:
        return "이전 포스트: 없음 (이 글이 체인의 시작입니다)"

    prev = next((p for p in posts if p.get("step") == current_step - 1), None)
    if not prev:
        return "이전 포스트: 없음"

    return (
        f"이전 포스트 ({prev.get('domain', '?')}, Step {prev['step']}):\n"
        f"  제목: {prev['title']}\n"
        f"  각도: {prev.get('angle', '')}\n"
        f"  → 자연스럽게 '앞서 살펴본 [{prev['title']}]에서...' 형식으로 연결"
    )


def _build_next_context(posts: list[dict], current_step: int) -> str:
    """다음 단계 포스트 정보를 컨텍스트 문자열로 조립."""
    if current_step == 3:
        return "다음 포스트: 없음 (이 글이 체인의 끝입니다. 마무리 단락으로 완결)"

    nxt = next((p for p in posts if p.get("step") == current_step + 1), None)
    if not nxt:
        return "다음 포스트: 없음"

    return (
        f"다음 포스트 ({nxt.get('domain', '?')}, Step {nxt['step']}):\n"
        f"  제목: {nxt['title']}\n"
        f"  각도: {nxt.get('angle', '')}\n"
        f"  → 마무리 단락 마지막에 다음 글로의 자연스러운 예고 문장 포함"
    )


# ── slug 생성 ──────────────────────────────────────────────────────

import re

def _build_slug(title: str, keyword: str) -> str:
    """Hugo-safe slug 생성 (keyword 기반 + 날짜 suffix)."""
    base = keyword.lower().strip()
    base = re.sub(r"[^a-z0-9가-힣\s-]", "", base)
    base = re.sub(r"[\s]+", "-", base).strip("-")
    if not base:
        base = "post"
    date_suffix = datetime.now().strftime("%Y%m%d")
    return f"{base}-{date_suffix}"


# ── 단일 포스트 초안 생성 ──────────────────────────────────────────

def draft_single_post(
    post: dict,
    posts: list[dict],
    seed_keyword: str,
) -> str:
    """
    post       : chain_posts 행 dict
    posts      : 같은 chain의 전체 post list (컨텍스트 빌드용)
    seed_keyword : 원본 시드 키워드
    Returns    : Hugo 마크다운 초안 전문 (frontmatter 포함)
    """
    prompts = _load_prompts()

    chain_cfg = _load_chain_cfg()
    blog_key = chain_cfg.get("chain_blogs", {}).get(post["depth"], "?")
    blog_url = chain_cfg.get("sites", {}).get(blog_key, {}).get("base_url", f"https://{blog_key}")
    chain_type = post.get("chain_type", "depth")
    depth_role = get_chain_direction_role(chain_type, post.get("step", 1))

    prev_ctx = _build_prev_context(posts, post.get("step", 1))
    next_ctx = _build_next_context(posts, post.get("step", 1))

    draft_user = prompts["draft_user"]
    user_prompt = draft_user.format(
        blog_name=blog_key,
        blog_url=blog_url,
        target_keyword=seed_keyword,
        title=post["title"],
        angle=post.get("angle", ""),
        category=post.get("category_guess", ""),
        step=post.get("step", 1),
        depth_role=depth_role,
        prev_context=prev_ctx,
        next_context=next_ctx,
    )

    system_prompt = prompts["draft_system"]

    print(f"  [drafter] Step {post.get('step', '?')} ({blog_key}) 초안 생성 중...")
    result = generate(system_prompt, user_prompt, tier="default", temperature=0.85)
    draft_md = result["content"]

    char_count = len(draft_md)
    print(f"  [drafter] Step {post.get('step', '?')} 완료 — {char_count:,}자 (model: {result['model']})")

    return draft_md


# ── 체인 전체 초안 생성 ────────────────────────────────────────────

def draft_chain(chain_id: int, seed_keyword: str) -> list[dict]:
    """
    chain_id의 모든 포스트 초안 생성.
    각 초안을 DB + output/drafts/{chain_id}/ 에 저장.
    Returns: 초안이 추가된 posts list
    """
    posts = get_chain_posts(chain_id)
    if not posts:
        raise RuntimeError(f"chain_id={chain_id} 의 posts가 없습니다")

    drafts_dir = Path(str(DRAFTS_DIR)) / str(chain_id)
    drafts_dir.mkdir(parents=True, exist_ok=True)

    updated_posts = []

    for post in posts:
        draft_md = draft_single_post(post, posts, seed_keyword)

        slug = _build_slug(post["title"], seed_keyword)
        slug = f"{slug}-s{post.get('step', post['depth'] + 1)}"

        # DB 업데이트
        update_post_draft(post["id"], draft_md, slug)

        # 파일 저장
        step = post.get("step", post["depth"] + 1)
        filename = f"step-{step}-{slug}.md"
        file_path = drafts_dir / filename
        file_path.write_text(draft_md, encoding="utf-8")
        print(f"  [drafter] 파일 저장: {file_path}")

        updated_posts.append({
            **post,
            "draft_md": draft_md,
            "slug": slug,
            "draft_file": str(file_path),
        })

    return updated_posts


# ── 운영자 검토 인터페이스 ────────────────────────────────────────

def review_drafts(chain_id: int) -> None:
    """
    생성된 초안 파일 위치 안내 → 운영자 검토 후 Enter로 진행.
    """
    drafts_dir = Path(str(DRAFTS_DIR)) / str(chain_id)
    print(f"\n{'═'*60}")
    print(f"  초안 파일 위치: {drafts_dir}")
    print(f"  3개 파일을 직접 열어 검토/수정하세요.")
    print(f"{'─'*60}")

    for f in sorted(drafts_dir.glob("step-*.md")):
        print(f"  {f.name}")

    print(f"{'═'*60}")
    input("\n  수정 완료 후 엔터를 누르면 이미지 생성 단계로 진행합니다... ")
    print()


# ── CLI test ──
if __name__ == "__main__":
    import sys
    chain_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    seed = sys.argv[2] if len(sys.argv) > 2 else "츄니토리"
    result = draft_chain(chain_id, seed)
    print(f"\nDraft complete: {len(result)} posts")
