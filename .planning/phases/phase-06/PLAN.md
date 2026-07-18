# Phase 6: Loop Funnel (Blowfish Hub + 2-CTA Spokes)

**Created:** 2026-07-18  
**Phase Number:** 6 (implements the Loop Funnel originally planned as Phase 4)  
**Mode:** mvp  

## Goal

Spoke(3 posts) → Hub(1 page) → 2-CTA dual funnel. Create a hub page at rotcha.kr/hub/{slug}/ with Blowfish cardView grid linking to 3 existing spoke posts, and inject dual CTA (information + conversion) into each spoke's `draft_md` and republish.

## Design Decisions

| Decision | Value | Why |
|----------|-------|-----|
| Hub domain | rotcha.kr/hub/{slug}/ | Single hub, no new domain |
| Hub template | Blowfish built-in `cardView: true` | No custom layout needed |
| Spoke count | 3 (step 1, 2, 3) | Matches existing chain structure |
| Monetization CTA | Configurable empty slot | Fill later via config |
| Phase number | 6 | Avoids collision with existing "Phase 4 ✅" in ROADMAP |

## Existing Code Constraints (MUST NOT Violate)

- Table name: `chain_posts` (NOT `posts`)
- PublisherCore class name: `PublisherCore` (NOT `Publisher`)
- Rotcha theme: **Blowfish** → `featureimage:` NOT `cover.image:`
- No `_run_cmd()` method — use `_run_wrangler(args, cwd, env)`
- No `_log_publish()` method — use `chain_db.log_publish()`
- `update_post_content()` does NOT rebuild Hugo — use separate publish method
- Blowfish cardView handles hub grid automatically — no custom list.html
- Existing `CardInjector` class must be preserved — add `DualCTAInjector` separately

---

## Wave 1: DB Schema + Config (3 tasks)

### Task 1.1: chain_db.py — Add loop tables and migration

**Files to modify:** `chain_db.py`  
**Change type:** Extension (append new functions, do not modify existing ones)

**Add:**
```python
LOOP_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS loop_chains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id    INTEGER NOT NULL REFERENCES chains(id) ON DELETE CASCADE,
    hub_slug    TEXT NOT NULL,
    hub_url     TEXT,
    spokes_count INTEGER DEFAULT 3,
    status      TEXT NOT NULL DEFAULT 'hub_pending',
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

LOOP_MIGRATIONS_SQL = [
    "ALTER TABLE chain_posts ADD COLUMN loop_role TEXT",
]
```

**New functions:**
- `init_loop_tables()` — executes LOOP_SCHEMA_SQL + LOOP_MIGRATIONS_SQL
- `insert_loop_chain(chain_id, hub_slug, spokes_count=3)` → returns loop_chain_id
- `get_loop_chain(chain_id)` → dict or None
- `update_loop_chain(loop_chain_id, **kwargs)` — updates hub_url, status
- `set_loop_role(post_id, role)` — sets `loop_role` = 'hub' | 'spoke' | NULL
- `get_chain_posts_by_loop_role(chain_id, role)` — filter by loop_role

**Do NOT change:** existing SCHEMA_SQL, MIGRATIONS_SQL, init_db(), or any function signatures.

### Task 1.2: config/chain_config.yaml — Fix theme + add loop section

**Files to modify:** `config/chain_config.yaml`

**Changes:**
1. Fix rotcha theme: `theme: PaperMod` → `theme: Blowfish`
2. Add loop section at end:
```yaml
loop:
  hub_url_base: https://rotcha.kr/hub
  spokes_per_hub: 3
  hub_layout: hub
  cardView: true
  cta:
    info_cta_text: "관련 글 모두 보기 →"
    conv_cta_text: "추천 상품 보기 →"
    conv_cta_url: ""
```

### Task 1.3: rotcha-blog/config.toml — Add hub to mainSections

**Files to modify:** `/Users/twinssn/Projects/rotcha-blog/config/_default/params.toml`

**Change:** `mainSections = ["posts"]` → `mainSections = ["posts", "hub"]`

