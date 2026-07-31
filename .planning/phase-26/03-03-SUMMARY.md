# Phase 26 Plan 03-03: 설정 JSON-Schema 검증 + 로드 훅 Summary

**Plan:** 26-03-03
**Type:** execute (wave 4)
**Status:** Complete
**Duration:** ~30 min
**Completed:** 2026-08-01

## One-liner

`config/schema.yaml` (JSON-Schema draft-07) 신설 + `chain_publisher_core.load_and_validate_config`/`validate_config`/`ConfigValidationError` 추가 — 19개 단위 테스트 고정. **관대(permissive) 스키마** — 실제 `prompts.yaml`(18 keys)과 `chain_config.yaml`(15 keys)이 그대로 통과. 기존 `mc_paths.load_config` 동작/호출자 무변경.

## What Was Done

1. **`config/schema.yaml`** (88 lines, must_haves min_lines 30 초과) — JSON-Schema draft-07 구조:
   - `prompts` 서브스키마: `derive_*`/`draft_*` string 필드 + `keyword_categories` (카테고리명 → `keyword_category` 정의), required `[derive_system, draft_system, draft_user, keyword_categories]`
   - `chain_config` 서브스키마: `keyword_mapping` (카테고리명 → enum `[depth, lateral, swallow]`), required `[keyword_mapping]`
   - `definitions`: `char_range` (min/max/target 정수), `keyword_category` (patterns 배열 + cta_phrases + char_count 3개 사이트 + step1~3_sections + 선택 priority)
   - 관대함 원칙 (PLAN.md 리스크: "JSON-Schema가 너무 엄격해서 기존 유효한 YAML을 거부"): `additionalProperties: true` 전역 + required 는 실존 필드만. T-26-25 (DoS): `maxProperties` 제한 (실현 값 대비 여유)
2. **`chain_publisher_core.py`** — 3개 API 추가 (기존 코드 무변경, 파일 끝에 추가):
   - `ConfigValidationError(ValueError)` — 호출자 try/except ValueError 호환
   - `validate_config(config, config_name) -> list[str]` — config dict 를 해당 서브스키마로 검증, 오류 메시지 리스트 반환 (경로: 메시지 형태)
   - `load_and_validate_config(config_name="chain_config.yaml") -> dict` — `mc_paths.load_config` 로드 후 검증, 실패 시 **파일명 + 오류 목록** 포함 ConfigValidationError 발생
   - **jsonschema 4.26 (referencing) 호환 수정**: 서브스키마만 Draft7Validator 에 넘기면 `#/definitions/*` $ref 가 해석되지 않음(PointerToNowhere) → 검증 문서에 `definitions` 를 병합해 해석
3. **`test_config_validation.py`** (19 tests) — 스키마 파일 자체 로드/min_lines, 실제 설정 2종 통과 + etc 빈 patterns 허용 + 미래 키 확장 허용(관대함), 무효 8종 거부(타입/누락/구조/enum), `load_and_validate_config` 성공/실패(파일명 포함) + ValueError 계열. 실제 config 파일 수정 없음 (dict 직접 검증 + monkeypatch)

## Files Changed

| File | Action |
|------|--------|
| `config/schema.yaml` | created (88 lines) |
| `chain_publisher_core.py` | modified (+60 — 파일 끝 3개 API 추가, 기존 코드 무변경) |
| `test_config_validation.py` | created (197 lines, 19 tests) |

## Verification Results

