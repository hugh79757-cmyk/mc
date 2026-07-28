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

from mc.leak_defense import strip_leaks

from chain_models import parse_ai_output, AIParseError, AIOutput

import mc_paths  # noqa: F401 — side effect: sys.path + 5000 주입
from mc_paths import (
    PROMPTS_PATH, CHAIN_CONFIG_PATH, DRAFTS_DIR,
    get_chain_direction_role, resolve_chain_type, classify_keyword
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

def _ensure_frontmatter_closer(draft_md: str) -> str:
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


def _ensure_featureimage(draft_md: str) -> str:
  """frontmatter에 featureimage: "" 필드를 항상 포함시킴 (빈칸 → publisher가 채움)."""
  draft_md = _ensure_frontmatter_closer(draft_md)
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


def _ensure_frontmatter(draft_md: str, post: dict) -> str:
  """
  draft_md에 frontmatter가 없으면 title/tags/categories로 생성.
  이미 frontmatter가 있으면 (---로 열리고 닫히면) 보존.
  Phase 11 W2 _ensure_featureimage와 달리 title/description/tags/categories도 추가.
  """
  if not draft_md or not draft_md.strip():
    return draft_md

  # 이미 유효한 frontmatter가 있는지 확인 (열고 닫는 ---가 모두 존재)
  if draft_md.strip().startswith("---"):
    # 닫는 ---는 반드시 독립 라인이어야 함 (테이블 구분선/수평선과 구분)
    _lines = draft_md.split("\n")
    for _li in range(1, min(len(_lines), 20)):
      if _lines[_li].strip() == "---":
        return draft_md  # frontmatter 이미 있음 → 보존
    # 닫는 --- 없음 → 기존 FM 필드 보존 + 닫는 --- 삽입
    _fm_end = 0
    for _li in range(1, min(len(_lines), 20)):
      _stripped = _lines[_li].strip()
      if not _stripped:
        _fm_end = _li
        break
      if ":" in _stripped:
        _fm_end = _li + 1
      else:
        _fm_end = _li
        break
    _fm_block = "\n".join(_lines[:_fm_end])
    _body = "\n".join(_lines[_fm_end:]).lstrip("\n")
    return _fm_block + "\n---\n\n" + _body

  # frontmatter 생성 (draft_md에 FM 없음)
  title = (post.get("title") or "").replace('"', '\\"')
  tags = post.get("tags", [])
  if isinstance(tags, str):
    tags = [t.strip() for t in tags.split(",") if t.strip()]
  tags_str = ", ".join(f'"{t}"' for t in (tags or []))
  cats = (post.get("category_guess") or post.get("category") or "일반").replace('"', '\\"')

  fm = (
    f"---\n"
    f'title: "{title}"\n'
    f"description: \"\"\n"
    f"draft: true\n"
    f"tags: [{tags_str}]\n"
    f'categories: ["{cats}"]\n'
    f"---\n\n"
  )
  return fm + draft_md


def _insert_body_image_marker(draft_md: str) -> str:
  """본문 첫 번째 ## 헤딩 직전에 <!--todo:image--> 마커 삽입."""
  h2_pattern = re.compile(r"^## ", re.MULTILINE)
  m = h2_pattern.search(draft_md)
  if m:
    pos = m.start()
    return draft_md[:pos].rstrip() + "\n\n<!--todo:image-->\n\n" + draft_md[pos:]

  # H2 헤딩이 없으면 첫 번째 빈 줄 직전에 마커 삽입 (백업 방식)
  lines = draft_md.split('\n')
  for i, line in enumerate(lines):
    if line.strip() == "" and i > 0:  # 빈 줄이고 첫 줄이 아닐 때
      return '\n'.join(lines[:i]) + "\n\n<!--todo:image-->\n\n" + '\n'.join(lines[i:])

  # 그래도 없으면 마지막에 추가
  return draft_md.rstrip() + "\n\n<!--todo:image-->\n\n"


def _insert_chart_marker(draft_md: str) -> str:
    """Insert <!--todo:chart--> before first ## heading."""
    h2_pattern = re.compile(r"^## ", re.MULTILINE)
    m = h2_pattern.search(draft_md)
    if m:
        pos = m.start()
        return draft_md[:pos].rstrip() + "\n\n<!--todo:chart-->\n\n" + draft_md[pos:]
    return draft_md


def _validate_draft_frontmatter(draft_md: str) -> None:
    """Validate frontmatter to catch common YAML issues before publishing.

    Raises ValueError with Korean message if validation fails.
    """
    if not draft_md.startswith("---"):
        return
    end = draft_md.find("---", 3)
    if end == -1:
        return
    fm_text = draft_md[3:end].strip()

    for line in fm_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("title:"):
            val = stripped.split("title:", 1)[1].strip().strip('"').strip("'")
            if ":" in val:
                raise ValueError(f"제목에 콜론(:)이 포함되어 있습니다: {val}")

    for field in ("tags", "categories"):
        lines = fm_text.splitlines()
        for i, l in enumerate(lines):
            if l.strip().startswith(f"{field}:"):
                if i + 1 < len(lines) and lines[i + 1].strip().startswith("-"):
                    raise ValueError(f"{field}가 여러 줄로 작성되었습니다 (한 줄 배열 필요)")
                break


# ── 단일 포스트 초안 생성 ──────────────────────────────────────────

def draft_single_post(
    post: dict,
    posts: list[dict],
    seed_keyword: str,
    use_context: bool = True,
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

    # ── H2 가이드라인 동적 선택 (keyword_categories 기반) ──
    kc = prompts.get("keyword_categories", {})
    kw_category = classify_keyword(seed_keyword)
    cat_config = kc.get(kw_category) or kc.get("etc")
    if not cat_config:
        raise ValueError(
            f"keyword_categories에 '{kw_category}' 카테고리와 etc fallback이 없습니다. "
            f"prompts.yaml keyword_categories 섹션을 확인하세요."
        )
    step_key = f"step{post.get('step', 1)}_sections"
    raw_sections = cat_config.get(step_key)
    if not raw_sections:
        raise ValueError(
            f"keyword_categories.{kw_category}.{step_key}가 비었거나 없습니다. "
            f"카테고리 설정을 확인하세요."
        )
    h2_lines = []
    for i, tmpl in enumerate(raw_sections, 1):
        h2_lines.append(f"{i}. {tmpl.replace('{keyword}', seed_keyword)}")
    h2_guidelines = "\n".join(h2_lines)

    # ── 프롬프트 조립 ──
    draft_user = prompts["draft_user"]
    user_prompt = draft_user.format(
        blog_name=blog_key,
        blog_url=blog_url,
        target_keyword=seed_keyword,
        title=post["title"],
        angle=post.get("angle", ""),
        category=kw_category,
        step=post.get("step", 1),
        depth_role=depth_role,
        prev_context=prev_ctx,
        next_context=next_ctx,
        h2_guidelines=h2_guidelines,
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

    # Parse JSON metadata + extract clean body via single entry point
    try:
        ai_output = parse_ai_output(raw_output)
        draft_md = ai_output.body
        meta = {
            "image_type": ai_output.meta.image_type,
            "image_keyword": ai_output.meta.image_keyword or "",
            "image_reason": ai_output.meta.image_reason or "",
            "chart_type": ai_output.meta.chart_type,
            "chart_data": ai_output.meta.chart_data,
        }
        print(f"  [drafter] AI 출력 파싱 완료 (image_type={meta['image_type']})")
    except AIParseError as e:
        print(f"  [drafter] ⚠️ AI 출력 파싱 실패, 본문만 추출: {e}")
        meta = {"image_type": "none", "image_keyword": "", "image_reason": "", "chart_type": None, "chart_data": None}
        draft_md = raw_output

    draft_md, _ = strip_leaks(draft_md, context="draft")

    char_count = len(draft_md)
    print(f" [drafter] Step {post.get('step', '?')} 완료 — {char_count:,}자 (model: {result['model']})")

    return draft_md, meta


# ── 체인 전체 초안 생성 ────────────────────────────────────────────

def draft_chain(chain_id: int, seed_keyword: str, use_context: bool = True) -> list[dict]:
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
                print(f"  [drafter] ⚠️ image_type=chart but chart_type/chart_data missing. Setting to none.")
                image_type = "none"

        # 이미지 검색어 강제: photo는 AI가 준 추상적 image_keyword를 무시하고
        # 항상 seed_keyword(주제어)로 검색하여 주제 무관 사진(은하/산 등) 방지.
        # chart는 데이터 시각화라 사진 검색과 무관 — 기존 보강 로직 유지.
        if image_type == "photo":
            _seed_kw = (seed_keyword or post.get("title", "")).strip()
            if _seed_kw:
                _ai_kw = str(meta.get("image_keyword") or "").strip()
                meta["image_keyword"] = _seed_kw
                if _ai_kw and _ai_kw != _seed_kw:
                    print(f"  [drafter] image_keyword 주제어 강제: '{_ai_kw}' → '{_seed_kw}'")
                else:
                    print(f"  [drafter] image_keyword 주제어 설정: '{_seed_kw}'")
        elif image_type == "chart" and (not meta.get("image_keyword") or not str(meta.get("image_keyword")).strip()):
            default_keyword = (post.get("title", "") or seed_keyword).strip()
            meta["image_keyword"] = default_keyword
            print(f"  [drafter] image_keyword 자동 보강(chart): '{default_keyword}'")

        # Phase 7: placeholder insertion
        draft_md = _ensure_featureimage(draft_md)
        if image_type == "photo":
            draft_md = _insert_body_image_marker(draft_md)
        elif image_type == "chart":
            draft_md = _insert_chart_marker(draft_md)
        # 'none' → no marker

        # Phase 11 W4: frontmatter 보장 — title/tags/categories로 기존 FM 보존 또는 생성
        draft_md = _ensure_frontmatter(draft_md, post)

        slug = _build_slug(post["title"], seed_keyword)
        slug = f"{slug}-s{post.get('step', post['depth'] + 1)}"

        update_post_draft(post["id"], draft_md, slug)

        from chain_db import ImageMetaDB
        _image_meta = ImageMetaDB(
            image_type=image_type,
            image_keyword=meta.get("image_keyword") or None,
            image_reason=meta.get("image_reason") or None,
            chart_type=meta.get("chart_type"),
            chart_data=meta.get("chart_data"),
        )
        from chain_db import update_image_meta
        update_image_meta(post["id"], _image_meta)

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
            "meta": meta,
        })

    return updated_posts


def count_body_chars(draft_md: str) -> int:
    """
    마크다운에서 순수 본문 글자수 계산.
    제외: frontmatter(---...---), 마크다운 문법(#, *, -, |, ```, [], (), > 등),
         이미지 마커(<!--todo:image-->, <!--todo:chart-->, <!-- image:... -->),
         HTML 주석, JSON 메타데이터 블록
    포함: 한글, 영문, 숫자, 공백, 문장부호(본문 내용)
    """
    if not draft_md or not draft_md.strip():
        return 0

    text = draft_md

    # 1. Frontmatter 제거 (---...--- 블록)
    text = re.sub(r'^---\s*\n.*?\n---\s*\n', '', text, flags=re.DOTALL | re.MULTILINE)

    # 2. 코드 블록 제거 (```...```)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)

    # 3. 인라인 코드 제거 (`...`)
    text = re.sub(r'`[^`]*`', '', text)

    # 4. 이미지 마커 제거 (<!--todo:image-->, <!--todo:chart-->, <!-- image:... -->)
    text = re.sub(r'<!--\s*todo:(image|chart)\s*-->', '', text)
    text = re.sub(r'<!--\s*image:.*?\s*-->', '', text)
    text = re.sub(r'<!--\s*thumbnail:.*?\s*-->', '', text)

    # 5. HTML 주석 제거 (<!-- ... -->)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # 6. JSON 메타데이터 블록 제거 (마크다운 코드블록 밖의 JSON 객체)
    text = re.sub(r'\n\s*\{[^{}]*"image_type"[^{}]*\}\s*$', '', text, flags=re.DOTALL)
    text = re.sub(r'^\s*\{[^{}]*"image_type"[^{}]*\}\s*\n', '', text, flags=re.DOTALL | re.MULTILINE)

    # 7. 마크다운 헤딩 제거 (# ## ### 등)
    text = re.sub(r'^#{1,6}\s+.*$', '', text, flags=re.MULTILINE)

    # 8. 리스트 마커 제거 (-, *, 1., 2. 등) - 줄 전체 제거
    text = re.sub(r'^[\s]*[-*+]\s+.+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+.+$', '', text, flags=re.MULTILINE)

    # 9. 표 관련 제거 (|, ---|--- 등)
    text = re.sub(r'^\|.*\|$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*[-|:]+[\s]*$', '', text, flags=re.MULTILINE)

    # 10. 블록인용 제거 (> )
    text = re.sub(r'^[\s]*>\s*', '', text, flags=re.MULTILINE)

    # 11. 링크 제거 ([text](url) -> text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # 이미지 제거 (![alt](url) -> alt)
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)

    # 12. 강조 마크다운 제거 (**, *, __, _)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # 13. 수평선 제거 (---, ***)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # 14. 공백 정리 (연속된 공백/줄바꿈을 단일 공백으로)
    text = re.sub(r'\s+', ' ', text)

    # 앞뒤 공백 제거
    text = text.strip()

    # 글자수 반환 (한글/영문/숫자/공백/문장부호 모두 1자로 카운트)
    return len(text)


