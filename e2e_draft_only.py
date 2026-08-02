"""Phase 36 E2E 단계 2: 기존 체인(10015)에 대해 draft만 실행 + 덤프.

- create_chain 호출 없음 (이미 저장된 체인 사용).
- draft_chain(chain_id, seed) → post별 초안 생성 → DB 업데이트.
- 결과를 .planning/phase36/e2e/ 로 덤프.

사용: python3 e2e_draft_only.py <chain_id> <seed>
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mc_paths import classify_keyword, resolve_chain_type  # noqa: E402
import chain_db as db  # noqa: E402

E2E_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".planning/phase36/e2e")


def main() -> None:
    chain_id = int(sys.argv[1]) if len(sys.argv) > 1 else 10015
    seed = sys.argv[2] if len(sys.argv) > 2 else "스파라쿠아"

    db.init_db()
    chain = db.get_chain(chain_id)
    if not chain:
        print(f"[e2e] ❌ chain {chain_id} 없음 — 중단")
        sys.exit(1)
    print(f"[e2e] chain {chain_id}: seed='{chain['seed']}', status={chain['status']}")

    from chain_drafter import draft_chain
    print(f"\n{'='*60}\n[e2e] Drafting chain #{chain_id}\n{'='*60}")
    t0 = time.time()
    drafted = draft_chain(chain_id, seed, use_context=True)
    elapsed = round(time.time() - t0, 1)
    print(f"[e2e] Draft 완료: {len(drafted)} posts, {elapsed}s")

    dump = {
        "chain_id": chain_id,
        "seed": seed,
        "elapsed_s": elapsed,
        "posts": [],
    }
    for post in drafted:
        dump["posts"].append({
            "id": post.get("id"),
            "step": post.get("step"),
            "depth": post.get("depth"),
            "title": post.get("title"),
            "target_keyword": post.get("target_keyword"),
            "draft_md_len": len(post.get("draft_md", "")),
            "draft_md": post.get("draft_md", ""),
            "meta": post.get("meta"),
        })
    out_path = os.path.join(E2E_DIR, f"draft_chain{chain_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=2)
    print(f"[e2e] 덤프 저장: {out_path}")


if __name__ == "__main__":
    main()
