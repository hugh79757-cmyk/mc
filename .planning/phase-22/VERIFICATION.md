# VERIFICATION.md — Phase 22: 콘텐츠 품질 제어

**Phase:** 22  
**Created:** 2026-07-26  
**Status:** Pending

---

## Verification Strategy

각 Task별 단위 테스트 + 통합 테스트 + 파이프라인 E2E 검증

---

## Task 1: 글자수 기준 정립 + 검증 게이트

### 1.1 단위 테스트: `count_body_chars()` 함수

| 테스트 케이스 | 입력 | 기대 결과 |
|-------------|------|----------|
| 한글만 | "안녕하세요 이것은 본문입니다" | 13자 (공백 포함) |
| 영문만 | "Hello world this is body" | 24자 |
| 한영 혼합 | "안녕 Hello 123" | 11자 |
| Frontmatter 포함 | `---\ntitle: "Test"\n---\n\n본문 내용` | 4자 ("본문 내용") |
| H2 헤딩 포함 | `## 제목\n\n본문입니다` | 5자 ("본문입니다") |
| 리스트 포함 | `- 항목1\n- 항목2\n\n본문` | 3자 ("본문") |
| 표 포함 | `| A | B |\n|---|---|\n| 1 | 2 |\n\n본문` | 3자 ("본문") |
| 코드 블록 포함 | ```\ncode\n```\n\n본문 | 3자 ("본문") |
| 이미지 마커 포함 | `<!--todo:image-->\n본문` | 3자 ("본문") |
| HTML 주석 포함 | `<!-- comment -->\n본문` | 3자 ("본문") |
| JSON 메타 포함 | `{"image_type": "photo"}\n본문` | 3자 ("본문") |

**파일:** `test_chain_drafter.py`에 `TestCountBodyChars` 클래스 추가

### 1.2 단위 테스트: `_validate_draft_schema()` 글자수 검증

| 테스트 케이스 | 설정 | 기대 결과 |
|-------------|------|----------|
| 기준 충족 | min=1000, actual=1200 | (True, "스키마 검증 통과") |
| 최소 미달 | min=1000, actual=800 | (True, "quality_warning: undercount (800/1000)") |
| 최대 초과 | max=1500, actual=1800 | (True, "quality_warning: overcount (1800/1500)") |
| meta 없음 | meta=None | 기존 검증만 수행 (글자수 스킵) |
| 차트 마커 | `<!--todo:chart-->` + min=1000, actual=500 | 글자수 검증 스킵 (차트는 글자수 기준 적용 안 함) |

**파일:** `test_chain_drafter.py`에 `TestValidateDraftSchemaCharCount` 클래스 추가

### 1.3 통합 테스트: `draft_chain()` 품질 경고 DB 기록

| 테스트 | 검증 내용 |
|--------|-----------|
| 글자수 미달 체인 발행 | `chain_posts.quality_warnings`에 `["undercount"]` 기록됨 |
| 정상 체인 발행 | `quality_warnings` 빈 배열 또는 NULL |

**파일:** `test_chain_drafter.py` 또는 `test_chain_publisher.py`에 추가

### 1.4 마이그레이션 검증

- `chain_db.init_db()` 실행 후 `PRAGMA table_info(chain_posts)`에 `quality_warnings` 컬럼 존재 확인
- 기존 DB에서 마이그레이션 실행 시 에러 없음

---

## Task 2: CTA 코드화

### 2.1 단위 테스트: `get_cta()` 함수

| 테스트 케이스 | 입력 | 기대 출력 |
|-------------|------|----------|
| Depth 0 (Step 1) | category=travel, depth=0, next_url=/post2 | chain_card, text="더 알아보기 →", url=/post2 |
| Depth 1 (Step 2) | category=stock, depth=1, next_url=/post3 | chain_card, text="더 알아보기 →", url=/post3 |
| Depth 2 (Step 3) | category=travel, depth=2, hub_url=/hub/xyz | hub_cta, text="전체 글 모아보기 →", url=/hub/xyz |
| 중간 카드 (H2 3개) | depth=1, is_middle=True | dual_info, text="이 시리즈 보기 →" |
| 알 수 없는 카테고리 | category=unknown, depth=0 | fallback: "관련 주제 보기 →" (chain_card) |

**파일:** `test_chain_card_injector.py`에 `TestGetCTA` 클래스 추가

### 2.2 단위 테스트: AI 생성 CTA 감지 + 제거 (`_strip_ai_cta`)

