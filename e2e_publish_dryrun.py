"""Phase 36 E2E 단계 3: dry-run 발행 파이프라인 릭 검증 (파일 쓰기/배포 없음).

정화 파이프라인 재현 (chain_publisher_core._publish_hugo의 정제 단계 전까지):
  1. BUG-006 게이트: check_plan_text_ratio(draft_md) — blocked이면 발행 차단.
  2. 본문 정화: strip_leaks(body, context="body") — 반환 후 남은 릭 0건 확인.
  3. FM 정화: strip_frontmatter_meta_leaks — title/description/meta 릭 0건 확인.
  4. 최종 산출물(정화된 full md)에서 has_leaks 스캔 → 0건 확인.
  5. protected(리스트/표/헤더) 내 plan_text_gate 2차 스캔 — T4(BUG-005) 검증.

입력: .planning/phase36/e2e/draft_chain{chain_id}.json
출력: .planning/phase36/e2e/publish_dryrun_chain{chain_id}.json
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chain_publisher_core import check_plan_text_ratio, PLAN_TEXT_RATIO_THRESHOLD  # noqa: E402
from mc.leak_defense import (  # noqa: E402
    has_leaks,
    strip_leaks,
    strip_frontmatter_meta_leaks,
    get_plan_text_patterns,
)

E2E_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".planning/phase36/e2e")


def _split_fm_body(md: str) -> tuple:
    """draft_md를 frontmatter / body로 분리 (--- 블록 첫 2개)."""
    lines = md.splitlines()
    if lines and lines[0].strip() == "---":
        try:
            idx2 = lines.index("---", 1)
            return "\n".join(lines[: idx2 + 1]), "\n".join(lines[idx2 + 1 :])
        except ValueError:
            pass
    return "", md


def _scan_protected_plan_gate(body: str) -> dict:
    """T4(BUG-005) 재현: protected(리스트/표/헤더) 문단 내부 plan_text_gate 스캔."""
    patterns = get_plan_text_patterns()
    dropped = []
    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        is_protected = (
            re.match(r"^\s*[-*+]\s+", stripped)
            or re.match(r"^\s*\|.*\|", stripped)
            or re.match(r"^\s*#{1,6}\s", stripped)
        )
        if is_protected:
            for pat in patterns:
                if pat.search(stripped):
                    dropped.append(stripped[:80])
                    break
    return {"protected_leaks_after": len(dropped), "samples": dropped[:5]}


def main() -> None:
    chain_id = int(sys.argv[1]) if len(sys.argv) > 1 else 10015
    in_path = os.path.join(E2E_DIR, f"draft_chain{chain_id}.json")
    with open(in_path, encoding="utf-8") as f:
        draft = json.load(f)

    report = {"chain_id": chain_id, "threshold": PLAN_TEXT_RATIO_THRESHOLD, "posts": []}
    all_clean = True
    for p in draft["posts"]:
        md = p["draft_md"]
        rec = {"step": p["step"], "target_keyword": p["target_keyword"]}

        # 1) BUG-006 게이트
        gate = check_plan_text_ratio(md)
        rec["gate_ratio"] = gate["ratio"]
        rec["gate_blocked"] = gate["blocked"]
        if gate["blocked"]:
            rec["verdict"] = "BLOCKED"
            report["posts"].append(rec)
            all_clean = False
            continue

        # 2) FM / body 분리 → 정화
        fm, body = _split_fm_body(md)
        body_cleaned, body_report = strip_leaks(body, context="body")
        fm_cleaned, fm_report = strip_frontmatter_meta_leaks(fm)

        # 3) 남은 릭 스캔 (정화 후 최종 산출물)
        full_cleaned = fm_cleaned + "\n\n" + body_cleaned
        leaks_after = has_leaks(body_cleaned, context="body")
        fm_leaks_after = has_leaks(fm_cleaned, context="test")

        # 4) T4 protected 2차 스캔 (정화 후 body 기준)
        prot = _scan_protected_plan_gate(body_cleaned)

        rec.update({
            "body_removed": body_report.get("removed", 0),
            "fm_removed": fm_report.get("removed", 0),
            "body_leaks_after": leaks_after,
            "fm_leaks_after": fm_leaks_after,
            "protected_leaks_after": prot["protected_leaks_after"],
            "protected_samples": prot["samples"],
            "cleaned_md_len": len(full_cleaned),
            "verdict": "CLEAN" if (not leaks_after and not fm_leaks_after
                                   and prot["protected_leaks_after"] == 0) else "LEAKS_REMAIN",
        })
        if rec["verdict"] != "CLEAN":
            all_clean = False
        report["posts"].append(rec)

    report["all_clean"] = all_clean
    out_path = os.path.join(E2E_DIR, f"publish_dryrun_chain{chain_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[e2e] dry-run 발행 검증 (chain {chain_id}) — all_clean={all_clean}")
    for rec in report["posts"]:
        print(f"  step {rec['step']} ({rec['target_keyword']}): gate_ratio={rec['gate_ratio']} "
              f"| body_removed={rec.get('body_removed')} fm_removed={rec.get('fm_removed')} "
              f"| body_leaks_after={rec.get('body_leaks_after')} fm_leaks_after={rec.get('fm_leaks_after')} "
              f"| protected_after={rec.get('protected_leaks_after')} → {rec['verdict']}")
    print(f"[e2e] 리포트 저장: {out_path}")


if __name__ == "__main__":
    main()
