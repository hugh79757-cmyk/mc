# Phase 26 Plan 03-02: 이미지 제공자 BaseImageProvider/CacheManager 적응 Summary

**Plan:** 26-03-02
**Type:** execute (wave 4)
**Status:** Complete
**Duration:** ~35 min
**Completed:** 2026-08-01

## One-liner

`image/search_providers.py` 에 `UnsplashProvider`/`PexelsProvider` (BaseImageProvider 상속, fetch/validate 구현, 공유 CacheManager 캐싱) 와 `image/prompt_builder.py` 에 `PromptBuilder` (기존 함수 위임 + 공유 캐시) 를 추가 — 28개 단위 테스트 고정. 기존 공개 함수 `search_body_image`/`_read_cache`/`_write_cache`(24h 파일 캐시)와 `build_contextual_prompt`/`build_full_prompt` 는 **무변경** (행동 보존, 이미지 파이프라인 테스트 의존).

## What Was Done

1. **`image/search_providers.py`** — `UnsplashProvider(BaseImageProvider)` / `PexelsProvider(BaseImageProvider)` 신설:
   - `fetch(keyword, timeout=30.0) -> Optional[dict]` — 기존 검색 로직 재사용 (`image.thumbnail` 의 provider.search + env API 키 `_UNSPLASH_KEY`/`_PEXELS_KEY`), `results[0]` 반환, 실패 시 None
   - `validate(result) -> bool` — dict + `id` + 이미지 URL 필드(`url_raw`/`url_regular`/`url`/`url_original`) 검증 (T-26-22: 무효 응답 차단)
   - 캐싱: `BaseImageProvider.shared_cache` (공유 `CacheManager` 싱글톤) — 키 `unsplash:{keyword}` / `pexels:{keyword}`, 히트 시 네트워크 재호출 없음
   - 기존 함수 기반 경로(`search_body_image`, `_read_cache`, `_write_cache`, `_to_body_path`) **무변경** — 인메모리 캐시(메타데이터)와 파일 캐시(다운로드 경로, 24h TTL)는 별도 네임스페이스로 공존
2. **`image/prompt_builder.py`** — `PromptBuilder` 클래스 신설:
   - `shared_cache = BaseImageProvider.shared_cache` — 공유 CacheManager 싱글톤
   - `build_contextual_prompt`/`build_full_prompt` 인스턴스 메서드 → 기존 모듈 함수 위임 (동일 시그니처·출력)
   - `get_style_for_blog(blog_key)` — 스타일 프롬프트를 공유 캐시(`style:{blog_key}`)로 저장·조회
   - 선택적 `provider` 주입 (BaseImageProvider 인터페이스)
   - 기존 함수 4종(`build_contextual_prompt`, `build_full_prompt`, `get_image_style_for_blog`, `get_aspect_ratio`) 및 상수 **무변경**
3. **`test_image_providers_refactored.py`** (28 tests) — 상속/추상구현 검증, fetch/validate 동작, 캐시 히트 시 API 재호출 없음, 공유 캐시 네임스페이스 분리, **래퍼 동등성** (새 클래스 fetch 결과 = 기존 경로가 소비하는 `results[0]`, `search_body_image` 시그니처/반환 튜플 유지), PromptBuilder 위임 동일성. 네트워크 미사용 — `image.thumbnail` 클래스 전부 mock

## Files Changed

| File | Action |
|------|--------|
| `image/search_providers.py` | modified (+95, 신규 클래스 2개 — 기존 함수 무변경) |
| `image/prompt_builder.py` | modified (+76, PromptBuilder 신설 — 기존 함수 무변경) |
| `test_image_providers_refactored.py` | created (235 lines, 28 tests) |

## Verification Results

