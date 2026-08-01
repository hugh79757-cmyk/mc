# CONTEXT.md — Phase 33: AI 출력 JSON 메타데이터 잔류 근본 수정

## 문제 요약

Chain #378 발행 시 Step 3(techpawz)은 성공했으나 Step 1(rotcha), Step 2(issue.techpawz) 발행 실패. 원인은 AI 출력에 포함된 JSON 메타데이터(`image_type`, `chart_type`, `image_keyword` 등)가 본문에 섞여 들어와 `_extract_clean_body()`가 이를 걷어내지 못함 → `_verify_before_deploy()`가 "JSON 잔류" 검증 실패 → `_publish_hugo()`가 빈 튜플 `("", "hugo", "")` 반환 → `publish_chain()`에서 `url`이 falsy → `"Step X failed"` 출력.

Step 2·1 발행 실패와 Step 1 카드 "missing next URL" 스킵은 모두 위 원인의 연쇄 결과. 근본 하나만 고치면 함께 해소됨.

## 핵심 코드 위치 (read로 갱신한 최신 라인)

| 기능 | 파일 | 라인 |
|------|------|------|
| `_extract_clean_body()` 진입점 | `chain_publisher_core.py` | 45 |
| `is_raw_json` 줄단위 탐지 한계 | `chain_publisher_core.py` | 117 |
| 코드펜스 JSON만 스킵 (`skip_json_block`) | `chain_publisher_core.py` | 90-97 |
| `_verify_before_deploy()` 실패 시 빈 튜플 반환 | `chain_publisher_core.py` | 693 |
| `publish_chain()` URL 검사 분기 | `chain_publisher.py` | 478 |
| 카드 주입 "missing next URL" 스킵 | `chain_publisher.py` | 557 |
| `parse_ai_output()` 진입점 | `chain_models.py` | 247 |
| `_extract_meta_from_raw()` (코드펜스 JSON만 탐지) | `chain_models.py` | 206 |
| `_extract_body_from_raw()` (불완전한 JSON 제거) | `chain_models.py` | 155 |
| `core.publish_post()` 호출부 (예외 처리 없음) | `chain_publisher.py` | 474-478 |

## 현재 테스트 기준선

- `pytest --co -q`: **792 tests collected** (실측)

## 근본 원인 분석 (이미 검증됨)

1. **AI 출력에 JSON 메타데이터 포함**: AI가 마지막에 `{"image_type": "photo", "image_keyword": "...", "chart_type": null}` 같은 JSON을 평문/들여쓰기/다중라인으로 출력함. 코드펜스(```json) 없이 출력되는 경우도 있음.

2. **파싱 단계에서 분리 실패**:
   - `parse_ai_output()` → `_extract_meta_from_raw()`: 코드펜스(```json) 있는 JSON만 탐지. 평문/들여쓰기/다중라인 JSON은 누락.
   - `_extract_body_from_raw()`: 코드펜스 JSON만 정규식으로 제거. 평문 JSON은 중괄호 깊이 카운팅으로 1개만 제거 시도(500자 제한), 다중 JSON/깊은 중첩 미처리.
   - 결과: 본문(`body`)에 JSON 메타데이터가 잔류.

