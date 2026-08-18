# Phase 37 Plan 01: DB 분리 + shared vendoring + R2 매핑 Summary

**One-liner:** DB 경로 분리 + 5000 shared 모듈 vendoring + R2 도메인 매핑 3건으로 복제 레포 필수 분리 지점 해소

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | DB 분리 — db_path 상대 경로 | 55f1372 | config/chain_config.yaml |
| 2 | shared vendoring | 24c2c64 | shared/__init__.py, shared/ai_writer.py, shared/env_loader.py, config/models.yaml |
| 3 | R2 매핑 키 추가 | 952a056 | image/r2_uploader.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] R2 키 매칭 순서 수정**
- **Found during:** Task 3
- **Issue:** `get_r2_config()`가 `if key in site_path`로 부분 문자열 매칭을 사용하는데, `"informationhot"`이 `"5.informationhot-hugo"`의 부분 문자열이라 5.informationhot이 아닌 informationhot으로 매칭됨
- **Fix:** 키 순서를 `"5.informationhot"` > `"informationhot"`으로 변경 (긴 키 우선 매칭 보장)
- **Files modified:** image/r2_uploader.py
- **Commit:** 952a056

**2. [Rule 1 - Bug] R2 키 포맷 수정 (underscore → dot)**
- **Found during:** Task 3
- **Issue:** 초기에 `"5_informationhot"` 키를 사용했으나 site_path가 `"5.informationhot-hugo"`이므로 부분 문자열 매칭 불가 (`_` ≠ `.`)
- **Fix:** `"5_informationhot"` → `"5.informationhot"`으로 키 포맷 변경
- **Files modified:** image/r2_uploader.py
- **Commit:** 952a056

### Known Limitations

**1. mc_paths.py PATH_5000 제거 보류**
- **이유:** 원본 mc 레포에서 `shared.publishers.hugo_writer` import가 5000 shared에서 오므로, PATH_5000을 제거하면 기존 기능 깨짐
- **권장:** 복제 레포에서만 `ensure_5000_on_path()` 호출 제거 또는 sharedublishers 모듈도 vendoring

## Verification

| Check | Result | Evidence |
|-------|--------|----------|
| db_path 상대 경로 확인 | [검증됨] | `python3 -c "from mc_paths import load_config; print(load_config()['db_path'])"` → `data/mc_chains.db` |
| shared import 정상 | [검증됨] | `from shared.ai_writer import generate` → OK |
| shared import 정상 | [검증됨] | `from shared.env_loader import load_env` → OK |
| models.yaml 로드 | [검증됨] | `yaml.safe_load(open('config/models.yaml'))` → 17 tiers |
| R2 매핑 매칭 정상 | [검증됨] | `get_r2_config('5.informationhot-hugo')` → `images/5_informationhot` |
| R2 매핑 매칭 정상 | [검증됨] | `get_r2_config('informationhot-hugo')` → `images/informationhot` |
| 기존 테스트 회귀 | [검증됨] | 917 passed, 5 failed (모두 사전 존재 실패) |

**테스트 결과:** 917 passed, 5 failed
- 5건 실패 모두我的 변경 이전부터 존재 (git stash 상태에서 동일 확인)
- `test_ai_writer_bug001.py` 3건: models.yaml tier 매칭 경고 → 사전 존재
- `test_chain_drafter.py` 2건: sqlite3 column 오류 → 사전 존재

## Known Stubs

None — plan 달성에 필요한 stub 없음.

## Threat Flags

None — 신규 네트워크 엔드포인트, 인증 경로, 파일 접근 패턴 없음.

## Self-Check

- [x] chain_config.yaml db_path 변경됨: `data/mc_chains.db`
- [x] shared/__init__.py 존재: ✅
- [x] shared/ai_writer.py 존재: ✅ (764 lines)
- [x] shared/env_loader.py 존재: ✅ (13 lines)
- [x] config/models.yaml 존재: ✅ (17 tiers)
- [x] image/r2_uploader.py HUGO_R2_DOMAINS에 informationhot 존재: ✅
- [x] image/r2_uploader.py HUGO_R2_DOMAINS에 5.informationhot 존재: ✅
- [x] 커밋 55f1372 존재: ✅
- [x] 커밋 24c2c64 존재: ✅
- [x] 커밋 952a056 존재: ✅

## Self-Check: PASSED