| 테스트 케이스 | 입력 본문 | 기대 결과 |
|-------------|-----------|----------|
| "더 알아보기" 직접 작성 | `본문\n\n더 알아보기\n\n다음 글에서...` | 제거됨, warning 로그 |
| "아래 버튼을 클릭하세요" | `자세한 내용은 아래 버튼을 클릭하세요` | 제거됨, warning 로그 |
| "지금 구매하세요" (금지표현) | `지금 구매하세요!` | 제거됨, warning 로그 (forbidden_cta) |
| "링크를 클릭해 보세요" | `링크를 클릭해 보세요` | 제거됨 |
| 공식 CTA shortcode | `{{< chain-card >}}` | **제거 안 됨** (보호) |
| `{{ENTRY_LINK}}` 플레이스홀더 | `{{ENTRY_LINK}}` | 제거됨 (placeholder_leak) |

**파일:** `test_chain_publisher_core.py`에 `TestCTALeakFilter` 클래스 추가

### 2.3 단위 테스트: 최종 마크다운 CTA 개수 검증 (`_verify_cta_count`)

| 테스트 케이스 | Step | H2 개수 | 기대 CTA 개수 | 결과 |
|-------------|------|--------|--------------|------|
| Step 1 기본 | 1 | 3 | chain-card 1개 (하단) | Pass |
| Step 2 H2 4개 | 2 | 4 | chain-card 2개 (하단+중간) | Pass |
| Step 3 허브 | 3 | 3 | hub_cta 1개 | Pass |
| HTML CTA 직접 삽입 | 1 | 3 | html_cta > 0 | Fail (DeployValidationError) |
| chain-card 3개 | 1 | 3 | chain-card > 2 | Fail |

**파일:** `test_chain_publisher_core.py`에 `TestVerifyCTACount` 클래스 추가

### 2.4 통합 테스트: 기존 체인 발행 플로우에서 CTA 정상 주입

```bash
mc "테스트키워드" --draft
# chain_posts.draft_md에 chain-card shortcode 1개 포함 확인
mc "테스트키워드" --image
# 이미지 생성 후 CTA 유지 확인
mc "테스트키워드" --publish
# 발행된 HTML에 chain-card shortcode 렌더링 확인
```

---

## Task 3: 릭 방어 패턴 통합 + SEO 메타 보강

### 3.1 단위 테스트: `strip_leaks()` 함수

| 테스트 케이스 | 입력 | 기대 제거 | 컨텍스트 |
|-------------|------|----------|---------|
| 프롬프트 릭 헤더 | `# Role:\n내용\n## 서론\n본문` | `# Role:` 블록 전체 | "draft" |
| 프롬프트 릭 인라인 | `본문\n이전 포스트 (내용)\n계속` | `이전 포스트 (내용)` | "draft" |
| CTA 릭 (D8-GATE 패턴) | `본문\n더 알아보기\n계속` | `더 알아보기` | "body" |
| CTA 릭 (금지표현) | `지금 구매하세요!` | `지금 구매하세요!` + warning | "body" |
| 플레이스홀더 | `링크: {{ENTRY_LINK}}` | `{{ENTRY_LINK}}` | "body" |
| Shortcode 보호 | `{{< chain-card >}}` | **제거 안 됨** | "body" |
| HTML 태그 | `<div class="cta">CTA</div>` | `<div...>...</div>` 전체 | "html" |
| JSON 누수 | `{"image_type": "photo"}\n본문` | JSON 객체 전체 | "body" |
| 복합 (여러 릭 동시) | 위 모든 것 혼합 | 각 카테고리별 제거 카운트 리포트 | "test" |

**검증:** 리포트 딕셔너리에 각 카테고리별 `removed` 카운트, `matches` 배열 포함 확인

**파일:** `test_chain_publisher_core.py`에 `TestStripLeaks` 클래스 추가

### 3.2 회귀 테스트: 기존 leak 방어 코드 교체 후 동일 동작

| 기존 테스트 | 파일 | 검증 내용 |
|------------|------|----------|
| `test_strip_prompt_leak_*` | `test_chain_drafter.py` | `_strip_prompt_leak` → `strip_leaks` 교체 후 동일 통과 |
| `test_sanitize_*` | `test_chain_publisher_core.py` | D8-GATE CTA/placeholder 제거 동일 동작 |
| `test_prompt_leak.py` 전체 | `test_prompt_leak.py` | audit 모듈 교체 후 동일 통과 |
| `assert_no_prompt_leak` | `conftest.py` 헬퍼 | `strip_leaks` 기반 재작성 후 동일 동작 |

### 3.3 단위 테스트: SEO 메타 보강

| 테스트 케이스 | 입력 | 기대 결과 |
|-------------|------|----------|
| description 150자 초과 | 200자 description | 150자로 잘림 + "..." suffix, warning 로그 |
| description 150자 이내 | 100자 description | 그대로 유지 |
| 이미지 alt 비어있음 | `![](https://img.url/img.webp)` | `![제목...](https://img.url/img.webp)`로 변환 |
| 이미지 alt 있음 | `![이미지 설명](url)` | 그대로 유지 |
| featureimage → images 배열 | featureimage=R2 URL | frontmatter에 `images: [url]` 추가 |

