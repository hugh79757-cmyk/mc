"""
draft_hub_page.py — 허브 페이지 index.md 자동 생성 (Phase 6)

chain_id → chain_posts 3개 스포크 로드 → 허브 index.md 생성:
  rotcha-blog/content/hub/{slug}/index.md

Frontmatter 패턴 (Blowfish cardView):
  type: hub, cardView: true, showSummary: true, featureimage: ...
"""

import os
import re
from datetime import datetime
from pathlib import Path

import chain_db as db
from mc_paths import load_config


def sanitize_slug(text: str) -> str:
    """한글/영문/숫자 → URL-safe slug. 공백은 - 로."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def draft_hub_page(chain_id: int) -> tuple:
    """
    Generate hub index.md for a chain.
    Returns: (ok: bool, hub_slug_or_error: str)
    """
    cfg = load_config()
    chain = db.get_chain(chain_id)
    if not chain:
        return (False, f"Chain #{chain_id} not found")

    posts = db.get_chain_posts(chain_id)
    if len(posts) < 1:
        return (False, f"Chain #{chain_id} has no posts")

    seed = chain["seed"]
    hub_slug = sanitize_slug(seed) + "-hub"

    # ── 허브 대표 이미지: step 3(techpawz)의 image_url 우선 ──
    feature_image = ""
    for p in posts:
        if p.get("step") == 3 and p.get("image_url"):
            feature_image = p["image_url"]
            break
    if not feature_image and posts[0].get("image_url"):
        feature_image = posts[0]["image_url"]

    # ── description: seed 기반 ──
    description = f"{seed}에 대한 기초부터 심화까지 3가지 깊이로 정리한 완벽 가이드입니다."

    # ── 본문: 스포크 목록 ──
    body_lines = [
        '{{< lead >}}',
        f'{seed}에 대한 3가지 깊이의 가이드를 한곳에 모았습니다.',
        '{{< /lead >}}',
        '',
        '## 시리즈 목록',
        '',
    ]
    for p in posts:
        title = p.get("title", "")
        url = p.get("published_url", "#")
        angle = p.get("angle", "")
        step = p.get("step", "?")
        site = cfg.get("chain_blogs", {}).get(p.get("depth", 0), "?")
        body_lines.append(
            f'{step}. **[{title}]({url})** — {angle} ({site})'
        )

    body_lines.append("")
    body = "\n".join(body_lines)

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # ── Frontmatter (Blowfish) ──
    fm_parts = [
        "---",
        f'title: "{seed} — 완벽 가이드 모음"',
        f'description: "{description}"',
        f"slug: {hub_slug}",
        f"date: {now}",
        "draft: false",
        "type: hub",
        "weight: 10",
        "cardView: true",
        "showSummary: true",
    ]
    if feature_image:
        fm_parts.append(f'featureimage: "{feature_image}"')
    fm_parts.append('categories: ["허브"]')
    tags = [f'"{seed}"', '"가이드"', '"허브"']
    fm_parts.append(f"tags: [{', '.join(tags)}]")
    fm_parts.append("---")

    draft_md = "\n".join(fm_parts) + "\n\n" + body

    # ── Hugo content/hub/{slug}/index.md 저장 ──
    rotcha_root = Path(cfg["sites"]["rotcha"]["hugo_root"])
    hub_dir = rotcha_root / "content" / "hub" / hub_slug
    hub_dir.mkdir(parents=True, exist_ok=True)
    index_md = hub_dir / "index.md"
    index_md.write_text(draft_md, encoding="utf-8")

    # ── DB 업데이트 ──
    lid = db.insert_loop_chain(chain_id, hub_slug, spokes_count=len(posts))
    for p in posts:
        db.set_loop_role(p["id"], "spoke")

    print(f"  [hub] ✅ Hub draft created: {index_md}")
    print(f"  [hub]    {len(posts)} spokes linked, loop_chain_id={lid}")

    return (True, hub_slug)


if __name__ == "__main__":
    import sys
    cid = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    ok, slug = draft_hub_page(cid)
    print(f"OK: {slug}" if ok else f"FAIL: {slug}")
