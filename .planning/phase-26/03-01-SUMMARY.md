# Phase 26 Plan 03-01: BaseImageProvider/캐시 매니저 신설 Summary

**Plan:** 26-03-01
**Type:** execute (wave 3)
**Status:** Complete
**Duration:** ~25 min
**Completed:** 2026-07-31

## One-liner

이미지 파이프라인 공통 기반 신설: `image/base_provider.py` 의 추상 `BaseImageProvider` (fetch/validate 인터페이스 + 공유 캐시) 와 `image/cache_manager.py` 의 `CacheManager` (LRU + TTL 인메모리 캐시, 스레드 세이프, 공유 싱글톤) — 27개 단위 테스트로 고정. 기존 `search_providers.py`/`prompt_builder.py` 는 무변경 (03-02 에서 적응).

## What Was Done

1. **Created `image/base_provider.py`** (64 lines) — 이미지 제공자 공통 인터페이스:
   - `BaseImageProvider(ABC)` — `fetch(keyword, timeout=30.0) -> Optional[dict]` + `validate(result) -> bool` 두 추상 메서드. 둘 다 구현해야 인스턴스화 가능
   - T-26-21 완화: `fetch` 에 `timeout` 파라미터(기본 30초) — 행잉 연결 방지
   - `shared_cache = CacheManager.get_shared()` 클래스 속성 — 서브클래스(제공자 인스턴스들)가 같은 캐시를 공유 (key_links 계약: `from .cache_manager import CacheManager`)
   - 패키지 내부 상대 import (`from .cache_manager import ...`) 스타일 — `image/` 는 패키지 (`__init__.py` 존재)
2. **Created `image/cache_manager.py`** (137 lines) — LRU + TTL 인메모리 캐시:
   - `CacheManager(maxsize=128, ttl=3600)` — `OrderedDict[key -> (ts, value, expires_at)]`, `time.monotonic()` 기반 (시계 변경 면역)
   - `get(key, default=None)` — 히트 시 `move_to_end` 로 LRU 갱신, 만료 항목 지연 제거
   - `set(key, value, ttl=None)` — 개별 ttl 오버라이드 지원, maxsize 초과 시 LRU 퇴출
   - `clear()` — 캐시 전체 즉시 비우기 (T-26-20), `prune()` — 만료 항목 일괄 제거
   - `get_shared()` 모듈 레벨 공유 싱글톤 (여러 제공자 인스턴스 간 공유), `threading.Lock` 으로 스레드 세이프
   - 키 타입 검증: str 이 아니면 `TypeError` (int/None 키로 인한 충돌 방지)
   - T-26-20 완화: 값은 비민감 데이터(이미지 메타데이터/경로)만 저장 원칙 + `clear()` 로 즉시 제거 가능
3. **Created `test_base_provider.py`** (8 tests) — 추상 강제(미구현/부분구현 → TypeError), 두 메서드 구현 시 인스턴스화 + 동작, abstractmethod 플래그, timeout 파라미터 존재, shared_cache 싱글톤 공유
4. **Created `test_cache_manager.py`** (19 tests) — hit/miss/default, overwrite, len/keys, **LRU 퇴출 순서**(maxsize=3 + 4번째 set → 최고령 퇴출), **get 으로 인한 LRU 갱신**(접근 항목은 MRU 유지), 재set 갱신, maxsize 최소 1 방어, **TTL 만료**, **개별 ttl 오버라이드**, prune(만료만 제거), clear, 공유 싱글톤 동일성/독립성, 키 타입 검증, 만료 항목 미노출
5. **`image/search_providers.py` / `image/prompt_builder.py` 무변경** — 03-02(다음 웨이브)에서 베이스 클래스/캐시로 적응. 행동 보존 최우선 규칙에 따라 이번 플랜에서는 접촉하지 않음 (허용된 skip — 아래 Deviations 참조)

## Files Changed

| File | Action |
|------|--------|
| `image/base_provider.py` | created (64 lines) |
| `image/cache_manager.py` | created (137 lines) |
| `test_base_provider.py` | created (95 lines, 8 tests) |
| `test_cache_manager.py` | created (188 lines, 19 tests) |

## Verification Results

