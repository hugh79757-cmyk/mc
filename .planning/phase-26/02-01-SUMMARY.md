# Phase 26 Plan 02-01: LinkFinder 클래스 신설 Summary

**Plan:** 26-02-01
**Type:** execute (wave 2)
**Status:** Complete
**Duration:** ~25 min
**Completed:** 2026-07-31

## One-liner

신규 `link_finder.py` 모듈에 `LinkFinder` 클래스 (HTML 앵커 / 마크다운 링크 / bare URL 추출, `url_utils.normalize_url` 기반 정규화 + T-26-10/T-26-11 입력 가드) 를 신설하고 47개 단위 테스트로 고정. `chain_card_injector.py` 에는 import 만 추가 (02-03 리팩터링용 예고).

## What Was Done

1. **Created `link_finder.py`** (repo root, 248 lines) — 링크 추출 단일 진실 공급원:
   - `LinkFinder.find_links(text) -> list[dict]` — 각 dict: `url` (정규화), `raw_url` (원본), `text` (앵커 텍스트 또는 주변 스니펫), `position` (char offset), `end`, `kind` ("html" | "markdown" | "bare")
   - HTML 앵커 `<a href>` (따옴표/무따옴표, 속성 오탐 `data-href` 방지, 엔티티 언이스케이프, 프로토콜 상대 `//host` → https 해석, 상대 경로 제외), 마크다운 `[text](url)`, bare URL 순으로 추출하고 더 구체적 형식에 포함된 URL이 bare 로 중복되지 않도록 span 제외
   - bare URL 은 `constants.URL_PATTERN` 의 **패턴 문자열**을 재사용하되 `IGNORECASE` 로 컴파일 (대문자 `HTTP://` 스킴 지원) — 패턴 문자는 constants 에서 단일 소스 유지
   - `url_utils.normalize_url` 재사용: 트래킹 파라미터(utm_*/fbclid 등) 제거, fragment 제거, scheme/host 소문자화
   - 코드 펜스(``` / ~~~) 내부 URL은 코드로 간주해 제외, HTML 태그 내 `<img src>` 등은 링크로 취급 안 함
   - `dedupe=True` 기본 (정규화 URL 기준 첫 발생만), `max_input_chars` 기본 1MB
2. **Created `test_link_finder.py`** (47 tests) — bare/markdown/html URL 형식, 쿼리·트래킹 파라미터, 엣지 (빈 텍스트/링크 없음/말라폼 URL/unicode·punycode 도메인/코드 펜스), 입력 가드 (TypeError/ValueError), dedup 동작. **Coverage: 98%** (92 stmts 중 2 miss — `normalize_url` 이 빈 문자열을 반환하지 않는 구조상 도달 불가한 방어 가드).
3. **Updated `chain_card_injector.py`** — `from link_finder import LinkFinder` import 만 추가 (파일의 Wave 1 미커밋 작업과 충돌하지 않도록 index-only 패치로 스테이징 — 아래 Deviations 참조).

## Files Changed

| File | Action |
|------|--------|
| `link_finder.py` | created (248 lines) |
| `test_link_finder.py` | created (263 lines, 47 tests) |
| `chain_card_injector.py` | modified (import 3 lines only — Wave 1 미커밋 작업은 그대로 잔존) |

## Verification Results

| Command | Result |
|---------|--------|
| `python -c "from link_finder import LinkFinder; lf=LinkFinder(); links=lf.find_links('Test http://example.com'); assert len(links)==1; assert links[0]['url']=='http://example.com'"` | OK (`LinkFinder works correctly`) — Plan Task 1 verify 명령 |
| `python -m pytest test_link_finder.py -q` | **47 passed** (0.05s) |
| `python -m pytest test_link_finder.py --cov=link_finder --cov-report=term-missing -q` | 47 passed, **coverage 98%** (miss: 183, 186 — 방어 가드) |
| `python -m pytest -q` (full suite) | **509 passed** in 20.75s — 산출: 462 (기준선, orchestrator 실측) + 47 (신규 test_link_finder.py) = 509. 기존 테스트 회귀 0건 |
| `git show --stat HEAD` | 3 files, +514/-0 — 의도치 않은 삭제 없음 |
| `git diff --cached` (commit 전) | `chain_card_injector.py` 3 insertions — 내 import 3줄만 스테이징됨 확인 |

## Deviations from Plan

1. **[Isolation 조치] `chain_card_injector.py` 커밋 방식 변경** — 이 파일은 Wave 1(01-04) 에이전트의 미커밋 작업이 포함된 상태였다. `git add chain_card_injector.py` 로 통째 스테이징하면 타 에이전트 WIP가 내 커밋에 섞이므로, 내 import 3줄만 index-only 패치(`git apply --cached`)로 스테이징해 커밋했다. Wave 1 작업은 작업 트리에 그대로 잔존 (commit 후 `git status` 로 확인).
2. **[Rule 1 - Bug 자동수정] 대문자 스킴 URL 미추출** — `constants.URL_PATTERN` 이 대소문자 구분(`https?://`)이라 `HTTP://Example.COM` 이 추출되지 않는 버그를 발견. `URL_PATTERN.pattern` 을 재사용하되 `IGNORECASE` 로 컴파일하고 `_resolve_url` 의 스킴 판별도 대소문자 무시로 수정. constants.py 자체는 Wave 1 소유 파일이라 수정하지 않음 (패턴 문자열 소스는 여전히 constants 단일).
3. **[Rule 2 - 추가 기능] 코드 펜스/HTML 태그 제외** — 계획 테스트 목록에 없었으나, 카드 주입 하류(downstream)에서 ` ```json ` 코드 블록 내 URL이 노이즈로 추출되는 것을 방지하기 위해 펜스(```/~~~) 내부 URL과 `<img src>` 등 HTML 태그 속성 URL을 제외 처리. 관련 테스트 4건 포함.
4. **[제한 문서화] 마크다운 URL 내 균형 괄호 미지원** — `[t](https://en.wikipedia.org/wiki/Foo_(bar))` 는 첫 `)` 에서 잘림. T-26-11 (ReDoS) 안전 우선 트레이드오프로 균형 괄호 매칭을 미지원하며 모듈 docstring 에 문서화.
5. **`<output>` 경로 무시** — 계획의 `.planning/phases/26-06/02-01-SUMMARY.md` 는 stale 경로. orchestrator 지시대로 repo 컨벤션 `.planning/phase-26/02-01-SUMMARY.md` 에 작성.

