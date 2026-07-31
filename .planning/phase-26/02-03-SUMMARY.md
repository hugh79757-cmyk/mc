# Phase 26 Plan 02-03: CardInjector 퍼사드 리팩터링 Summary

**Plan:** 26-02-03
**Type:** execute (wave 3)
**Status:** Complete
**Duration:** ~40 min
**Completed:** 2026-07-31

## One-liner

`CardInjector` 의 카드 HTML 생산(3개 메서드)을 `CardGenerator` + `HtmlRenderer` 로 위임하는 퍼사드 리팩터링. 공개 API 시그니처와 출력을 리팩터링 전과 **바이트 단위 동일**하게 유지했고, 이를 59개 행동 동등성 테스트(리팩터링 전 캡처 GOLDEN 35건)로 고정했다.

## What Was Done

1. **`chain_card_injector.py` 퍼사드 위임** (3개 메서드 + 헬퍼 2개, 시그니처 전부 보존):
   - `build_card_html(title, url, cta)` → `self._generator().generate_next_card_spec(...)` + `self._renderer().render(spec)` — `{{< chain-card ... >}}` shortcode 출력 동일
   - `build_official_card_html(link)` → `generate_official_card_spec` + render — falsy link 는 기존과 동일하게 `""` 조기 반환, `{{< chain-official-card ... >}}` 출력 동일
   - `build_external_link_card(links, seed_keyword)` → `generate_external_card_spec` + render — primary(`#DC2626`)/secondary(`#2563eb`, 2개 슬라이싱)/fallback(`#fafafa`, seed_keyword 기본 라벨) 복합 HTML 동일, primary url 누락 시 KeyError 전파 동일
   - `_generator()`/`_renderer()` 지연(lazy) 생성 헬퍼 — `CardInjector.__new__(CardInjector)` 패턴(기존 `test_w3_cards_image.py` 관례)의 `__init__` 미경유 인스턴스에서도 동작. `__init__` 시그니처 자체는 변경 없음
   - `inject_bottom_card` / `inject_mid_card` / `inject_cards_into_draft` / `inject_into_post` / `fix_unclosed_fences` / `get_cta` / `find_external_links` / `find_official_link` / `_search_via_api` / `_naver_fallback` / `_domain` / `_score_official` / `_keyword_tokens` / `_extract_domain` / `_decode_idn` — **무변경** (내부에서 위임된 메서드를 호출하는 흐름만 유지)
   - `DualCTAInjector` — **완전히 미접촉** (시그니처 + 행동 스냅샷으로 고정)
2. **Created `test_card_integration.py`** (59 tests):
   - **GOLDEN 바이트 동일성**: 리팩터링 직전 캡처한 실제 출력 35건 — build_card_html 5, build_official_card_html 5, build_external_link_card 11 (KeyError 1건 포함), inject_bottom_card 4, inject_mid_card 3, inject_cards_into_draft 7 (D9 게이트·미닫힌 펜스·frontmatter 유무·D2 fallback 포함)
   - **API 서피스 스냅샷**: `CardInjector` 15개 + `DualCTAInjector` 4개 메서드 시그니처를 리팩터링 전 캡처값과 `inspect.signature` 로 비교
   - **위임 스파이**: SpyGenerator/SpyRenderer 로 3개 메서드가 실제로 컴포넌트를 호출하는지 확인
   - **지연 초기화**: `__new__` 만으로 생성된 인스턴스에서 위임 동작 + 컴포넌트 지연 생성 검증
   - **파이프라인 동등성**: `CardInjector` 경유 출력 == `CardGenerator`+`HtmlRenderer` 직접 파이프라인 출력
   - **fix_unclosed_fences**: 정적 메서드 유지 + 기존 의미론(내용 있으면 열기 직후 닫기, 내용 없으면 제거) 보존
   - **DualCTAInjector 행동**: build_dual_cta_html 출력 구조(v2: info CTA only) 보존

## Files Changed

| File | Action |
|------|--------|
| `chain_card_injector.py` | modified (3개 메서드 위임 + 지연 헬퍼 2개 — index-only 패치로 내 hunks 만 스테이징, Wave 1 미커밋 작업 미포함) |
| `test_card_integration.py` | created (634 lines, 59 tests) |

## Verification Results

