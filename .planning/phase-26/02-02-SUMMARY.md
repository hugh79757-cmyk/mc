# Phase 26 Plan 02-02: CardGenerator/HtmlRenderer 클래스 신설 Summary

**Plan:** 26-02-02
**Type:** execute (wave 3)
**Status:** Complete
**Duration:** ~35 min
**Completed:** 2026-07-31

## One-liner

카드 생성 파이프라인을 역할 기반 클래스로 분리: `card_generator.py` 의 `CardGenerator` (link dict + 포스트 메타 → 카드 스펙 dict) 와 `html_renderer.py` 의 `HtmlRenderer` (카드 스펙 → HTML, 기존 `CardInjector` 출력과 **바이트 단위 동일**) 를 신설하고 70개 단위 테스트로 고정. `chain_card_injector.py` 에는 import 만 추가 (02-03 퍼사드 리팩터링용 예고).

## What Was Done

1. **Created `card_generator.py`** (repo root, 164 lines) — 카드 스펙 생성 단일 진실 공급원:
   - `generate_next_card_spec(title, url, cta)` / `generate_internal_card_spec(...)` / `generate_chain_card_spec(card_type, ...)` → `{{< chain-card >}}` shortcode용 스펙 (type: next/internal)
   - `generate_official_card_spec(link)` → `{{< chain-official-card >}}` 스펙. link falsy(빈 dict 포함) → `{"type": "none"}` (기존 `build_official_card_html` 의 `if not link: return ""` 와 동일)
   - `generate_external_card_spec(links, seed_keyword)` → primary/secondary/fallback 복합 스펙. 분기 규칙(primary truthy → 블록, secondary 최대 2개 슬라이싱, 둘 다 없으면 fallback 기본값 `url="#"`/`label=f"네이버에서 '{seed_keyword}' 검색"`)이 기존 `build_external_link_card` 와 1:1 대응
   - `primary["url"]` 누락 시 **KeyError 전파** (기존 구현과 동일한 실패 동작 — 황금 픽스처로 캡처)
   - T-26-12 완화: 비문자열 입력(title/url/cta/label/seed_keyword) → `ValueError`. 기존 f-string 보간이 `'None'`/`'123'` 을 HTML 에 그대로 노출하던 문제를 차단
2. **Created `html_renderer.py`** (repo root, 150 lines) — 카드 HTML 렌더링 단일 진실 공급원:
   - `render(spec)` — `spec["type"]` 으로 디스패치 (none → `""`, next/internal → chain-card, official → chain-official-card, external → raw HTML 복합)
   - 템플릿은 기존 `chain_card_injector.py` 의 f-string 과 문자 단위 동일 (shortcode 구조 `{{< chain-card title="..." url="..." cta="..." >}}`, 외부 링크 카드의 `#DC2626` primary / `#2563eb` secondary / `#fafafa` fallback 블록, `"\n\n"` join)
   - T-26-13 완화: 템플릿은 모듈 로드 시 고정 상수 — 사용자 입력으로 확장 불가. secondary 는 생성기에서 2개로 슬라이싱되어 복잡도 O(1)
3. **Updated `chain_card_injector.py`** — `from card_generator import CardGenerator` / `from html_renderer import HtmlRenderer` 2줄 import 추가 (예고 import, `# noqa: F401`). 아직 사용하지 않음 — 02-03 에서 위임
4. **Created `test_card_generator.py`** (27 tests) — 스펙 구조/기본값/슬라이싱/KeyError 전파/T-26-12 비문자열 검증
5. **Created `test_html_renderer.py`** (43 tests) — **GOLDEN 픽스처 동일성 테스트**: 리팩터링 전 `CardInjector` 실제 출력 21건(카드 5, official 5, external 11 — 예외 1건 포함)을 캡처해 임베드하고, `CardGenerator`+`HtmlRenderer` 파이프라인 출력과 바이트 단위 동일함을 단언. plus 디스패치/엣지 케이스

## Files Changed

| File | Action |
|------|--------|
| `card_generator.py` | created (164 lines) |
| `html_renderer.py` | created (150 lines) |
| `test_card_generator.py` | created (191 lines, 27 tests) |
| `test_html_renderer.py` | created (358 lines, 43 tests) |
| `chain_card_injector.py` | modified (import 2 lines only — index-only 패치, Wave 1 미커밋 작업 미포함) |

## Verification Results