| Command | Result |
|---------|--------|
| `python -c "from image.search_providers import UnsplashProvider, PexelsProvider; up = UnsplashProvider(); pp = PexelsProvider(); print('Providers instantiated')"` | `Providers instantiated` (Plan Task 1 verify) |
| `python -c "from image.prompt_builder import PromptBuilder; pb = PromptBuilder(); print('PromptBuilder created')"` | `PromptBuilder created` (Plan Task 2 verify) |
| `python -m pytest test_image_providers_refactored.py -v` | **28 passed** (Plan Task 3 verify — 계획의 `test_image_providers_reduced.py` 명은 stale, orchestrator 지시대로 refactored 명 사용) |
| `python -m pytest -q` (full suite) | **693 passed** in 21.07s — 산출: 665 (03-01 종료 시점) + 28 신규 = 693. 기존 테스트 회귀 0건 |
| `git show --stat HEAD` | 3 files, +405/-1 — 의도치 않은 삭제 없음 |
| `git show HEAD -- image/search_providers.py \| grep -c url_utils` | 0 — Wave 1 WIP(불필요 noqa import 라인) 커밋 미포함 확인 |

## Deviations from Plan

1. **[구현 조정] 클래스가 기존 로직을 감싸는 방향 채택** — 계획은 "search_body_image 를 래퍼로 바꾸거나 클래스가 기존 로직을 감싸거나" 중 선택을 허용. 기존 함수 무변경 방식을 택함 (테스트 `test_image_search.py` 가 `image.search_providers._read_cache`/`image.thumbnail.*Provider` 를 patch 해 의존하므로, 함수를 CacheManager 로 재라우팅하면 기존 테스트 8건이 깨짐 — 행동 보존 최우선).
2. **[Rule 1 - Bug 자동수정] 테스트 격리 누락으로 실네트워크 호출** — `test_providers_share_cache_namespace` 에서 UnsplashProvider 만 호출하고 `image.thumbnail.UnsplashProvider` 를 patch 하지 않아 실 API 호출 발생. [TEST CODE] 수정: 양쪽 provider 모두 mock. 수정 후 28/28 통과 (실제 네트워크 호출 재발 없음).
3. **`<output>` 경로 무시** — `.planning/phases/26-09/` 는 stale. repo 컨벤션 `.planning/phase-26/03-02-SUMMARY.md` 에 작성.
4. **Wave 1 WIP 혼재 파일 커밋 시 hunk 분리** — `image/search_providers.py`/`image/prompt_builder.py` 에 Wave 1 미커밋 `url_utils` noqa import 가 공존. `git update-index --cacheinfo` 로 WIP 라인을 제외한 blob 만 스테이징해 커밋 (커밋 후 WIP 는 작업 트리에 그대로 잔존 확인).

## Known Stubs

None — 신규 클래스/래퍼는 완전히 동작. `search_body_image`→새 클래스 경로로의 파일캐시-인메모리캐시 통합은 향후 리팩터링 범위(현재 병행 구조, 동작 충돌 없음).

## Threat Flags

None — 신규 코드는 기존 네트워크 호출 로직을 재사용하며, T-26-22 (무효 API 응답 → `validate()` 로 차단), T-26-23 (재시도/호출 증폭 없음 — 캐시 히트 시 재호출 차단) 완화. 신규 네트워크 엔드포인트·파일 접근 패턴·인증 경로 없음.

## Self-Check: PASSED

- `[ -f image/search_providers.py ]` → FOUND / `[ -f image/prompt_builder.py ]` → FOUND / `[ -f test_image_providers_refactored.py ]` → FOUND
- `git log | grep 08fcdf9` → FOUND (feat 커밋 존재)
- `python -m pytest -q` → 693 passed (실행 명령 출력으로 검증)

## Residual Risk

- 새 클래스 인메모리 캐시(기본 ttl 3600s)와 기존 파일 캐시(24h) 이중 구조 — 동작 충돌 없으나 키워드 동일 시 두 캐시가 독립 저장. 향후 단일화 시 `search_body_image` 경로의 테스트 의존을 함께 재설계해야 함.
- `image.thumbnail` 의 `UnsplashProvider`/`PexelsProvider` (search/download) 가 실네트워크 제공자로 남아 있음 — 신규 클래스는 이를 내부적으로 사용하므로 API 키 env 부재 시 빈 결과 → None (기존과 동일 동작).
- Wave 1 WIP(`url_utils` noqa import, mc/leak_defense.py 등)는 여전히 미커밋 — 오케스트레이터가 Wave 1 통합 커밋에서 처리 예정.