This ensures Blowfish's cardView layout picks up `.Pages` from the hub section.

---

## Wave 2: Hub Page + Spoke Draft (2 new files)

### Task 2.1: draft_hub_page.py — Hub page MD generator

**New file:** `draft_hub_page.py`

**Goal:** Given a chain_id, load 3 spoke posts from `chain_posts`, generate hub `index.md` at `rotcha-blog/content/hub/{slug}/index.md`.

**Input:** `chain_id: int`

**Logic:**
1. Load chain info: `chain = get_chain(chain_id)`, `posts = get_chain_posts(chain_id)`
2. Build slug: `chain.seed + "-hub"` (slugified)
3. Build featureimage URL: Use step 3 (techpawz) thumbnail from R2 if available
4. Build spoke list for body: Markdown list with title + URL for each post
5. Generate frontmatter:
```yaml
---
title: "{chain.seed} — 완벽 가이드 모음"
description: "{chain.seed}에 대한 기초부터 심화까지 3가지 깊이로 정리한 완벽 가이드"
slug: {slug}
date: {ISO}
draft: false
type: hub
weight: 10
cardView: true
showSummary: true
featureimage: "{R2 thumbnail URL from step 3}"
categories: ["허브"]
tags: ["{chain.seed}", "가이드", "허브"]
---
```
6. Body: Simple intro paragraph per spoke, e.g.:
```markdown
{{< lead >}}
{chain.seed}에 대한 3가지 깊이의 가이드를 한곳에 모았습니다.
{{< /lead >}}

## 시리즈 목록

1. **[{post[0].title}]({post[0].published_url})** — {post[0].angle}
2. **[{post[1].title}]({post[1].published_url})** — {post[1].angle}
3. **[{post[2].title}]({post[2].published_url})** — {post[2].angle}
```
7. Write to `rotcha-blog/content/hub/{slug}/index.md` (create `content/hub/` if not exists)
8. Update DB: `set_loop_role(post_id, 'hub')` for hub post, `set_loop_role(post_id, 'spoke')` for 3 spokes
9. `insert_loop_chain(chain_id, hub_slug)` to record loop state
10. Return `(ok, hub_slug_or_error_msg)`

**Output:** `(True, "hub-slug-name")` or `(False, "error message")`

**Do NOT:** Modify existing chain_posts, overwrite existing spoke content, or use PaperMod frontmatter.

### Task 2.2: draft_loop_spoke.py — Spoke loop role marker

**New file:** `draft_loop_spoke.py`

**Goal:** Record which posts in a chain belong to a loop as spokes.

**Logic:**
1. Load chain posts: `posts = get_chain_posts(chain_id)`
2. For each post, call `set_loop_role(post['id'], 'spoke')`
3. Return count of spokes marked

This is intentionally lightweight — the real work (dual-CTA injection) is in Wave 3.

---

## Wave 3: Dual CTA + Publishing (3 files to extend)

### Task 3.1: chain_card_injector.py — Add DualCTAInjector class

**Files to modify:** `chain_card_injector.py`  
**Change type:** Append new class (do NOT modify existing `CardInjector`)

**New class: `DualCTAInjector`**

```python
class DualCTAInjector:
    def __init__(self, config: dict = None):
        self.config = config or load_config()
    
    def build_dual_cta_html(self, hub_url: str, hub_title: str,
                            info_cta_text: str = None,
                            conv_cta_text: str = None,
                            conv_cta_url: str = "") -> str:
        """Generate dual CTA card HTML.
        
        Structure:
        ┌──────────────────────────────┐
        │  이 시리즈 전체 보기          │
        │  [관련 글 모두 보기 →]         │  ← info CTA
        │                              │
        │  ─── 또는 ───                │
        │                              │
        │  추천 상품                     │
        │  [추천 상품 보기 →]           │  ← conversion CTA (configurable URL)
        └──────────────────────────────┘
        """
        ...
    
    def inject_dual_cta_into_draft(self, draft_md: str,
                                    hub_url: str, hub_title: str,
                                    conv_cta_url: str = "") -> str:
        """Inject dual CTA into draft_md body (after frontmatter)."""
        ...
        return updated_md
    
    def inject_into_post(self, publisher_core, post_id: int,
                          hub_url: str, hub_title: str,
                          conv_cta_url: str = "") -> bool:
        """Full pipeline: load draft_md → inject CTA → re-publish."""
        post = get_post(post_id)
        updated_md = self.inject_dual_cta_into_draft(...)
        # Update DB draft_md
        # Then republish via PublisherCore._publish_hugo()
        ...
```