| Command | Result |
|---------|--------|
| `python -c "from card_generator import CardGenerator; cg = CardGenerator(); print('CardGenerator created')"` | `CardGenerator created` (Plan Task 1 verify) |
| `python -c "from html_renderer import HtmlRenderer; hr = HtmlRenderer(); print('HtmlRenderer created')"` | `HtmlRenderer created` (Plan Task 2 verify) |
| `python -c "import chain_card_injector"` | OK (import 성공) |
| `python -m pytest test_card_generator.py -q` | **27 passed** |
| `python -m pytest test_html_renderer.py -q` | **43 passed** |
| `python -m pytest test_card_generator.py test_html_renderer.py -v` | **70 passed** in 0.04s (Plan Task 3 verify) |
| `python -m pytest -q` (full suite) | **579 passed** in 21.07s — 산출: 509 (기준선) + 70 (27 + 43 신규) = 579. 기존 테스트 회귀 0건 |
| 바이트 동일성 선검증 (커밋 전 스크립트) | GOLDEN 21건 전부 `ALL BYTE-IDENTICAL + VALIDATION OK` |
| `git show --stat HEAD` | 5 files, +866/-0 — 의도치 않은 삭제 없음 |
| `git diff --cached` (commit 전) | `chain_card_injector.py` 3 insertions — 내 import 2줄 + 빈 줄만 스테이징됨 확인 |

## Deviations from Plan

1. **[Isolation 조치] `chain_card_injector.py` 커밋 방식** — 02-01 과 동일하게 index-only 패치(`git apply --cached`)로 내 import 2줄만 스테이징. HEAD 버전(커밋된 link_finder import 뒤)에 적용했고, 작업 트리의 Wave 1 WIP(url_utils/constants import, wrapper 전환, seed_keyword 호출 변경)는 커밋에 미포함. 커밋 후 `git status` 로 Wave 1 WIP 잔존 확인.
2. **[T-26-12 강화] 비문자열 입력 ValueError** — 계획 테스트 목록에 없었으나 threat register 의 T-26-12 (Information Disclosure) 완화로 추가. 기존 f-string 은 `None`/`123` 을 str() 로 강제 변환해 카드 HTML 에 노출시켰음. ValueError 는 비문자열 입력에서만 발생 — 기존 문자열 호출부(검색 API 결과, mc.cta, DB 필드)는 모두 str 이므로 동작 변경 없음. 전체 스위트 579 passed 로 회귀 0건 확인.
3. **`CardInjector.__new__(CardInjector)` 패턴 대응 설계 반영** — 기존 테스트(`test_w3_cards_image.py`)가 `__init__` 을 거치지 않고 인스턴스를 만들어 `build_external_link_card` 를 호출한다. 따라서 02-03 위임은 `__init__` 의존 없이 지연(lazy) 생성해야 함을 확인 — 02-03 설계에 반영 (이번 플랜에서는 import 만 추가).
4. **`<output>` 경로 무시** — 계획의 `.planning/phases/26-06/02-02-SUMMARY.md` 는 stale 경로. orchestrator 지시대로 repo 컨벤션 `.planning/phase-26/02-02-SUMMARY.md` 에 작성.

## Known Stubs

None — `CardGenerator`/`HtmlRenderer` 는 완전히 동작하는 신규 모듈. `chain_card_injector.py` 의 import 는 02-03 퍼사드 리팩터링 전까지 미사용 예고 import (`# noqa: F401`).

## Threat Flags

None — `card_generator.py`/`html_renderer.py` 는 순수 함수 모듈 (네트워크/파일 접근 없음). 계획 threat register 의 T-26-12 (비문자열 입력 검증 → ValueError) 와 T-26-13 (고정 템플릿 + secondary 2개 슬라이싱으로 복잡도 제한) 을 모두 구현·테스트했다.

## Self-Check: PASSED

- `[ -f card_generator.py ]` → FOUND / `[ -f html_renderer.py ]` → FOUND / `[ -f test_card_generator.py ]` → FOUND / `[ -f test_html_renderer.py ]` → FOUND
- `git log | grep a7b884f` → FOUND (refactor 커밋 존재)
- `python -m pytest -q` → 579 passed (실행 명령 출력으로 검증)

## Residual Risk

- `pyproject.toml` 의 `[tool.setuptools.packages.find] include = ["cli*", "chain_*", "image*", "shared*"]` 에 `card_generator.py`/`html_renderer.py` 가 포함되지 않음 — 01-01/02-01 SUMMARY 에서 지적된 동일한 잠재 리스크 (미래 `pip install .` 시 누락). 현재 repo 는 작업 트리에서 직접 실행하므로 실영향 없음. 향후 계획에서 include 목록 정리 필요.
- `chain_card_injector.py` 의 import 위치가 HEAD(내 커밋)와 작업 트리(Wave 1 소유 버전)에서 서로 다름 (커밋본: `link_finder` import 뒤, 작업 트리: `constants` import 뒤). Wave 1 커밋 시 diff 노이즈가 생길 수 있으나 데이터 손실/충돌 없음.
- HtmlRenderer 는 현재 구현과 동일하게 따옴표/HTML 이스케이프를 하지 않는다 (바이트 동일성 계약 우선). 제목에 `"` 가 포함되면 shortcode 속성이 깨질 수 있으나 이는 기존 동작과 동일하며, 실데이터(검색 API 제목 50자 제한)에서는 실측 빈도 낮음.
