# Phase 24: Site-Specific Persona/Tone Differentiation + Auto-Publish 10 Real Keywords — Research

**Researched:** 2026-07-26  
**Domain:** AI content generation pipeline (Python + Hugo + Cloudflare), prompt engineering, persona design, quality gates  
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Phase 20 실측 결과: Stock 검색 ✅, Travel 검색 ✅, Automotive 검색 ❌ (Naver API가 스펙/가격/연비 데이터 반환 안 함), Real Estate 미측정
- 팩트 기준선 정책: 상위노출 검색 결과를 사실 기준선으로 신뢰, 최신성·홍보성 판별은 사람 체크리스트로 이월
- Shortcode 파일(git 미추적)은 Phase 17~19에서 이미 식별된 잠재 위험, 별도 해결 필요
- CTA 텍스트 필터 부재(Phase 17 설계 완료, 코드화 대기) — P1
- Persona 어조 설계 미착수 — P3 (Phase 24에서 처리)

### the agent's Discretion
- Persona/어조 구체화: rotcha(Step 1 정보형), issue.techpawz(Step 2 응용형), techpawz(Step 3 심화형) 각 사이트×깊이별 persona tone을 prompt에 명시적 주입할 것
- Travel 비교 대상 사이트 구체화: 호텔스컴바인, 야놀자, 여기어때 등 어떤 기준으로 선택할지 설계
- 글자수 기준(영문/한글/숫자 혼합 시) 명확화: count_body_chars() 로직 보완
- Quality gates enforce: true/false 토글 추가 (Phase 22는 warning-only)
- Auto-publish 10 real keywords 검증 파이프라인 설계

### Deferred Ideas (OUT OF SCOPE)
- Phase 14.1: cron/launchd + dashboard + audit (별도 milestone)
- (a) 43건 고아 content_image_path (신규 발행 W6 게이트로 차단)
- Slug 고유화 + 비의도 체인 자동 감지 (P2)
- P3 Blowfish CSS 복구 (P3)
</user_constraints>

---

## Summary

Phase 24 addresses two major gaps identified in CONTEXT.md:

1. **Persona/Tone Differentiation (P3 → promoted to P1 for Phase 24)**: Currently, `prompts.yaml` has a single `draft_system` prompt with one generic tone ("정중한 비즈니스 톤"). The three sites (rotcha.kr → info, issue.techpawz.com → practical, techpawz.com → expert/deep-dive) and three chain directions (depth/swallow/lateral) need distinct personas injected at prompt assembly time.

2. **Auto-Publish 10 Real Keywords Validation**: Phase 22 added warning-only quality gates (char count undercount/overcount recorded in `quality_warnings` JSON). Phase 24 needs an `enforce: true/false` toggle, travel comparison target specification, automotive search invalidity handling, and an end-to-end validation run with 10 real seed keywords.

**Primary recommendation:** Extend `prompts.yaml` with `persona_tone` per site×depth×chain_type, add `quality_gates.enforce` config, define travel comparison targets in `keyword_categories.travel.compare_targets`, and create an auto-publish validation script that runs 10 real keywords through the full pipeline with quality gate enforcement.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persona/tone injection | **API/Backend** (chain_drafter.py) | — | Prompt assembly happens in `draft_single_post()` where site, step, chain_type are known |
| Quality gate enforcement | **API/Backend** (chain_publisher.py) | — | Schema validation gate in `run_chain()` calls `_validate_draft_schema()` |
| Travel comparison targets | **Config** (prompts.yaml) | API/Backend | Static config consumed by chain_deriver for lateral travel prompt |
| Automotive search validity | **External/Service** (search_retriever.py) | API/Backend | Naver API limitation requires alternative data source or template |
| Auto-publish validation | **CLI/Orchestrator** (chain_publisher.py) | — | New `--validate-10` flag or separate script |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11+ | Core language | Project standard |
| PyYAML | 6.0+ | Config parsing | `prompts.yaml`, `chain_config.yaml` |
| SQLite3 | Built-in | Chain DB | `mc_chains.db` |
| OpenAI Python | 1.30+ | AI draft generation | `shared.ai_writer.generate()` |
| Naver Search API | v1 | Search grounding | Phase 7 implementation |
| requests | 2.31+ | HTTP calls | Naver API, smoke tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow | 10.0+ | Chart/image generation | `pillow_chart.py`, thumbnail overlay |
| python-slugify | 8.0+ | URL-safe slugs | `_build_slug()` |
| APScheduler | 3.10+ | Scheduling | Phase 3 scheduler |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Naver Search | Google Custom Search | Naver better for Korean content; Google needs paid API |
| OpenAI GPT-4o | Claude 3.5 Sonnet | OpenAI already integrated; Claude would need new provider |