| Command | Result |
|---------|--------|
| `python -c "from image.base_provider import BaseImageProvider; print('BaseImageProvider imported')"` | `BaseImageProvider imported` (Plan Task 1 verify) |
| `python -c "from image.cache_manager import CacheManager; cm = CacheManager(); print('CacheManager created')"` | `CacheManager created` (Plan Task 2 verify) |
| `python -m pytest test_base_provider.py -q` | **8 passed** |
| `python -m pytest test_cache_manager.py -q` | **19 passed** |
| `python -m pytest test_base_provider.py test_cache_manager.py -v` | **27 passed** in 0.71s (Plan Task 3 verify) |
| `python -m pytest -q` (full suite) | **665 passed** in 21.27s — 산출: 638 (02-03 종료 시점) + 27 (8 + 19 신규) = 665. 기존 테스트 회귀 0건 |
| `git show --stat HEAD` | 4 files, +484/-0 — 의도치 않은 삭제 없음 |
| `git diff --cached` (commit 전) | 내 신규 4개 파일만 스테이징 — Wave 1 WIP(chain_card_injector/image/prompt_builder 등) 미포함 확인 |

## Deviations from Plan

1. **[Rule 1 - Bug 자동수정] 개별 ttl 미적용** — 최초 구현에서 `set(key, val, ttl=X)` 의 개별 ttl 을 저장하지 않아 `get()`/`prune()` 이 인스턴스 기본 ttl 만으로 만료 판정 (개별 ttl 테스트 2건 실패). [PRODUCTION CODE] 수정: 저장 형태를 `(ts, value, expires_at)` 으로 확장해 항목별 절대 만료 시각을 기록·판정. 수정 후 27/27 통과.
2. **[테스트 작성 과정에서 발견한 설계 결정] search_providers.py 무접촉** — orchestrator 지시("Adding harmless imports there is allowed only if nothing breaks; otherwise skip and note")에 따라 skip. `search_providers.py` 는 현재 함수 기반 + 파일 캐시(24h TTL)이고, 03-02 가 `BaseImageProvider`/`CacheManager` 로 적응하는 계획이므로 이번 플랜에서 추가 import 는 무의미한 사전 변경. 행동 무변경.
3. **`<output>` 경로 무시** — `.planning/phases/26-08/` 는 stale. repo 컨벤션 `.planning/phase-26/03-01-SUMMARY.md` 에 작성.
4. **계획 min_lines 충족 확인** — base_provider.py 64 ≥ 20, cache_manager.py 137 ≥ 25 (must_haves 기준 초과 충족).

## Known Stubs

None — `BaseImageProvider`/`CacheManager` 는 완전히 동작하는 신규 모듈. 구체 제공자 적응은 03-02 계획의 범위.

## Threat Flags

None — 신규 2개 모듈은 인메모리/순수 클래스 (네트워크 요청은 수행하지 않음, 파일 접근 없음). T-26-20 (캐시 민감 정보 방지: 비민감 값 원칙 + clear()) 과 T-26-21 (fetch timeout 파라미터) 을 모두 구현·테스트했다.

## Self-Check: PASSED

- `[ -f image/base_provider.py ]` → FOUND / `[ -f image/cache_manager.py ]` → FOUND / `[ -f test_base_provider.py ]` → FOUND / `[ -f test_cache_manager.py ]` → FOUND
- `git log | grep 6f0b7a8` → FOUND (feat 커밋 존재)
- `python -m pytest -q` → 665 passed (실행 명령 출력으로 검증)

## Residual Risk

- `pyproject.toml` packages include 에 `image*` 가 있어 이번 신규 이미지 모듈은 향후 `pip install .` 에 포함되나, `card_generator.py`/`html_renderer.py`/`link_finder.py` 등 루트 신규 모듈은 미포함 (01-01/02-02/02-03 SUMMARY 와 동일한 잔존 리스크 — 향후 include 목록 정리 필요).
- `CacheManager` 는 인메모리 캐시라 프로세스 재시작 시 소멸. 기존 `search_providers.py` 의 파일 캐시(24h)와 이중 구조가 03-02 적응까지 공존 — 동작 충돌 없음 (별도 네임스페이스).
- 싱글톤 `get_shared()` 는 첫 호출 파라미터가 이후 호출에 고정됨 (maxsize/ttl 재설정 불가). 재설정이 필요하면 `clear()` 후 새 인스턴스 사용 — 문서화됨.