**CTA HTML design (Blowfish-compatible Tailwind classes):**
```html
<div class="max-w-2xl mx-auto my-8 p-6 bg-neutral-50 dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700">
  <p class="text-lg font-semibold mb-2">이 시리즈 전체 보기</p>
  <p class="text-sm text-neutral-600 dark:text-neutral-400 mb-4">{hub_title} 시리즈의 모든 글을 한곳에서 확인하세요.</p>
  <a href="{hub_url}" 
     class="inline-block w-full text-center px-4 py-3 bg-neutral-800 dark:bg-neutral-100 text-white dark:text-neutral-800 rounded-lg font-medium hover:opacity-90 transition-opacity">
    {info_cta_text}
  </a>
  
  <div class="relative my-4">
    <div class="absolute inset-0 flex items-center"><div class="w-full border-t border-neutral-300 dark:border-neutral-600"></div></div>
    <div class="relative flex justify-center"><span class="bg-neutral-50 dark:bg-neutral-800 px-3 text-sm text-neutral-500">또는</span></div>
  </div>
  
  <p class="text-lg font-semibold mb-2">추천 상품</p>
  <p class="text-sm text-neutral-600 dark:text-neutral-400 mb-4">이 주제와 관련된 추천 상품을 확인해보세요.</p>
  <a href="{conv_cta_url or '#'}" 
     class="inline-block w-full text-center px-4 py-3 bg-amber-600 text-white rounded-lg font-medium hover:bg-amber-700 transition-colors">
    {conv_cta_text}
  </a>
</div>
```

**Key behavior:**
- If `conv_cta_url` is empty string, the conversion CTA button links to `#` (placeholder)
- CTA text comes from `config.loop.cta.*`
- Dual CTA goes at the BOTTOM of the post body (after last H2 section)
- Updates chain_posts.draft_md in DB
- Re-publishes via `PublisherCore.publish_post()` (full hugo build + wrangler deploy)

### Task 3.2: chain_publisher_core.py — Add publish_hub_page()

**Files to modify:** `chain_publisher_core.py`  
**Change type:** Add new method to existing `PublisherCore` class (do NOT modify existing methods)

**New method:**
```python
def publish_hub_page(self, hub_draft: dict) -> tuple:
    """
    Publish a hub page to rotcha-blog.
    hub_draft: {
        'content_dir': 'content/hub',
        'slug': str,
        'draft_md': str,      # already frontmatter-processed
        'featured_image': str # R2 URL or empty
    }
    Returns: (published_url, 'hugo', file_path)
    
    Logic:
    1. Write hub/index.md to rotcha-blog/content/hub/{slug}/index.md
    2. Run hugo build --gc --minify
    3. Run wrangler pages deploy
    4. log_publish
    5. Return URL
    """
    hugo_path = Path(self.config['sites']['rotcha']['hugo_root'])
    content_dir = hub_draft.get('content_dir', 'content/hub')
    slug = hub_draft['slug']
    
    # Create target dir
    target_dir = hugo_path / content_dir / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Write index.md
    index_md = target_dir / 'index.md'
    index_md.write_text(hub_draft['draft_md'], encoding='utf-8')
    
    # Hugo build
    ...same pattern as _publish_hugo but without R2 upload...
    
    # Wrangler deploy
    ...use _run_wrangler['pages', 'deploy', ...]...
    
    # Log
    blog_id = blog_cfg.get('blog_id', '')
    log_publish(blog_id, slug, published_url, 'hugo')
    
    return (published_url, 'hugo', str(index_md))
```