## Known Stubs

None — `LinkFinder` 는 완전히 동작하는 신규 모듈이며 기존 코드의 스텁 대체가 아니다. `chain_card_injector.py` 의 import 는 02-03 리팩터링 전까지 미사용(`# noqa: F401`) 예고 import.

## Threat Flags

None — `link_finder.py` 는 순수 함수 모듈 (네트워크/파일 접근 없음). 계획 threat register 의 T-26-10 (입력 크기 상한, ValueError) 와 T-26-11 (단순 정규식 + 입력 상한) 을 모두 구현·테스트했다.

## Self-Check: PASSED

- `[ -f link_finder.py ]` → FOUND / `[ -f test_link_finder.py ]` → FOUND / `[ -f .planning/phase-26/02-01-SUMMARY.md ]` → FOUND
- `git log | grep 1d8ea63` → FOUND (refactor 커밋 존재)
- `python -m pytest -q` → 509 passed (실행 명령 출력으로 검증)

## Residual Risk

- `pyproject.toml` 의 `[tool.setuptools.packages.find] include = ["cli*", "chain_*", "image*", "shared*"]` 에 `link_finder.py` 가 포함되지 않음 — 01-01-SUMMARY 에서 frontmatter_utils.py 에 대해 지적된 동일한 잠재 리스크 (미래 `pip install .` 시 누락). 현재 repo 는 작업 트리에서 직접 실행하므로 실영향 없음. 향후 계획에서 include 목록 정리 필요.
- `chain_card_injector.py` 의 import 위치가 HEAD(내 커밋)와 작업 트리(Wave 1 소유 버전)에서 서로 다름 (커밋본: `mc.cta` import 뒤, 작업 트리: `constants` import 뒤). Wave 1 커밋 시 diff 노이즈가 생길 수 있으나 데이터 손실/충돌 없음.
- 방어 가드 2줄 (`if not raw_url`, `if not url`) 이 현재 입력 형식상 도달 불가 (URL_PATTERN 이 최소 7자 보장, normalize_url 이 빈 문자열 미반환) — 테스트 불가 코드로 coverage 98% 수준에서 유지 중. 제거는 02-03 리팩터링 시 판단.
- 마크다운 균형 괄호 URL (위키피디아 스타일) 잘림 — 한글 카드 콘텐츠에서는 실측 빈도 낮음. 필요 시 별도 계획으로 대응.
