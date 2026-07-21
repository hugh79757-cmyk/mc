# Context: Phase 11 — HTML 릭 + 광고 겹침 수정

## Goal

진단 리포트(`docs/diagnostics/2026-07-html-leak-ad-overlap.md`)에서 도출된 5개 Wave 수정을 위험도 낮은 순으로 순차 실행한다. 각 Wave는 pytest 50/50 통과 + 1페이지 라이브 검증 후 머지한다.

## Scope

### IN Scope
- W1: `_extract_clean_body()` 인라인 HTML 필터링 강화 (`chain_publisher_core.py:112`)
- W2: 프롬프트 HTML 전면 금지 규칙 추가 (`config/prompts.yaml:248-254`)
- W4: `_verify_before_deploy()` HTML 태그 검증 추가 (`chain_publisher_core.py:166-174`)
- W5: rotcha-blog CSS 방어 broadened + 3개 사이트 전파
- W3: card_injector HTML 카드 → Hugo shortcode 전환 (위험도 중간, 마지막)

### OUT of Scope (LOCKED)
- `_NON_INTENDED_CHAINS={19,27}` 가드 — 절대 건드리지 않음
- FM 보존 로직 (`_extract_clean_body()` closer 처리) — 변경 금지
- 기존 발행된 1,086건 글 — 이미 제거됨, 건드리지 않음
- Phase 1-10의 기존 기능 — 회귀 유발 수정 금지

## Existing Diagnosis

| Wave | 파일 | 수정 내용 | 위험도 | 공수 |
|------|------|-----------|--------|------|
| W1 | `chain_publisher_core.py:112` | `re.match()` → `re.search()` + 태그 목록 확대 | 낮음 | 0.5일 |
| W2 | `config/prompts.yaml:248-254` | HTML 태그 전면 금지 규칙 추가 | 낮음 | 0.5일 |
| W4 | `chain_publisher_core.py:166-174` | HTML 태그 검증 로직 추가 | 낮음 | 0.5일 |
| W5 | `rotcha-blog/assets/css/extended/custom.css` + 3개 사이트 | `adsbygoogle` CSS 방어 broadened | 낮음 | 0.5일 |
| W3 | `chain_card_injector.py` | HTML 카드 → Hugo shortcode 전환 | 중간 | 1일 |

## Constraints
- pytest 50/50 통과 필수 (각 Wave별)
- 각 Wave 머지 전 대표 승인
- pytest 깨지면 즉시 롤백
- W3는 별도 브랜치
- STATE.md는 머지 시점에만 갱신

## Key Files
- `chain_publisher_core.py` — _extract_clean_body(), _verify_before_deploy()
- `chain_drafter.py` — _strip_prompt_leak()
- `chain_card_injector.py` — build_card_html(), build_official_card_html()
- `config/prompts.yaml` — draft_system 프롬프트
- `docs/diagnostics/2026-07-html-leak-ad-overlap.md` — 진단 리포트
- `rotcha-blog/assets/css/extended/custom.css` — 광고 CSS
- `rotcha-blog/layouts/partials/adsense/*.html` — 광고 partials
