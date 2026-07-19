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
import re
import json
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
from search_retriever import NaverSearchClient, retrieve_context_for_post


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


# ── frontmatter 유틸 ──────────────────────────────────────────────────

def _ensure_featureimage(draft_md: str) -> str:
  """frontmatter에 featureimage: "" 필드를 항상 포함시킴 (빈칸 → publisher가 채움)."""
  if not draft_md.startswith("---"):
    return "---\nfeatureimage: \"\"\n---\n\n" + draft_md
  end = draft_md.find("---", 3)
  if end == -1:
    return draft_md
  before_close = draft_md[:end]
  rest = draft_md[end:]
  if "featureimage:" in before_close:
    return draft_md  # 이미 있으면 그대로
  return before_close.rstrip() + "\nfeatureimage: \"\"\n" + rest


def _insert_body_image_marker(draft_md: str) -> str:
  """본문 첫 번째 ## 헤딩 직전에 <!--todo:image--> 마커 삽입."""
  h2_pattern = re.compile(r"^## ", re.MULTILINE)
  m = h2_pattern.search(draft_md)
  if m:
    pos = m.start()
    return draft_md[:pos].rstrip() + "\n\n<!--todo:image-->\n\n" + draft_md[pos:]
  return draft_md  # H2 없으면 건너뜀


def _insert_chart_marker(draft_md: str) -> str:
    """Insert <!--todo:chart--> before first ## heading."""
    h2_pattern = re.compile(r"^## ", re.MULTILINE)
    m = h2_pattern.search(draft_md)
    if m:
        pos = m.start()
        return draft_md[:pos].rstrip() + "\n\n<!--todo:chart-->\n\n" + draft_md[pos:]
    return draft_md


# ── 단일 포스트 초안 생성 ──────────────────────────────────────────

def draft_single_post(
    post: dict,
    posts: list[dict],
    seed_keyword: str,
    use_context: bool = False,
) -> tuple[str, dict]:
    """
    post       : chain_posts 행 dict
    posts      : 같은 chain의 전체 post list (컨텍스트 빌드용)
    seed_keyword : 원본 시드 키워드
    Returns    : (Hugo 마크다운 초안 전문, meta dict)
                 meta: {image_type, image_keyword, image_reason, chart_type, chart_data}
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

    # ── Search context injection (Phase 7) ──
    if use_context:
        try:
            client = NaverSearchClient()
            # Map angle prefix to basic/advanced/expert
            angle_first = post.get("angle", "")[:2]
            angle_map = {"기초": "basic", "분석": "advanced", "전문": "expert",
                         "구매": "basic", "절약": "advanced", "금융": "expert",
                         "주제": "basic", "비교": "advanced", "비즈니스": "expert"}
            angle_key = angle_map.get(angle_first, "webkr")

            chain_cfg = _load_chain_cfg()
            ok, ctx = retrieve_context_for_post(
                seed_keyword, angle_key, client, cfg=chain_cfg,
            )
            if ok:
                context_md = ctx
                from chain_db import update_post_context
                update_post_context(post["id"], ctx)
                user_prompt += "\n\n" + ctx
                print(f"  [drafter] Step {post.get('step', '?')} 검색 컨텍스트 {len(ctx)}자 추가됨")
            else:
                print(f"  [drafter] ⚠️ 검색 결과 없음: {ctx}")
        except Exception as e:
            print(f"  [drafter] ⚠️ 검색 컨텍스트 스킵: {e}")

    system_prompt = prompts["draft_system"]

    print(f"  [drafter] Step {post.get('step', '?')} ({blog_key}) 초안 생성 중...")
    result = generate(system_prompt, user_prompt, tier="default", temperature=0.85)
    raw_output = result["content"]

    # Parse chart JSON from GPT output
    meta = {"image_type": "none", "image_keyword": "", "image_reason": "", "chart_type": None, "chart_data": None}
    draft_md = raw_output

    json_match = re.search(r'```json\s*\n(.*?)\n```', raw_output, re.DOTALL)
    if not json_match:
        # Fallback: GPT sometimes omits closing ```
        json_match = re.search(r'```json\s*\n(.*?)$', raw_output, re.DOTALL)
    if json_match:
        try:
            chart_json = json.loads(json_match.group(1))
            meta["image_type"] = chart_json.get("image_type", "none")
            meta["image_keyword"] = chart_json.get("image_keyword", "")
            meta["image_reason"] = chart_json.get("image_reason", "")
            meta["chart_type"] = chart_json.get("chart_type")
            meta["chart_data"] = chart_json.get("chart_data")
            # Remove JSON block from draft
            draft_md = raw_output[:json_match.start()].rstrip()
        except (json.JSONDecodeError, TypeError) as e:
            print(f"  [drafter] ⚠️ chart JSON 파싱 실패: {e}. image_type=none")
    else:
        # No JSON block found — no chart
        pass

    char_count = len(draft_md)
    print(f"  [drafter] Step {post.get('step', '?')} 완료 — {char_count:,}자 (model: {result['model']})")

    return draft_md, meta


# ── 체인 전체 초안 생성 ────────────────────────────────────────────

def draft_chain(chain_id: int, seed_keyword: str, use_context: bool = False) -> list[dict]:
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
        draft_md, meta = draft_single_post(post, posts, seed_keyword, use_context=use_context)

        # Phase 8: image_type determination
        image_type = meta.get("image_type", "none")
        if image_type == "chart":
            if not meta.get("chart_type") or not meta.get("chart_data"):
                print(f"  [drafter] ⚠️ image_type=chart but chart_type/chart_data missing. Fallback to photo.")
                image_type = "photo"

        # Phase 7: placeholder insertion
        draft_md = _ensure_featureimage(draft_md)
        if image_type == "photo":
            draft_md = _insert_body_image_marker(draft_md)
        elif image_type == "chart":
            draft_md = _insert_chart_marker(draft_md)
        # 'none' → no marker

        slug = _build_slug(post["title"], seed_keyword)
        slug = f"{slug}-s{post.get('step', post['depth'] + 1)}"

        # DB 업데이트
        update_post_draft(post["id"], draft_md, slug)

        # Phase 8: DB에 chart 데이터 저장
        if image_type == "chart":
            from chain_db import update_chart
            update_chart(post["id"], meta["chart_type"], json.dumps(meta["chart_data"], ensure_ascii=False))
        if meta.get("image_keyword"):
            from chain_db import update_post_image
            update_post_image(post["id"], meta["image_keyword"])
        if meta.get("image_reason"):
            from chain_db import update_post_context
            update_post_context(post["id"], meta["image_reason"])

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