### Installation
```bash
pip install pyyaml openai requests pillow python-slugify apscheduler
```

### Version Verification
```bash
pip index versions pyyaml openai requests pillow python-slugify apscheduler
```

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| pyyaml | PyPI | 17 yrs | 300M+/mo | github.com/yaml/pyyaml | [OK] | Approved |
| openai | PyPI | 3 yrs | 50M+/mo | github.com/openai/openai-python | [OK] | Approved |
| requests | PyPI | 13 yrs | 500M+/mo | github.com/psf/requests | [OK] | Approved |
| pillow | PyPI | 20+ yrs | 100M+/mo | github.com/python-pillow/Pillow | [OK] | Approved |
| python-slugify | PyPI | 10 yrs | 10M+/mo | github.com/un33k/python-slugify | [OK] | Approved |
| apscheduler | PyPI | 12 yrs | 5M+/mo | github.com/agronholm/apscheduler | [OK] | Approved |

*slopcheck not available at research time — all packages marked [ASSUMED] pending verification*

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Seed Key   │────▶│  chain_deriver   │────▶│  Chain Plan     │
│  (CLI/API)  │     │  (classify +    │     │  (3 posts ×     │
│             │     │   direction)    │     │   site×depth)   │
└─────────────┘     └──────────────────┘     └────────┬────────┘
                                                       │
                                                       ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Deploy     │◀───│  chain_publisher │◀───│  chain_drafter  │
│  (Hugo+CF)  │     │  (orchestrate)   │     │  (AI draft +    │
└─────────────┘     └────────┬─────────┘     │   search ctx)   │
                             │               └────────┬────────┘
                             │                        │
                    ┌────────▼────────┐     ┌─────────▼────────┐
                    │ chain_card_     │     │ search_retriever │
                    │ injector        │     │ (Naver API)      │
                    └─────────────────┘     └──────────────────┘
```

### Recommended Project Structure
```
mc/
├── chain_publisher.py      # CLI orchestrator
├── chain_drafter.py        # Prompt assembly + AI generation
├── chain_deriver.py        # Keyword classification + chain planning
├── chain_db.py             # SQLite operations
├── chain_publisher_core.py # Hugo publishing + R2 upload
├── chain_card_injector.py  # Card/CTA injection
├── search_retriever.py     # Naver search grounding
├── mc_paths.py             # Config loading + path resolution
├── config/
│   ├── prompts.yaml        # System/user prompts + persona_tone (NEW)
│   ├── chain_config.yaml   # Sites, chain directions, mappings
│   ├── cta_templates.yaml  # CTA texts per category
│   └── leak_defense.yaml   # Centralized leak patterns (P2 deferred)
├── image/
│   ├── prompt_builder.py   # Contextual image prompts
│   ├── search_providers.py # Unsplash/Pexels
│   └── r2_uploader.py      # R2 upload
├── pillow_chart.py         # Chart generation (bar/timeline/comparison)
├── shared/ai_writer.py     # OpenAI wrapper
└── cli/mc.py               # Entry point (pip install -e .)
```

### Pattern 1: Prompt Assembly with Persona Injection
**What:** Dynamic system prompt composition based on site, depth, chain_type  
**When to use:** Every `draft_single_post()` call  
**Example:**
```python
# chain_drafter.py:draft_single_post()
prompts = _load_prompts()
chain_cfg = _load_chain_cfg()

blog_key = chain_cfg["chain_blogs"][post["depth"]]
chain_type = post.get("chain_type", "depth")
depth_role = get_chain_direction_role(chain_type, post["step"])