3. **사후 정제 단계에서 미탐지**:
   - `_extract_clean_body()`의 `is_raw_json` (line 117): `stripped.startswith("{") and ("image_type" in ...)` — **줄 단위** 탐지라 들여쓰기/다중라인 JSON 미탐지.
   - `skip_json_block` (line 90-97): ``````json` 펜스만 스킵. 펜스 없는 JSON 통과.
   - 결과: JSON 잔류가 `clean_body`에 포함됨.

4. **배포 검증에서 차단**: `_verify_before_deploy()`의 `bare_json` 정규식(`image_type` 키 탐지)이 Hugo 빌드 산출물 HTML에서 잔류 JSON 발견 → `DeployValidationError` 발생.

4. **빈 튜플 반환으로 실패 처리**: `_publish_hugo()`가 `DeployValidationError` 잡을 때 `return ("", "hugo", "")` 반환 → `publish_chain()`에서 `url`이 falsy → `"Step X failed"` 출력. 상세 에러 메시지 미출력.

## 수정 범위 (합의됨)

### 1순위·근본: `parse_ai_output()`에서 JSON 메타 블록 구조적 분리 추출
- **목표**: 코드펜스 유무·들여쓰기·다중라인 무관하게 JSON 객체를 인식해 메타데이터는 별도 파싱, 본문은 그 JSON을 제외한 나머지로 확정.
- **핵심**: "사후 제거"가 아니라 **"파싱 시점 분리"**.
- **대상**: `chain_models.py`의 `_extract_meta_from_raw()` / `_extract_body_from_raw()` 전면 재설계.

### 2차 방어: `_extract_clean_body()`의 `is_raw_json` 탐지 강화
- **목표**: 1번을 뚫고 남는 잔류를 잡는 안전망.
- **방식**: 줄 단위 → **블록 단위(중괄호 깊이 카운팅)**로 강화. `{`~`}` 깊이 카운팅으로 JSON 객체 전체 매칭 후 `image_type`/`chart_type` 키 존재 시 블록 전체 스킵.
- **대상**: `chain_publisher_core.py:117` (`is_raw_json`) 및 `skip_json_block` 로직 (line 90-97) 재작성.

### 3차 방어·관측성: 배포 검증 실패 상세 로깅
- **목적**: 실패 시 어떤 검증(1단계 index.md / 2단계 HTML), 어떤 키(`image_type` 등)가 걸렸는지 스텝별 출력.
- **대상**: 
  - `chain_publisher.py:474-478` (`core.publish_post()` 호출부) → try-except로 감싸 실패 사유(어느 검증, 어떤 키) 출력.
  - `_verify_before_deploy()` 실패 시 원본 에러 컨텍스트(어느 단계/어떤 정규식)도 로그에 남김.
- **제약**: 기존 정상 흐름의 반환 규약(`("", "hugo", "")`)은 바꾸지 않음.

## 반환 규약 영향 분석

| 함수 | 현재 반환 | 변경 후 반환 | 호출부 영향 |
|------|-----------|--------------|-------------|
| `parse_ai_output()` | `AIOutput(body, meta)` | 동일 (단 `body`에 JSON 잔류 0 보장) | `chain_drafter.py` line 311-319: `ai_output.body`, `ai_output.meta` 사용 — 영향 없음 |
| `_extract_clean_body()` | `CleanedDraft(frontmatter, body)` | 동일 (단 `body`에 JSON 잔류 0 보장) | `chain_publisher_core.py` line 630, 732: `cleaned.body` 사용 — 영향 없음 |
| `_verify_before_deploy()` | 예외 발생 / 통과 | 동일 | `_publish_hugo()` line 691 catch 블록 — 영향 없음 |
| `_publish_hugo()` | `(url, method, file)` / `("", "hugo", "")` | 동일 | `chain_publisher.py:478` `if url:` 분기 — 영향 없음 |

**결론**: 반환 타입/규약 변경 없음. 내부 구현만 교체 → 하위호환 유지.

## 테스트 계획

### 단위 테스트 (신규/확장)
| 대상 | 케이스 | 기대 |
|------|--------|------|
| `parse_ai_output()` | 코드펜스 있는 JSON (` ```json\n{...}\n``` `) | meta 추출 OK, body에 JSON 없음 |
| | 코드펜스 없는 평문 JSON (`{...}`) | meta 추출 OK, body에 JSON 없음 |
| | 들여쓰기·다중라인 JSON | meta 추출 OK, body에 JSON 없음 |
| | 메타데이터 없는 출력 | meta=기본값, body=전체 |
| | 깨진 JSON (`{image_type: "photo"`) | meta=기본값, body=원문 유지 (폴백) |
| `_extract_clean_body()` | 들여쓰기 JSON 잔류 | 블록 스킵, body에 잔류 없음 |
| | 다중 JSON 객체 잔류 | 모두 스킵 |
| | `image_type` 키만 있는 부분 JSON | 스킵 |

### 통합 테스트 (신규)
- `test_chain_publisher_core.py`: `_publish_hugo()` → `_verify_before_deploy()` 통과 검증 (mock AI 출력에 JSON 포함 케이스)
- `test_chain_publisher.py`: `publish_chain()` → Step 1/2/3 모두 `url` 반환 검증 (mock AI 출력에 JSON 포함 케이스)

### 회귀 테스트
- `pytest -q` → **792 tests** 통과 (기존 기능 회귀 없음)
- 특히 `test_chain_drafter.py`, `test_chain_publisher_core.py`, `test_chain_models.py` 전체 통과

### 검증 기준
- **정량**: `pytest --co -q` 결과 792 tests 통과
- **정성**: Chain #378 재발행 시 Step 1/2/3 모두 `✅ Step X published: <url>` 출력, 배포 검증 통과, 카드 주입 정상 동작(Step 1 next URL 존재 → 카드 주입 성공)

## 추가 조사 항목 (이번 수정엔 미포함, 기록만)

> **같은 모델인데 Step 3은 정상이고 Step 1·2만 원시출력이 섞인 이유가 step별 프롬프트 차이인지 모델 출력 비결정성인지** — 다음 진단 대상.  
> (Step 3은 `image_type=photo` 강제 + 프롬프트 차이로 JSON 블록이 코드펜스 안에 들어가거나 아예 출력이 깔끔했을 가능성. 프롬프트별 `draft_user` 템플릿 비교 및 모델 출력 샘플링 필요.)

## Task 분해 (순차 실행)

| Task | 설명 | 산출물 |
|------|------|--------|
| T1: 백업 | 수정 대상 파일 4개 백업 (`chain_models.py`, `chain_publisher_core.py`, `chain_publisher.py`, `chain_drafter.py` 관련 테스트) | `*.bak` 파일 4개 |
| T2: 파싱 분리 구현 | `chain_models.py`의 `_extract_meta_from_raw()` / `_extract_body_from_raw()` 재작성 — 중괄호 깊이 카운팅으로 JSON 블록 탐지, 메타/본문 완전 분리 | `chain_models.py` 수정 |
| T3: 2차 방어 구현 | `chain_publisher_core.py`의 `is_raw_json` (line 117) / `skip_json_block` (line 90-97) 블록 단위 탐지로 재작성 | `chain_publisher_core.py` 수정 |
| T4: 관측성 로깅 | `chain_publisher.py:474-478` try-except 추가, `_verify_before_deploy()` 실패 컨텍스트 로깅 | `chain_publisher.py`, `chain_publisher_core.py` 수정 |
| T5: 단위/통합 테스트 작성 | 위 테스트 계획에 따른 신규 테스트 케이스 추가 | `test_chain_models.py`, `test_chain_publisher_core.py`, `test_chain_publisher.py` 확장 |
| T6: 전체 테스트 실행 + 회귀 확인 | `pytest -q` → 792 tests 통과 | 로그 |
| T7: Chain #378 재발행 검증 | `--chain-id 378 --publish` → 3개 스텝 모두 성공, 카드 주입/배포 정상 | 실측 로그 |

## 리스크/롤백

| 리스크 | 완화 | 롤백 절차 |
|--------|------|-----------|
| 파싱 로직 변경으로 메타 추출 실패(깨진 JSON 등) | 폴백: 메타 추출 실패 시 `meta=기본값`, `body=원문` 유지 (기존 `_extract_meta_from_raw()` 마지막 `return {}` 유지) | `git checkout chain_models.py chain_publisher_core.py chain_publisher.py` |
| `_extract_clean_body()` 블록 단위 탐지 과탐(일반 텍스트를 JSON으로 오인) | `image_type`/`chart_type` 키 존재 시에만 스킵 (키 존재 조건 유지) | 동일 |
| 반환 규약 변경으로 호출부 오류 | 반환 타입/규약 변경 없음 (위 표 참고). 단위 테스트로 검증. | 동일 |

## 완료 기준

1. `pytest -q` → **792 tests 통과**
2. Chain #378 `--publish` → Step 1/2/3 모두 `✅ Step X published: <url>` 출력
3. 배포 검증 통과 (JSON 잔류 0, 광고 슬롯 ≤3, 이미지 참조 정상)
4. 카드 주입 정상 (Step 1 next URL 존재 → `✅ Step 1 next card injected`)
5. `.bak` 파일 4개만 생성, 기타 의도치 않은 파일 변경 없음

---

**승인 대기 중 — 실행하지 않음**