**Do NOT:** Modify `_publish_hugo`, `_publish_blogger`, or `update_post_content`.

### Task 3.3: chain_publisher.py — Add --loop, --hub, --spoke flags

**Files to modify:** `chain_publisher.py`  
**Change type:** Add new argparse flags + handler functions (do NOT modify existing flags)

**New argparse flags:**
```python
parser.add_argument('--loop', action='store_true', help='Full loop: hub + spoke dual-CTA')
parser.add_argument('--hub', action='store_true', help='Generate and publish hub page only')
parser.add_argument('--spoke', action='store_true', help='Inject dual-CTA and republish spokes')
```

**New handler functions (added to existing main() routing):**
```python
def cmd_hub(chain_id, dry_run):
    """1. draft_hub_page → 2. publish_hub_page"""
    ...
    
def cmd_spoke(chain_id, dry_run):
    """1. draft_loop_spoke → 2. DualCTAInjector for each spoke → 3. republish"""
    ...
    
def cmd_loop(chain_id, dry_run):
    """Single transaction: hub → spokes (no duplicate builds)"""
    ...
```

**Execution flow for `--loop`:**
```
cmd_loop(chain_id, dry_run):
  # Phase 1: Hub
  ok, hub_info = draft_hub_page(chain_id)
  if dry_run: log and return
  url, method, path = publisher.publish_hub_page(hub_info)
  
  # Phase 2: Spokes
  for each post in chain_posts:
    if post.loop_role == 'spoke':
      updated_md = injector.inject_dual_cta_into_draft(...)
      publisher.publish_post(blog_key, updated_md, post.slug, ...)  # full rebuild
```

**Routing in main():**
```python
if args.loop:
    cmd_loop(args.chain_id, args.dry_run)
elif args.hub:
    cmd_hub(args.chain_id, args.dry_run)
elif args.spoke:
    cmd_spoke(args.chain_id, args.dry_run)
```

---

## Verification Criteria

| # | Criteria | Command |
|---|----------|---------|
| V1 | All files compile | `python -m py_compile draft_hub_page.py draft_loop_spoke.py chain_db.py chain_card_injector.py chain_publisher.py chain_publisher_core.py` |
| V2 | DB migration success | `python -c "import chain_db as db; db.init_db(); db.init_loop_tables()"` → `sqlite3 ... '.tables'` shows `loop_chains` |
| V3 | Hub dry-run | `python chain_publisher.py --chain-id 9 --hub --dry-run` → shows hub draft path without publishing |
| V4 | Hub actual publish | `python chain_publisher.py --chain-id 9 --hub` → `https://rotcha.kr/hub/{slug}/` accessible |
| V5 | Spoke dual-CTA republish | `python chain_publisher.py --chain-id 9 --spoke` → 3 spokes with dual CTA at bottom |
| V6 | Full loop | `python chain_publisher.py --chain-id 9 --loop` → hub + 3 spokes, 4 deploys total |

## Do NOT

- Modify existing function signatures in PublisherCore or CardInjector
- Use `cover.image` (Blowfish uses `featureimage`)
- Create `layouts/hub/list.html` (Blowfish cardView handles it)
- Create `assets/css/extended/hub.css` (Tailwind handles styling)
- Write `posts` instead of `chain_posts`
- Overwrite existing spoke content (only append dual-CTA HTML)
- Run `--hub` and `--spoke` separately before `--loop` (causes double deploy)

## File Summary

| File | Action | Lines (est.) |
|------|--------|-------------|
| `draft_hub_page.py` | **NEW** | ~80 |
| `draft_loop_spoke.py` | **NEW** | ~30 |
| `chain_db.py` | EXTEND | ~40 |
| `config/chain_config.yaml` | MODIFY | ~10 |
| `rotcha-blog/config/_default/params.toml` | MODIFY | 1 line |
| `chain_card_injector.py` | EXTEND | ~100 |
| `chain_publisher_core.py` | EXTEND | ~50 |
| `chain_publisher.py` | EXTEND | ~60 |

**Total estimated: ~370 lines of new code**