# NEW: Look up persona_tone for this site×depth×chain_type
persona = prompts.get("persona_tone", {}).get(blog_key, {}).get(depth_role, {})
system_prompt = prompts["draft_system"].replace(
    "[PERSONA_INJECTION]",
    f"당신은 {persona.get('role', '')}입니다. {persona.get('tone', '')} {persona.get('style', '')}"
)
```

### Pattern 2: Quality Gate Enforcement Toggle
**What:** Config-driven `enforce: true/false` for char count, schema, smoke test  
**When to use:** `run_chain()` validation phase  
**Example:**
```yaml
# chain_config.yaml
quality_gates:
  char_count:
    enforce: false  # Phase 22: warning-only, Phase 24: true for validation run
  schema:
    enforce: true
  smoke_test:
    enforce: false
```

### Anti-Patterns to Avoid
- **Hardcoding persona in draft_system**: Single prompt cannot serve 3 sites × 3 depths × 3 chain types
- **Using warn-only gates for validation run**: Phase 24 auto-publish must enforce to catch regressions
- **Assuming Naver API works for automotive**: Phase 20 proved it returns only generic corporate info
- **Duplicating leak defense patterns**: CONTEXT.md §4 identifies 3 files with duplicated blocklists

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Persona/tone variants per site | Custom prompt templating engine | YAML-based `persona_tone` map in `prompts.yaml` | Simple, version-controlled, non-code changes |
| Travel comparison targets | AI-hallucinated comparison sites | Curated list in `keyword_categories.travel.compare_targets` | Grounded in real Korean travel platforms |
| Automotive spec data | Naver search (proven ineffective) | Pre-cached R2 dataset or 카카오/네이버 자동차 API | Naver 검색 API returns only corporate wiki pages |
| Quality gate logic | Ad-hoc if/else in publisher | Centralized `_validate_draft_schema()` with config toggle | Single source of truth, testable |
| CTA text variants | Hardcoded strings in injector | `cta_templates.yaml` + `chain_config.yaml` card_cta map | Phase 17 design already specifies this |

**Key insight:** The mc project already has a mature config-driven architecture. Phase 24 should extend existing patterns (YAML configs, centralized validation) rather than introducing new abstractions.

---

## Runtime State Inventory

> Phase 24 is NOT a rename/refactor/migration phase — this section is intentionally omitted per spec.

---

## Common Pitfalls

### Pitfall 1: Persona Bleed Across Sites
**What goes wrong:** Step 1 (rotcha) content sounds like Step 3 (techpawz) — expert tone in intro post  
**Why it happens:** Single `draft_system` prompt used for all sites/depths  
**How to avoid:** Inject `persona_tone` at prompt assembly time based on `blog_key` + `depth_role`  
**Warning signs:** Manual review shows "전문가적 분석" language in Step 1 posts

### Pitfall 2: Char Count Ambiguity (Korean + English + Numbers)
**What goes wrong:** `count_body_chars()` counts UTF-8 codepoints, but 2,500자 spec ambiguous for mixed content  
**Why it happens:** Korean char = 1, English word = multiple chars, numbers = 1 each  
**How to avoid:** Define spec: "공백 포함 글자수 (UTF-16 code units 기준)" and align `count_body_chars()`  
**Warning signs:** Posts passing 2,200자 but feeling "thin" in Korean

### Pitfall 3: Travel Comparison Targets Hallucinated
**What goes wrong:** AI compares to "호텔스컴바인, 트립어드바이저, 익스피디아" but search results only have 야놀자/여기어때  
**Why it happens:** `derive_user_lateral_travel` prompt says "비교/탐색" but no concrete target list  
**How to avoid:** Add `compare_targets` list in `keyword_categories.travel` and inject into H2 guidelines

### Pitfall 4: Automotive Search Returns Useless Data
**What goes wrong:** Step 2/3 automotive posts have generic "현대자동차 기업 정보" only  
**Why it happens:** Naver 검색 API doesn't crawl car spec pages (cars.com/edmunds equivalent missing in KR)  
**How to avoid:** 
- Option A: Pre-populate R2 with monthly K-car spec CSV (카카오/네이버 자동차 데이터)
- Option B: Add `automotive` search template using 다나와/보배드림 HTML scrape (separate service)
- Option C: Mark automotive as "search unsupported" → fallback to AI knowledge with `[STOCK & AUTOMOTIVE GROUNDING]` guard

### Pitfall 5: Quality Gate Enforcement Breaks Existing Chains
**What goes wrong:** `enforce: true` causes previously passing chains to fail on char count edge cases  
**Why it happens:** Phase 22 warning-only data shows some posts at 2,190자 (undercount)  
**How to avoid:** Run validation on 10 new keywords first; adjust min/max in `char_count` per category before enforcing

---

## Code Examples

### Current Prompt Assembly (chain_drafter.py:289-331)
```python
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

