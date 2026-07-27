"""
mc — 체인 주제 도출 모듈 (Phase 2)

키워드 성격 분류 → 방향 결정 → AI derivation → DB 저장
"""

import json
import sys
from typing import Optional

from mc_paths import (
    ensure_5000_on_path, load_config, load_prompts,
    get_chain_blog_key, resolve_chain_type, classify_keyword
)

ensure_5000_on_path()

from shared.ai_writer import generate

import chain_db as db

# ── Category-specific lateral prompt validation (config 자동 로드) ──
def _expected_lateral_keys(prompts: dict) -> list:
    """prompts.yaml의 keyword_categories 키로부터 기대되는 lateral 프롬프트 키 목록 생성.
    새 카테고리를 config에 추가하면 자동으로 검증 대상에 포함됨 (코드 수정 불필요)."""
    categories = prompts.get("keyword_categories", {}) or {}
    return [f"derive_user_lateral_{cat}" for cat in categories.keys()]


def _validate_lateral_prompts(prompts: dict) -> None:
    """로드 시점에 category별 lateral 프롬프트 존재 여부 검증 (config 기반).
    누락 시 경고만 출력 — deriver는 depth 프롬프트로 폴백 가능."""
    expected = _expected_lateral_keys(prompts)
    missing = [k for k in expected if k not in prompts]
    if missing:
        print(f"[mc] ⚠️ Missing lateral prompt(s): {', '.join(missing)}")


def derive_chain(seed: str, chain_type: str = None,
                 review_callback=None, edit_callback=None) -> int:
    """
    1. 키워드 성격 분류 (또는 수동 chain_type 지정)
    2. 방향에 맞는 derive 프롬프트 선택
    3. AI 호출 → JSON 파싱
    4. 검토/편집 (선택적)
    5. DB 저장
    Returns: chain_id
    """
    # ── 1. 키워드 분류 + 방향 결정 ──
    resolved_type = resolve_chain_type(seed, override=chain_type)
    category = classify_keyword(seed)

    print(f"\n{'='*60}")
    print(f"[mc] 🔗 Deriving chain for seed: '{seed}'")
    print(f"    분류: {category} → 방향: {resolved_type}")
    print(f"{'='*60}\n")

    # ── 2. 방향별 프롬프트 선택 ──
    prompts = load_prompts()
    _validate_lateral_prompts(prompts)

    derive_key = f"derive_user_{resolved_type}"

    # Phase 19: category-specific prompt for ALL chain types, not just lateral.
    # stock/automotive/real_estate → depth 방향에서도 category-aware angle 사용.
    category_key = f"derive_user_lateral_{category}"
    if category_key in prompts:
        derive_key = category_key
        if resolved_type == "lateral":
            print(f"    [lateral] Using category-specific prompt: {category_key}")
        else:
            print(f"    [{resolved_type}] Using category-specific prompt: {category_key}")
    elif resolved_type == "lateral":
        etc_fallback = "derive_user_lateral_etc"
        if etc_fallback in prompts:
            derive_key = etc_fallback
            print(f"[mc] ⚠️ No lateral prompt for category '{category}', falling back to 'etc'")
        # else: keep fallback key (= derive_user_lateral generic)

    if derive_key not in prompts:
        print(f"[mc] ⚠️ Prompt '{derive_key}' not found, falling back to depth")
        derive_key = "derive_user_depth"
        resolved_type = "depth"

    system_prompt = prompts.get("derive_system", prompts.get("derive_system_prompt", ""))
    user_prompt = prompts[derive_key].format(seed=seed, category=category)

    # ── 3. AI derivation ──
    result = generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tier="default",
        temperature=0.85,
    )

    content = result.get("content", "")
    print(f"[mc] AI derivation received ({len(content)} chars)\n")

    # ── 4. Parse JSON ──
    posts_data = _parse_derivation(content)
    if not posts_data:
        print("[mc] ❌ Failed to parse AI derivation. Raw content:")
        print(content[:2000])
        return 0

    # ── 5. 검토/편집 ──
    if review_callback:
        posts_data = review_callback(posts_data)
    if edit_callback:
        posts_data = edit_callback(posts_data)

    # ── 6. DB 저장 (with chain_type) ──
    db.init_db()
    chain_id = db.create_chain(seed, depth_count=len(posts_data), chain_type=resolved_type)
    for post in posts_data:
        db.create_chain_post(
            chain_id=chain_id,
            depth=post.get("depth", post.get("step", 1) - 1),
            step=post.get("step", post.get("depth", 0) + 1),
            chain_type=resolved_type,
            title=post.get("title", ""),
            target_keyword=post.get("target_keyword", ""),
            key_points=post.get("key_points", []),
            angle=post.get("angle", ""),
            category_guess=post.get("category_guess", ""),
            bridge_logic=post.get("bridge_logic", ""),
            image_prompt=post.get("image_prompt", ""),
        )

    print(f"\n[mc] ✅ Chain #{chain_id} saved with {len(posts_data)} posts ({resolved_type})")
    _print_chain_summary(chain_id)
    return chain_id


def _parse_derivation(content: str) -> list:
    """AI 응답에서 JSON 배열 파싱 (```json 마크다운 대응)."""
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("chain", "posts", "articles", "items"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []
    except json.JSONDecodeError as e:
        print(f"[mc] ⚠️ JSON parse error: {e}")
        if "[" in content and "]" in content:
            try:
                start = content.index("[")
                end = content.rindex("]") + 1
                data = json.loads(content[start:end])
                return data if isinstance(data, list) else []
            except (json.JSONDecodeError, ValueError):
                pass
        return []


def _print_chain_summary(chain_id: int):
    """방금 생성된 체인 내용 출력."""
    posts = db.get_chain_posts(chain_id)
    chain = db.get_chain(chain_id)
    chain_type = chain["chain_type"] if chain else "?"
    cfg = load_config()
    print(f"  📋 Chain #{chain_id} — {len(posts)} posts (type: {chain_type})")
    for p in posts:
        blog_key = cfg.get("chain_blogs", {}).get(p["depth"], "?")
        direction_role = p.get("angle", "")
        print(f"    Step {p.get('step', '?')} ({blog_key}): {p['title']} [{direction_role}]")


# ── CLI test ──
if __name__ == "__main__":
    seed = sys.argv[1] if len(sys.argv) > 1 else "츄니토리"
    chain_type = sys.argv[2] if len(sys.argv) > 2 else None
    chain_id = derive_chain(seed, chain_type=chain_type)
    print(f"\nDone. Chain ID: {chain_id}")
