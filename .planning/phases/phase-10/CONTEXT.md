# Phase 10 Context: Phase 9 Aftermath — 회귀 방지 및 잔여 이슈 해결

## Goal

Phase 9에서 발견·수정된 모든 fix의 회귀를 방지하고, 3개 사이트에 CSS/SRI 수정을 전파하며, R2 썸네일 업로드 실패의 근본 원인을 수정한다.

## Issues Overview

### Already Fixed (verified in session, need audit confirmation)
| # | Issue | Fix Location | Status |
|---|-------|-------------|--------|
| I1 | JSON metadata prompt leak | `chain_drafter.py` — `_parse_meta_from_json()` | ✅ 완료 |
| I2 | CTA inline block leak | `chain_publisher_core.py` `_sanitize_markdown_body()` + `prompts.yaml` | ✅ 완료 |
| I3 | SRI/CORS CSS 렌더링 (rotcha) | `rotcha-blog` `head.html` + `fixed-fill-blur.html` | ✅ 완료 |

### Partially Fixed / Needs Propagation
| # | Issue | Fix Location | Status |
|---|-------|-------------|--------|
| I4 | SRI/CORS — informationhot, techpawz | 동일 `head.html` + `fixed-fill-blur.html` 수정 필요 | ◆ 미적용 |

### Unresolved (needs root cause → fix)
| # | Issue | Description | Status |
|---|-------|-------------|--------|
| I5 | R2 썸네일 업로드 실패 | 신규 포스트(20260720)의 썸네일이 R2에 전혀 존재하지 않음. 로컬 `output/images/thumb_*.webp`는 존재하나 `upload_all_images()`가 R2에 업로드하지 못함. 원인: `get_r2_client()` credentials 누락? `upload_all_images` 호출 전 R2 키·prefix 전달 실패? | ◆ 조사 중 |

### Missing (never existed, needs creation)
| # | Issue | Description |
|---|-------|-------------|
| I6 | 회귀 방지 audit 체계 부재 | `audit_posts.py` 전수검사 도구 없음. Phase 9 fix들이 차기 체인에서 회귀하는지 탐지 불가 |
| I7 | Phase 9 E2E 검증 미완료 | Phase 9 fix 8개 + 추가 fix 3개(JSON/CTA/SRI)의 통합 검증 안 됨 |

## Locked Scope

- **In:** R2 업로드 디버깅, CSS/SRI 3개 사이트 전파, audit_posts.py, E2E 검증
- **Out:** KREA AI (무기한 연기), 새 이미지 프로바이더, 프롬프트 전면 재작성, Hugo 테마 변경

## Key Constraints

- R2 credentials는 `mde2` 프로젝트의 `app/services/r2_uploader.py`에서 관리
- `upload_all_images()`가 `post_dir/assets/`까지 스캔하도록 되어 있으나 실제로 R2에 업로드 안 됨
- 배포 시 `CLOUDFLARE_API_TOKEN` 등 env를 unset 후 `hugh79757` wrangler 프로필로 실행
- 3개 사이트 Hugo 빌드 명령어가 각각 다름 (rotcha/informationhot/techpawz 각각 hugo --gc --minify)

## Files

| File | Action | Reason |
|------|--------|--------|
| `mde2/app/services/r2_uploader.py` | READ + MODIFY | R2 업로드 credentials + upload_all_images 로직 |
| `chain_publisher_core.py` | READ + MODIFY | upload_all_images 호출 체인 검증 |
| `rotcha-blog/layouts/partials/head.html` | REFERENCE | SRI/CORS 패턴 (다른 사이트 복사용) |
| `rotcha-blog/layouts/partials/header/fixed-fill-blur.html` | REFERENCE | SRI/CORS 패턴 |
| `informationhot-hugo/layouts/partials/head.html` | MODIFY | SRI/CORS 적용 |
| `techpawz-hugo/layouts/partials/head.html` | MODIFY | SRI/CORS 적용 |
| NEW: `audit/audit_chain.py` | CREATE | 전수검사 audit 도구 |