# ── 스키마 검증 게이트 ─────────────────────────────────────────────

def _validate_draft_schema(draft_md: str, meta: dict = None) -> tuple[bool, str]:
    """
    초안 마크다운의 스키마를 검증합니다.

    Args:
        draft_md: 검증할 초안 마크다운 문자열
        meta: 선택적 메타데이터 딕셔너리 (image_keyword, char_count 등을 포함)

    Returns:
        tuple[bool, str]: (검증 결과, 실패 시 원인 메시지)
    """
    if not draft_md or not draft_md.strip():
        return False, "초안이 비어 있습니다"

    # 1. H2 헤딩 검증 (최소 1개)
    h2_pattern = r'^##\s+.+$'
    h2_matches = re.findall(h2_pattern, draft_md, re.MULTILINE)
    if len(h2_matches) < 1:
        return False, "본문에 최소 1개 이상의 H2 헤딩이 필요합니다"

    # 2. 이미지 마커 검증 (<!--todo:image--> 또는 <!--todo:chart-->)
    image_marker_pattern = r'<!--todo:(image|chart)-->'
    image_markers = re.findall(image_marker_pattern, draft_md)
    if not image_markers:
        return False, "이미지 마커(<!--todo:image--> 또는 <!--todo:chart-->)가 필요합니다"

    # Determine if any chart marker is present
    has_chart = '<!--todo:chart-->' in draft_md

    # 3. 이미지 키워드 검증 (meta가 제공되고, 차트 마커가 아닌 경우)
    if meta is not None and not has_chart:
        image_keyword = meta.get('image_keyword') if isinstance(meta, dict) else None
        if not image_keyword or not str(image_keyword).strip():
            return False, "이미지 마커에 대한 image_keyword가 비어 있습니다"

    # 4. Frontmatter 검증 (필수 필드)
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*$'
    frontmatter_match = re.search(frontmatter_pattern, draft_md, re.DOTALL | re.MULTILINE)

    if frontmatter_match:
        frontmatter_content = frontmatter_match.group(1)
        required_fields = ['title', 'description', 'tags', 'categories']

        for field in required_fields:
            # YAML 형식과 평범한 텍스트 형식 모두 지원
            if f'{field}:' not in frontmatter_content:
                return False, f"Frontmatter에 필수 필드 '{field}'가 없습니다"
    else:
        return False, "Frontmatter(---로 시작하는 섹션)가 없습니다"

    # 5. 글자수 검증 (meta에 char_count가 있는 경우)
    if meta and isinstance(meta, dict) and meta.get('char_count'):
        cc = meta['char_count']
        actual = count_body_chars(draft_md)
        if actual < cc.get('min', 0):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"[QUALITY] 글자수 미달: {actual}자 (최소 {cc['min']}자)")
            return True, f"quality_warning: undercount ({actual}/{cc['min']})"
        if actual > cc.get('max', 999999):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"[QUALITY] 글자수 초과: {actual}자 (최대 {cc['max']}자)")
            return True, f"quality_warning: overcount ({actual}/{cc['max']})"

    return True, "스키마 검증 통과"


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