| Command | Result |
|---------|--------|
| 리팩터링 직후 GOLDEN 대조 (커밋 전 스크립트) | `ALL 35 OUTPUTS BYTE-IDENTICAL` — 단위 21 + 파이프라인 14 전건 |
| `python -m pytest test_card_integration.py -q` | **59 passed** (0.09s) — Plan Task 2 verify |
| `python -m pytest test_card_integration.py test_html_renderer.py test_card_generator.py test_w3_cards_image.py -q` | **177 passed** (0.35s) — **커밋 대상(index) 버전으로 검증**: `git checkout-index` 로 index 파일을 작업 트리에 복원해 실행 후 원복 |
| `python -m pytest -q` (full suite) | **638 passed** in 20.01s — 산출: 579 (02-02 종료 시점) + 59 (신규 test_card_integration.py) = 638. 기존 테스트 회귀 0건 |
| `git diff --cached` (commit 전) | chain_card_injector.py 106줄 변경 — 내 위임/헬퍼 hunks 만 포함, Wave 1 WIP(url_utils/constants import, wrapper, seed_keyword 호출) 미포함 확인 |
| `git show --stat HEAD` | 2 files, +670/-70 — 의도치 않은 삭제 없음 (삭제된 70줄은 대체된 기존 f-string 본문) |
| `git diff --check HEAD` | rc=0 — 화이트스페이스 오류 없음 |

## Deviations from Plan

1. **[Isolation 조치] `chain_card_injector.py` 커밋 방식** — 02-01/02-02 와 동일하게 index-only 패치 사용. HEAD 버전에 내 02-03 편집(4개 앵커: `__init__` 헬퍼 추가, official/card/external 메서드 대체)만 재적용한 대상 파일을 만들어 diff → `git apply --cached`. 커밋 후 Wave 1 WIP 는 작업 트리에 그대로 잔존 (`MM` 상태로 확인).
2. **[검증 강화] 커밋 대상 버전 자체로 테스트** — 작업 트리는 Wave 1 WIP 포함 버전이므로, 실제 커밋 내용(index)으로 카드 테스트 177건을 재실행해 동등성을 교차 검증했다 (`git checkout-index` → 테스트 → 백업 복원, 복원 바이트 동일성 `diff` 로 확인).
3. **[테스트 정정] `fix_unclosed_fences` 기대값** — 내 초기 작성이 잘못된 기대값(닫기 펜스를 끝에 추가한다고 가정)을 담았으나, 실제(그리고 기존 `test_w3_cards_image.py` 의미론)는 "내용이 남아 있으면 **열기 직후** 닫기 추가, 펜스만 남고 내용이 없으면 제거". [TEST CODE] 수정으로 정정 — production code 는 무변경.
4. **계획의 verify 스니펫 무효** — `chain_card_injector.ChainCardInjector()` 는 존재하지 않는 클래스명. 실존 클래스 `CardInjector` 를 기준으로 검증 (orchestrator 사전 안내와 동일).
5. **`inject_related_links`/`insert_related_links` 미존재** — 계획 must_haves exports 에 있는 이 함수들은 현재 파일에 없음 (계획이 이상화된 API 기준). 실존 진입점 `inject_cards_into_draft`/`inject_into_post` 를 보존·검증 대상으로 삼음.
6. **`<output>` 경로 무시** — `.planning/phases/26-07/` 는 stale. repo 컨벤션 `.planning/phase-26/02-03-SUMMARY.md` 에 작성.

## Known Stubs

None — 위임은 완전히 배선됨. `test_card_integration.py` 는 리팩터링 전 실제 출력을 픽스처로 임베드한 행동 동등성 테스트 (스텁 아님).

## Threat Flags

None — `chain_card_injector.py` 의 변경은 내부 위임뿐, 네트워크/파일 접근 패턴 변화 없음. T-26-14 (카드 정보 누출 방지)는 CardGenerator 의 비문자열 입력 거부(02-02)를 통해 강화됨. T-26-15 (리팩터링 취약점 무발생)는 35건 바이트 동일성 + API 스냅샷 + 전체 638 통과로 검증.

## Self-Check: PASSED

- `[ -f test_card_integration.py ]` → FOUND
- `git log | grep 43d386a` → FOUND (refactor 커밋 존재)
- `python -m pytest -q` → 638 passed (실행 명령 출력으로 검증)
- 복원 확인: `diff /tmp/card_capture/cci_worktree_backup.py chain_card_injector.py` → `RESTORE IDENTICAL`

## Residual Risk

- `chain_card_injector.py` 의 import 영역은 HEAD(커밋본)와 작업 트리(Wave 1 소유 버전)가 계속 다름. Wave 1 커밋 시 diff 노이즈 발생 가능하나 데이터 손실/충돌 없음.
- `pyproject.toml` packages include 미포함 리스크 (card_generator.py/html_renderer.py) — 02-02 SUMMARY 에 기록됨, 향후 include 목록 정리 필요.
- 위임으로 인한 간접 레이어는 호출당 2회의 dict 생성(스펙)이 추가됨. 카드 주입은 포스트당 수 회 호출이라 실측 영향 미미 (A10 성능 체크는 Wave 3 후반 계획에 존재).
