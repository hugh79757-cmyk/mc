# Phase 7 Codebase Context

## DB Schema Verification

Post fields confirmed from `sqlite3 mc_chains.db PRAGMA table_info(chain_posts)`:

| Question | Actual Field | Status |
|----------|-------------|--------|
| keyword 컬럼명 | `target_keyword` | ✅ |
| angle 컬럼명 | `angle` | ✅ |
| draft_md 컬럼명 | `draft_md` | ✅ |
| chain_id 참조 | `chain_id INTEGER NOT NULL REFERENCES chains(id) ON DELETE CASCADE` | ✅ |

Full schema: `chain_posts` has 30 columns including `loop_role` (Phase 6).

## Key File Signatures

### chain_drafter.py
- `draft_chain(chain_id, seed_keyword)` → `list[dict]` — NO `use_context` param yet
- `draft_single_post(post, posts, seed_keyword)` → `str` (markdown)
- `_load_prompts()` → reads `config/prompts.yaml`
- Uses `generate(system_prompt, user_prompt, tier="default", temperature=0.85)` from `shared.ai_writer`
- User prompt template: `prompts["draft_user"]` with format vars: `blog_name, blog_url, target_keyword, title, angle, category, step, depth_role, prev_context, next_context`

### chain_deriver.py
- `derive_chain(seed, chain_type, review_callback, edit_callback)` → `int` (chain_id)
- Posts stored with: `title, target_keyword, key_points, angle, category_guess, bridge_logic, image_prompt, image_keyword`

### chain_db.py
- `get_chain_posts(chain_id)` → `list[dict]` (all columns)
- `update_post_draft(post_id, draft_md, slug)` — updates `chain_posts.draft_md`
- `update_post_status(post_id, status, error_log)` — status management
- `get_post(post_id)` → `Optional[dict]`
- Pattern: conn = get_conn() → execute → commit → close

### chain_publisher.py (CLI)
- `--seed`, `--chain-id`, `--dry-run`, `--draft`, `--publish`, `--loop`, etc.
- No `--search` / `--no-search` flags yet

### config/chain_config.yaml
- No `search:` section exists yet
- Ends at line 144 with `db_path`
- Config structure: `sites.{blog_key}`, `chain_blogs`, `loop`, `ai_writer`, etc.

### config/prompts.yaml
- `draft_user` template uses f-string style: `{blog_name}`, `{target_keyword}`, `{title}`, `{angle}`, `{category}`, `{step}`, `{depth_role}`, `{prev_context}`, `{next_context}`
- Context injection happens at `{prev_context}` and `{next_context}` positions
- No search context section exists yet

### .env
- Current: `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL`
- NO Naver API keys in `mc/.env`

### Naver API Keys (external)
- Located in `/Users/twinssn/.env.common`
- `NAVER_CLIENT_ID=Ss5fmY2dm6QCf9y1cIwV`
- `NAVER_CLIENT_SECRET=HRhD8QKZim`
- Also available: `NAVER_AD_*`, `NAVER_DATALAB_*` keys