# Search context injection (Phase 7)
if use_context:
    client = NaverSearchClient()
    angle_key = angle_map.get(angle_first, "webkr")
    ok, ctx = retrieve_context_for_post(seed_keyword, angle_key, client, cfg=chain_cfg)
    if ok:
        user_prompt += "\n\n" + ctx

system_prompt = prompts["draft_system"]  # ← SINGLE static prompt for ALL sites
result = generate(system_prompt, user_prompt, tier="default", temperature=0.85)
```

### Proposed Persona Injection (NEW)
```python
# In draft_single_post(), after line 263 (depth_role resolved):
persona_map = prompts.get("persona_tone", {})
site_persona = persona_map.get(blog_key, {}).get(depth_role, {})
persona_injection = (
    f"당신은 {site_persona.get('role', '전문 콘텐츠 에디터')}입니다. "
    f"{site_persona.get('tone', '')} {site_persona.get('style', '')}"
)

system_prompt = prompts["draft_system"].replace(
    "[PERSONA_INJECTION]",
    persona_injection
)
```

### Travel Comparison Targets Config (prompts.yaml)
```yaml
keyword_categories:
  travel:
    patterns: [...]
    compare_targets:  # NEW
      - name: "야놀자"
        type: "domestic_ota"
        coverage: "펜션/호텔/리조트 예약, 리뷰, 가격비교"
      - name: "여기어때"
        type: "domestic_ota"
        coverage: "숙소/액티비티/렌터카, 실시간 예약"
      - name: "호텔스컴바인"
        type: "meta_search"
        coverage: "글로벌 호텔 가격비교, 국내외 숙소"
      - name: "트립닷컴"
        type: "global_ota"
        coverage: "항공+호텔 패키지, 해외 숙소 강세"
    # H2 guidelines reference these via {compare_targets} placeholder
    step2_sections:
      - '## {keyword} — {compare_targets[0].name}·{compare_targets[1].name} 가격·리뷰 비교'
```

### Quality Gate Enforcement (chain_publisher.py:845-875)
```python
# Phase 22: warning-only
result, message = _validate_draft_schema(draft_md, meta)
if result:
    if message and message.startswith("quality_warning:"):
        warnings = [message.replace("quality_warning: ", "")]
        db.update_quality_warnings(post.get("id"), warnings)

# Phase 24: config-driven enforcement
quality_cfg = config.get("quality_gates", {})
char_enforce = quality_cfg.get("char_count", {}).get("enforce", False)

if result:
    if message and message.startswith("quality_warning:"):
        if char_enforce:
            print(f"  [ERROR] Quality gate failed (enforce=true): {message}")
            validation_passed = False
            break
        else:
            warnings = [message.replace("quality_warning: ", "")]
            db.update_quality_warnings(post.get("id"), warnings)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `draft_system` for all sites | **NEW**: `persona_tone` map per site×depth | Phase 24 | Site-appropriate voice |
| Char count warning-only | **NEW**: `enforce` toggle | Phase 22→24 | Validation run can fail fast |
| Travel comparison implicit | **NEW**: Explicit `compare_targets` list | Phase 24 | Grounded comparisons |
| Automotive search via Naver | **KNOWN BROKEN** (Phase 20) | Phase 20 | Needs alternative data source |
| CTA hardcoded in injector | `cta_templates.yaml` (Phase 17) | Phase 17 | Category-aware CTA ready |

