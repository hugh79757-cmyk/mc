# Phase 6 (Formerly Phase 4): Loop Funnel — Research

## Codebase Audit Summary

### DB Schema (chain_posts)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | PK |
| chain_id | INTEGER | FK → chains.id |
| step | INTEGER | 1, 2, 3 |
| depth | INTEGER | 0, 1, 2 |
| title | TEXT | Post title |
| target_keyword | TEXT | SEO keyword |
| slug | TEXT | URL slug |
| draft_md | TEXT | Full Hugo MD (frontmatter + body) |
| published_url | TEXT | Final URL |
| publish_method | TEXT | 'hugo'/'blogger'/'manual' |
| card_injected | INTEGER | 0/1 |
| status | TEXT | derived/drafted/published/failed |
| hugo_file_path | TEXT | Path to index.md |
| image_url | TEXT | Thumbnail URL |

**No `cover_image_url` or `description` column.** Cover image is in `draft_md` frontmatter; description is inside `draft_md` frontmatter.

### Critical Finding: rotcha-blog Theme = Blowfish (NOT PaperMod)
- `chain_config.yaml` says `theme: PaperMod` for rotcha ❌
- Actual Hugo config: `theme = 'blowfish'` ✅
- Blowfish frontmatter uses `featureimage:` (not `cover.image:`)
- Blowfish supports `cardView: true` for automatic card grid rendering
- No custom layout override needed for hub pages

### rotcha-blog Config
- `mainSections = ["posts"]` → needs `"hub"` added
- Theme: Blowfish, Tailwind CSS, Hugo Pipes

### PublisherCore Methods
- `publish_post(blog_key, draft_md, slug, title, labels, chain_type)` — main entry
- `_publish_hugo(blog_cfg, draft_md, slug, title, labels)` — Hugo build + wrangler deploy
- `update_post_content(blog_key, post_id_or_path, new_content, is_html)` — writes file only (NO build/deploy)
- `_run_wrangler(args, cwd, env)` — wrangler execution helper

### CardInjector (Existing)
- `inject_cards_into_draft(draft_md, next_title, next_url, blog_key, direction)` — single CTA
- `build_card_html(title, url, cta)` — single CTA HTML
- No dual-CTA capability yet

### CLI Flags (Existing)
- `--inject-card` — card injection
- `--inject` — legacy HTML card path
- `--theme-override, --cf-pages-project` — publish overrides
- No `--loop, --hub, --spoke` yet

### Image Modules
- `image/injector.py` (not `image_injector.py`)
- `image/pollinations_client.py`, `image/prompt_builder.py`

## Confirmed Design Decisions (from User)
| Decision | Choice | Rationale |
|----------|--------|-----------|
| D1 Hub location | rotcha.kr/hub/{slug}/ | Single hub domain |
| D2 Spokes per hub | 3 | Matches existing 3-way chain |
| D3 Monetization link | Empty slot (configurable) | Fill later |
| D4 Layout override | Built-in (cardView: true) | Blowfish handles it natively |
| D4-1 UI | Card grid (Blowfish cardView) | No custom CSS needed |