**파일:** `test_chain_publisher_core.py`에 `TestSEOMeta` 클래스 추가

### 3.4 통합 테스트: 전체 파이프라인 품질 게이트

```bash
# 1. 글자수 미달 체인 생성 (의도적으로 짧은 프롬프트 또는 mock)
mc "테스트" --draft
# quality_warnings에 "undercount" 기록 확인

# 2. AI CTA 포함된 초안 강제 주입 후 발행
# chain_publisher.py에서 draft 생성 후 CTA 문구 삽입 → 발행
# D8-GATE에서 자동 제거 확인

# 3. 전체 테스트 스위트 통과
python -m pytest -q
# 251 + 신규 테스트 모두 통과
```

---

## Acceptance Criteria (Definition of Done)

### Task 1 완료 조건
- [ ] `config/prompts.yaml`에 전 카테고리 `char_count` 필드 추가됨
- [ ] `count_body_chars()` 함수 구현 + 단위 테스트 10개 이상 통과
- [ ] `_validate_draft_schema()` 글자수 검증 추가 + 테스트 5개 통과
- [ ] `quality_warnings` DB 컬럼 추가 + 마이그레이션 동작
- [ ] 글자수 미달 시 warning 로그 + 파이프라인 계속 진행 확인

### Task 2 완료 조건
- [ ] `config/cta_templates.yaml` 생성 (Phase 17 설계 반영)
- [ ] `mc/cta.py` `get_cta()` 함수 구현 + 단위 테스트 5개 통과
- [ ] `chain_card_injector.py` CTA 주입 로직 교체 + 기존 호출부 호환
- [ ] `DualCTAInjector` 전환성 CTA 코드 완전 제거
- [ ] `_strip_ai_cta()` 필터 구현 + 단위 테스트 6개 통과
- [ ] `_verify_cta_count()` 검증 함수 구현 + 단위 테스트 5개 통과
- [ ] `mc "키워드" --draft/--image/--publish` 통합 테스트 통과

### Task 3 완료 조건
- [ ] `config/leak_defense.yaml` 생성 (전 패턴 통합)
- [ ] `mc/leak_defense.py` `strip_leaks()` 구현 + 단위 테스트 15개 이상 통과
- [ ] `chain_drafter.py` `_strip_prompt_leak` → `strip_leaks` 교체
- [ ] `chain_publisher_core.py` D8-GATE → `strip_leaks` 교체
- [ ] `audit/audit_chain.py` `check_prompt_leak`/`check_cta_leak` → `strip_leaks` 교체
- [ ] `conftest.py` 헬퍼 함수 `strip_leaks` 기반 재작성
- [ ] SEO 메타 보강: description 150자 제한, 이미지 alt 자동 추가, images 배열
- [ ] 전체 pytest **251 + 신규 테스트** 모두 통과
- [ ] `mc "테스트키워드" --draft` 실행 시 품질 게이트 동작 확인 (로그 출력)

---

## Test Count Summary

| Task | 신규 단위 테스트 | 통합/회귀 테스트 |
|------|----------------|-----------------|
| Task 1 | 15 (count_body_chars 10 + validate_schema 5) | 2 |
| Task 2 | 16 (get_cta 5 + CTA filter 6 + verify_cta 5) | 3 |
| Task 3 | 25 (strip_leaks 15 + SEO meta 5 + 회귀 5) | 2 |
| **Total** | **56** | **7** |

**예상 최종 테스트 수:** 251 (기존) + 56 (신규) = **307+ 개**

---

## Verification Commands

```bash
# 1. 단위 테스트만 실행
python -m pytest test_chain_drafter.py::TestCountBodyChars -v
python -m pytest test_chain_drafter.py::TestValidateDraftSchemaCharCount -v
python -m pytest test_chain_card_injector.py::TestGetCTA -v
python -m pytest test_chain_publisher_core.py::TestCTALeakFilter -v
python -m pytest test_chain_publisher_core.py::TestVerifyCTACount -v
python -m pytest test_chain_publisher_core.py::TestStripLeaks -v
python -m pytest test_chain_publisher_core.py::TestSEOMeta -v

# 2. 회귀 테스트
python -m pytest test_chain_drafter.py::TestStripPromptLeak -v
python -m pytest test_prompt_leak.py -v
python -m pytest test_chain_publisher_core.py -k "sanitize" -v

# 3. 전체 테스트 스위트
python -m pytest -q
# 307+ passed 확인

# 4. E2E 파이프라인 품질 게이트 확인
mc "테스트키워드" --draft 2>&1 | grep -E "(QUALITY|quality_warning|글자수|CTA|leak)"
```