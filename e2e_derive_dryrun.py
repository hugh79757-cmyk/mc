"""Phase 36 E2E 단계 1: derive만 dry-run (DB 쓰기 없음, 2~3회 반복).

- BUG-001 실효: generate() 반환 content가 truncation 없이 완결됐는지
  (shared.ai_writer._is_truncated 로직 검증 — reasoning_content 추출 포함).
- BUG-002 실효: _parse_derivation이 정상 post 배열(요소 dict) 반환.
- DB 저장 없음 (create_chain/create_chain_post 호출 안 함).
- 회차별 raw 응답을 .planning/phase36/e2e/ 로 덤프.

사용: python3 e2e_derive_dryrun.py <keyword> <runs>
"""
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mc_paths import classify_keyword, resolve_chain_type, load_prompts  # noqa: E402
from chain_deriver import _parse_derivation  # noqa: E402
from shared.ai_writer import generate, _is_truncated  # noqa: E402

E2E_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".planning/phase36/e2e")


def _derive_prompt(seed: str) -> tuple:
    """derive_chain과 동일한 프롬프트 선택 로직 (DB 저장 전까지만 재현)."""
    prompts = load_prompts()
    resolved_type = resolve_chain_type(seed)
    category = classify_keyword(seed)
    derive_key = f"derive_user_{resolved_type}"
    category_key = f"derive_user_lateral_{category}"
    if category_key in prompts:
        derive_key = category_key
    elif resolved_type == "lateral":
        etc_fallback = "derive_user_lateral_etc"
        if etc_fallback in prompts:
            derive_key = etc_fallback
    if derive_key not in prompts:
        derive_key = "derive_user_depth"
        resolved_type = "depth"
    system_prompt = prompts.get("derive_system", prompts.get("derive_system_prompt", ""))
    user_prompt = prompts[derive_key].format(seed=seed, category=category)
    return system_prompt, user_prompt, resolved_type, category


def run_once(seed: str, run_no: int) -> dict:
    system_prompt, user_prompt, resolved_type, category = _derive_prompt(seed)
    t0 = time.time()
    result = generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tier="default",
        temperature=0.85,
    )
    elapsed = round(time.time() - t0, 1)
    content = result.get("content", "")
    finish_reason = result.get("finish_reason")
    model = result.get("model", "?")

    # BUG-001: truncation 판정 — generate 반환 content 자체 + _is_truncated 재검증
    truncated_ret = _is_truncated(content, finish_reason)
    char_count = len(content)
    # JSON 완결성 (직접 확인)
    import json as _json

    json_balanced = False
    if content.strip().startswith("{"):
        json_balanced = content.count("{") == content.count("}")
    elif content.strip().startswith("["):
        json_balanced = content.count("[") == content.count("]")

    # BUG-002: 파싱
    try:
        posts = _parse_derivation(content)
    except Exception as e:
        posts = []
        parse_error = f"{type(e).__name__}: {e}"
    else:
        parse_error = None
    posts_ok = bool(posts) and all(isinstance(p, dict) for p in posts)

    record = {
        "run": run_no,
        "seed": seed,
        "category": category,
        "chain_type": resolved_type,
        "model": model,
        "elapsed_s": elapsed,
        "char_count": char_count,
        "finish_reason": finish_reason,
        "bug001_truncated": truncated_ret,
        "json_balanced": json_balanced,
        "bug002_parsed_posts": len(posts) if posts else 0,
        "bug002_parse_error": parse_error,
        "bug002_posts_ok": posts_ok,
        "raw_content": content,
        "parsed_posts_preview": posts[:3] if posts else [],
        "timestamp": datetime.now().isoformat(),
    }
    return record


def main() -> None:
    seed = sys.argv[1] if len(sys.argv) > 1 else "스파라쿠아"
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    os.makedirs(E2E_DIR, exist_ok=True)
    print(f"[e2e] derive dry-run: seed='{seed}', runs={runs} (DB 쓰기 없음)")

    all_records = []
    for i in range(1, runs + 1):
        print(f"\n{'='*60}\n[e2e {i}/{runs}] derive...\n{'='*60}")
        rec = run_once(seed, i)
        all_records.append(rec)
        print(f"  chars={rec['char_count']} finish={rec['finish_reason']} "
              f"BUG-001 truncated={rec['bug001_truncated']} "
              f"json_balanced={rec['json_balanced']}")
        print(f"  BUG-002 posts={rec['bug002_parsed_posts']} ok={rec['bug002_posts_ok']} "
              f"err={rec['bug002_parse_error']}")

        # raw 덤프 (개별)
        raw_path = os.path.join(E2E_DIR, f"derive_r{rec['run']}_raw.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump({"seed": seed, "run": rec["run"], "raw": rec["raw_content"]},
                      f, ensure_ascii=False, indent=2)
        print(f"  → raw 저장: {raw_path}")

    # 요약 덤프
    summary_path = os.path.join(E2E_DIR, "derive_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            [{k: v for k, v in r.items() if k not in ("raw_content", "parsed_posts_preview")}
             for r in all_records],
            f, ensure_ascii=False, indent=2,
        )
    print(f"\n[e2e] 요약 저장: {summary_path}")
    print(f"[e2e] 완료 — 정상(BUG-001/002 통과) 회차: ",
          [r["run"] for r in all_records
           if not r["bug001_truncated"] and r["bug002_posts_ok"] and r["bug002_parsed_posts"] == 3])


if __name__ == "__main__":
    main()