| Command | Result |
|---------|--------|
| `python -c "import yaml, jsonschema; print('Schema validation libraries available')"` | libraries available (Plan Task 1 verify — yaml/jsonschema 4.26.0 설치 확인) |
| `python -c "from chain_publisher_core import load_and_validate_config; print('export ok')"` | `export ok` (Plan Task 2 verify — `load_config` 는 없고 `load_and_validate_config` 가 계약 API) |
| `python -c "from chain_publisher_core import load_and_validate_config; load_and_validate_config('chain_config.yaml'); load_and_validate_config('prompts.yaml')"` | `chain_config validated OK — keys: 15` / `prompts.yaml validated OK — keys: 18` (실제 설정 통과) |
| `python -m pytest test_config_validation.py -v` | **19 passed** in 0.43s (Plan Task 3 verify) |
| `python -m pytest -q` (full suite) | **712 passed** in 21.50s — 산출: 693 (03-02 종료 시점) + 19 신규 = 712. 기존 테스트 회귀 0건 |
| `git show --stat HEAD` | 3 files, +344/-1 — 삭제는 HEAD 마지막 줄 newline 처리로 인한 1줄(내용 삭제 없음, `--diff-filter=D` 0건) |

## Deviations from Plan

1. **[계획 파일명 조정] `keyword_mapping.yaml` 별도 파일은 존재하지 않음** — PLAN.md files_modified 에 `config/keyword_mapping.yaml` 이 있었으나 repo 현실은 `config/chain_config.yaml` 내부 `keyword_mapping:` 섹션 (orchestrator 사전 확인 사항과 일치). 스키마는 해당 섹션을 검증. prompts.yaml 도 무수정 (검증 대상일 뿐).
2. **[Rule 1 - Bug 자동수정] jsonschema 4.26 referencing $ref 해석 실패** — `Draft7Validator(schema["prompts"])` 로만 검증하면 `#/definitions/keyword_category` 가 `PointerToNowhere` 오류로 실패 (referencing 라이브러리가 서브스키마를 독립 리소스로 취급). [PRODUCTION CODE] 수정: `doc = dict(sub); doc["definitions"] = schema["definitions"]` 병합 후 검증. 수정 후 실설정 통과 + 19/19.
3. **`<output>` 경로 무시** — `.planning/phases/26-10/` 는 stale. repo 컨벤션 `.planning/phase-26/03-03-SUMMARY.md` 에 작성.
4. **Wave 1 WIP 혼재 파일 커밋 시 hunk 분리** — `chain_publisher_core.py` 에 Wave 1 미커밋 변경(상수 통합 import) 공존. `git update-index --cacheinfo` 로 HEAD + 내 추가 블록만 스테이징 (커밋 후 WIP 는 작업 트리에 잔존, `git diff`로 확인).

## Known Stubs

None — 스키마/검증 훅 완전 동작. 다만 `validate_config` 는 아직 어떤 호출 경로에도 자동 연결되지 않음 (발행 파이프라인은 계속 `mc_paths.load_config` 를 직접 사용 — 기존 동작 보존 원칙). 자동 연결은 향후 플랜 범위.

## Threat Flags

None — T-26-24 (스키마는 구조/타입만 기술, 민감 값 없음), T-26-25 (maxProperties 제한 구현). 신규 네트워크/파일 접근/인증 경로 없음 (config/schema.yaml 읽기만 추가).

## Self-Check: PASSED

- `[ -f config/schema.yaml ]` → FOUND / `[ -f test_config_validation.py ]` → FOUND
- `git log | grep b847dd6` → FOUND (feat 커밋 존재)
- `python -m pytest -q` → 712 passed (실행 명령 출력으로 검증)

## Residual Risk

- 검증 훅이 발행 경로에 자동 연결되어 있지 않음 — 잘못된 config 가 변경되더라도 publish 시점에는 잡히지 않음 (명시적 호출 필요). 의도된 것 (기존 동작 보존), 향후 자동 연결 검토.
- `maxProperties` 값(100/200)은 현실 값 기준 여유 — 향후 카테고리 100개 초과 시 스키마 갱신 필요.
- Wave 1 WIP(`chain_publisher_core.py` 상수 통합, mc/leak_defense.py 등)는 여전히 미커밋 — 오케스트레이터가 Wave 1 통합 커밋에서 처리 예정. 03-04 가 같은 파일을 다시 수정하므로 커밋 시 hunk 분리 재적용 필요.