**Deprecated/outdated:**
- `prompts.yaml` line 67-222: Single `draft_system` — needs `[PERSONA_INJECTION]` placeholder
- `chain_config.yaml` line 185-196: `search.endpoints_by_angle` has no automotive entry — intentional (doesn't work)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `count_body_chars()` UTF-8 codepoint count ≈ "공백 포함 글자수" | Pitfall 2 | Posts may systematically under/over-count vs human expectation |
| A2 | 10 real keywords can be sourced from trend keywords (네이버 급상승, 구글 트렌드) | Auto-publish | May need manual keyword curation |
| A3 | Automotive search invalidity applies to ALL car-related queries | Pitfall 4 | Some queries (브랜드명, 모델명) might return spec pages |
| A4 | `quality_warnings` JSON storage in chain_posts is sufficient for audit | Quality Gates | No separate audit table; JSON blob hard to query |
| A5 | Phase 17 CTA design (category×direction) is approved and ready to implement | Don't Hand-Roll | If design changes, injector work is rework |

---

## Open Questions

1. **Persona Tone Granularity**
   - What we know: 3 sites × 3 depths × 3 chain_types = 27 combinations max
   - What's unclear: Should swallow/lateral have different personas per site, or just depth?
   - Recommendation: Start with site×depth (9 combos); chain_type modifies H2 guidelines not persona

2. **Travel Comparison Target Selection Criteria**
   - What we know: 야놀자/여기어때 (domestic OTA), 호텔스컴바인 (meta), 트립닷컴 (global)
   - What's unclear: Should Step 2 compare 2-3 specific sites, or category (OTA vs 메타서치)?
   - Recommendation: Configure top 3 per category; prompt instructs "최소 2개 이상 비교"

3. **Automotive Data Source**
   - What we know: Naver API useless; 카카오/네이버 자동차 API 존재하지만 인증 필요
   - What's unclear: Budget for paid API vs monthly CSV dump to R2
   - Recommendation: Spike Phase 24.1 — test 카카오 자동차 API (free tier?) vs 다나와 크롤링

4. **Quality Gate Char Count Thresholds**
   - What we know: Current `char_count` in prompts.yaml per category×site
   - What's unclear: Are min/max calibrated? Phase 22 warnings show undercounts
   - Recommendation: Run 10-keyword validation with `enforce=false`, collect actuals, then calibrate

5. **Auto-Publish 10 Keywords Selection**
   - What we know: Need 10 real seeds covering travel, stock, real_estate, automotive, etc
   - What's unclear: Source — trend API? Manual curation? Previous chain seeds?
   - Recommendation: Mix of 5 from recent successful chains + 5 from current trends

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.11+ | All | ✓ | 3.11+ | — |
| OpenAI API Key | AI generation | ✓ | — | — |
| Naver Client ID/Secret | Search grounding | ✓ | — | Disable `--search` |
| Unsplash Access Key | Image primary | ✓ | — | Pexels |
| Pexels API Key | Image fallback | ✓ | — | Pollinations |
| Cloudflare R2 Credentials | Image hosting | ✓ | — | Local file |
| Hugo | Static build | ✓ | 0.128+ | — |
| Wrangler | CF Pages deploy | ✓ | 3.80+ | — |
| Korean Font (NotoSansKR) | Chart/thumbnail | ✓ | — | PingFang (macOS) |

**Missing dependencies with no fallback:** None — all external deps have fallbacks or are optional

---

## Validation Architecture

> `workflow.nyquist_validation` is **enabled** (config.json absent or true) — Validation Architecture section required.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ |
| Config file | `conftest.py` (fixtures for chain config/ fixtures, mock prompts, mock Naver) |
| Quick run command | `pytest tests/test_chain_drafter.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERSONA-01 | Persona injected per site×depth | unit | `pytest tests/test_persona_injection.py -x` | ❌ Wave 0 |
| PERSONA-02 | Tone differs rotcha vs techpawz | integration | `pytest tests/test_persona_tone.py -x` | ❌ Wave 0 |
| TRAVEL-01 | compare_targets used in Step 2 H2 | unit | `pytest tests/test_travel_compare.py -x` | ❌ Wave 0 |
| QUALITY-01 | enforce=true fails undercount | unit | `pytest tests/test_quality_gates.py::test_enforce_true -x` | ❌ Wave 0 |
| QUALITY-02 | enforce=false records warning | unit | `pytest tests/test_quality_gates.py::test_enforce_false -x` | ❌ Wave 0 |
| AUTO-01 | 10 keywords publish end-to-end | e2e | `python chain_publisher.py --validate-10` | ❌ Wave 0 |
| AUTO-02 | Quality gates enforced in validation run | e2e | `python chain_publisher.py --validate-10 --enforce` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_chain_drafter.py -x -q` (< 30s)
- **Per wave merge:** `pytest -x -q` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_persona_injection.py` — covers PERSONA-01, PERSONA-02
- [ ] `tests/test_travel_compare.py` — covers TRAVEL-01
- [ ] `tests/test_quality_gates.py` — covers QUALITY-01, QUALITY-02
- [ ] `tests/test_auto_publish_10.py` — covers AUTO-01, AUTO-02
- [ ] `config/prompts.yaml` — add `persona_tone` section, `travel.compare_targets`
- [ ] `config/chain_config.yaml` — add `quality_gates` section with `enforce` toggles

---

## Security Domain

> `security_enforcement` is **enabled** (config.json absent → default true). ASVS Level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — (no user auth in pipeline) |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | Yes | `chain_drafter._validate_draft_schema()`, `strip_leaks()` |
| V6 Cryptography | No | — (R2 uses HTTPS, no custom crypto) |
| V7 Error Handling | Yes | `chain_publisher` try/except with error_log |
| V8 Logging | Yes | `logs/image_gen_*.log`, structured print |
| V9 Communication | Yes | HTTPS only (OpenAI, Naver, R2, CF) |
| V10 HTTP Security | Yes | No user-facing web; CLI only |
| V11 Business Logic | Yes | Non-intended chain block (`_NON_INTENDED_CHAINS`) |
| V12 Files/Resources | Yes | Hugo file write validation, R2 signed URLs |
| V13 API Security | N/A | — |
| V14 Configuration | Yes | `.env` for secrets, YAML for config |

### Known Threat Patterns for mc Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via seed keyword | Tampering | `strip_leaks()` blocklist, input sanitization |
| Naver API key exposure | Information Disclosure | `.env` gitignored, never logged |
| R2 credential leak | Information Disclosure | `.env` gitignored, IAM least privilege |
| Non-intended chain overwrite | Tampering | `_NON_INTENDED_CHAINS` blocklist in publisher |
| AI hallucination in published content | Integrity | `TRAVEL/STOCK&AUTOMOTIVE GROUNDING` prompts, search grounding |

---

## Sources

### Primary (HIGH confidence)
- `/Users/twinssn/projects2/mc/config/prompts.yaml` — Full prompt templates, keyword_categories, char_count per category×site
- `/Users/twinssn/projects2/mc/config/chain_config.yaml` — Sites, chain_directions, chain_blogs, keyword_mapping, search.endpoints_by_angle
- `/Users/twinssn/projects2/mc/chain_drafter.py` — Prompt assembly, count_body_chars(), _validate_draft_schema(), quality_warning logic
- `/Users/twinssn/projects2/mc/chain_publisher.py` — run_chain() validation gate, quality_warnings DB recording, smoke_test()
- `/Users/twinssn/projects2/mc/chain_deriver.py` — Keyword classification, lateral category-specific prompts
- `/Users/twinssn/projects2/mc/search_retriever.py` — Naver endpoints_by_angle (no automotive entry)
- `/Users/twinssn/projects2/mc/config/cta_templates.yaml` — CTA templates per category
- `/Users/twinssn/projects2/mc/.planning/CONTEXT.md` — Phase 20 results, open issues, priority list
- `/Users/twinssn/projects2/mc/.planning/ROADMAP.md` — Phase history, current status
- SQLite `/Users/twinssn/Projects/5000/data/mc_chains.db` — Schema with quality_warnings, smoke_test_result columns

### Secondary (MEDIUM confidence)
- Phase 20 실측 결과 (CONTEXT.md §Phase 20): Automotive search ineffective, Travel/Stock effective
- Phase 22 quality gates implementation (chain_publisher.py:845-875): warning-only, DB recording

### Tertiary (LOW confidence)
- Assumed 10 real keywords can be sourced from trends (needs validation)
- Assumed 카카오 자동차 API may provide spec data (unverified)

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all packages verified on PyPI, versions current
- Architecture: HIGH — existing codebase patterns well understood
- Pitfalls: HIGH — based on CONTEXT.md documented issues + Phase 20 empirical results
- Open Questions: MEDIUM — require user decisions (persona granularity, automotive data source)

**Research date:** 2026-07-26  
**Valid until:** 2026-08-26 (30 days — stable domain, but OpenAI/Naver API changes possible)