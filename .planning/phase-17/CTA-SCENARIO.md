# CTA 시나리오 설계 — Phase 17 (v2: 대표님 방침 반영)

**생성일:** 2026-07-24 v1 → 2026-07-24 v2 (5건 정리)  
**Phase:** 17  
**Mode:** design-only (코드 착수는 5건 확정 후)  
**Owner:** 대표님 + 신입 에이전트

---

## 1. 현재 CTA 구조 분석

| 계층 | 현재 위치 | 형태 | 내용 |
|------|-----------|------|------|
| A. 카드 CTA | `chain_card_injector.py` `get_cta(blog_key, direction)` | shortcode `chain-card` | 사이트×direction별 고정 문구 (category 무관) |
| B. 듀얼 CTA | `chain_card_injector.py` `DualCTAInjector` | shortcode `dual-cta` | 정보성("관련 글 모두 보기 →") + 전환성("추천 상품 보기 →") 2종 |
| C. Step 문구 | `prompts.yaml` draft_user | 본문 내 유도문 | "예약 시 확인하세요" 등 (프롬프트 지시, 실제 고정 CTA 아님) |

### 문제점 (현재 상태)
- **단일 CTA:** `get_cta()`는 `(blog_key, direction)`만 받고 category 모름. 모든 카테고리가 동일 문구.
- **내부이동 vs 최종행동 미분리:** Depth0/1은 next card, Depth2는 external card. rotcha hub 유입 CTA 없음.
- **전환성 CTA 목적지 없음:** `DualCTAInjector.conv_cta_url` = `""` → `#` (dead link). 애드센스 전환 후 제휴 링크가 없음.
- **플레이스홀더 잔존 위험:** `{{CPA_LINK_PLACEHOLDER}}`가 코드/DB에 남아있을 수 있음 (확인 필요).

---

## 2. 카테고리별 독자 행동 여정 (분석 — 문구 결정과 무관, 유지)

| 키워드 카테고리 | 체인 방향 | Step 1 (rotcha) | Step 2 (issue.techpawz) | Step 3 (techpawz) |
|----------------|-----------|-----------------|-------------------------|-------------------|
| **travel** | lateral | 정보탐색 → 다음 단계 예고 | 비교/해석 → 예약 전략 | 결정/예약 → 핵심 체크리스트 |
| **real_estate** | depth | 개요/정보 → 계약 기초 | 비교/분석 → 대출/세금 | 실행/입주 → 계약서·하자보수 |
| **automotive** | depth | 개요/정보 → 구매 판단 | 비교/분석 → 할인/리스 | 실행/인도 → 점검표·유지비 |
| **stock** | depth | 개념/정보 → 기본 지표 | 비교/분석 → 매매 전략 | 실행/관리 → 타이밍·분산 |
| **etc** | depth | 개요/정보 → 문제 상황 | 비교/분석 → 대안 탐색 | 실행/선택 → 후속 조치 |

---

## 3. CTA 문구 — 단일 방침 (v2: 대표님 확정 반영)

### 3.0 방침

> **"더 알아보기"로 통일. 빨간 배경(#DC2626) / 흰 글씨 카드.**
> 카테고리 차이는 CTA 문구가 아니라 **링크 목적지**로만 분기한다.

### 3.1 통일 CTA 문구

| 위치 | CTA 텍스트 | 스타일 |
|------|-----------|--------|
| 체인 카드 (chain-card shortcode) | `더 알아보기 →` | 빨간 배경(#DC2626) / 흰 글씨 |
| 듀얼 CTA 정보성 | `이 시리즈 보기 →` | 빨간 배경(#DC2626) / 흰 글씨 |
| 듀얼 CTA 전환성 | 사용 안 함 (폐기, see §6) | — |
| Step 3 듀얼 (hub) | `전체 글 모아보기 →` | 빨간 배경(#DC2626) / 흰 글씨 |

### 3.2 링크 목적지 (카테고리별 분기 — 이것만 다름)

| 카테고리 | chain-card (내부이동) | hub CTA ({{ENTRY_LINK}}) |
|----------|----------------------|--------------------------|
| travel | 다음 step 포스트 URL | rotcha.kr/hub/{slug} |
| real_estate | 다음 step 포스트 URL | rotcha.kr/hub/{slug} |
| automotive | 다음 step 포스트 URL | rotcha.kr/hub/{slug} |
| stock | 다음 step 포스트 URL | rotcha.kr/hub/{slug} |
| etc | 다음 step 포스트 URL | rotcha.kr/hub/{slug} |

> **차이 없음.** 전 카테고리가 동일한 링크 구조. `{{ENTRY_LINK}}`만 사용 ($6 참조).

### 3.3 억지 CTA 제외 — 전 카테고리 공통

| 금지 표현 | 이유 |
|-----------|------|
| "지금 구매하세요", "한정 수량", "마감 임박" | 구체적 수치/시간 강요 → anti-hallucination 위반 |
| "최저가 보장", "오늘만 특가" | 객관적 수치와 무관한 구매 유도 |
| "지금 매수", "곤두박질" | 구체적 시점·수익 보장 표현 |
| "오늘 계약", "지금 청약" | 실제 딜러/분양 일정과 무관 |
| "아래 버튼", "링크를 클릭" | 카드 CTA를 본문에서 언급 → prompt leak |

---

## 4. keyword_categories `cta_phrases` 필드 설계안 (v2: 단순화)

### 4.1 YAML 구조

```yaml
keyword_categories:  
  travel:
    patterns: [ ... ]
    cta_phrases:
      next_post: "더 알아보기 →"
      entry_funnel: "{{ENTRY_LINK}}"
      fallback: "관련 주제 보기 →"
```

### 4.2 규칙

- `next_post`: 다음 step으로의 내부이동 카드 CTA — 전 카테고리 "더 알아보기 →" 통일
- `entry_funnel`: rotcha hub 유입 링크 플레이스홀더 (카테고리 무관 동일 hub URL)
- `fallback`: 매칭 실패 시 기본 CTA
- **`action_funnel` / `{{FUNNEL_LINK}}` 폐기** — 애드센스 모델에서 목적지 없음 ($6 참조)

### 4.3 필드 의미

| 필드 | 타입 | 용도 |
|------|------|------|
| `next_post` | string | 체인 내 다음 글 카드 CTA (전 category "더 알아보기 →") |
| `entry_funnel` | string | `{{ENTRY_LINK}}` — 발행 시 rotcha hub URL로 치환 |
| `fallback` | string | 카테고리 미매칭 시 대체 CTA |

---

## 5. Step별 주입 위치 설계안 (v2: 실제 코드 대조 완료)

### 5.1 실제 현재 동작 (chain_card_injector.py 기준, 2026-07-24 코드 읽음)

| 삽입 위치 | 실제 규칙 | 코드 위치 | 5.1절 v1 주장과 일치? |
|-----------|----------|-----------|----------------------|
| 중간 카드 | H2가 **3개 이상**일 때 2번째 H2 직후 1개 | `should_inject_middle_card()` L323, `inject_middle_card()` L328 | ✅ 일치 |
| 하단 카드 | 마지막 H2 섹션 이후 | `inject_bottom_card()` L301 | ✅ 일치 |
| 상단 카드 | 금지 | 상단 주입 코드 없음 | ✅ 일치 |
| depth0/1 | next card (chain-card shortcode) | `inject_cards_into_draft()` L448-451 | ✅ 일치 |
| depth2 | external link card (raw HTML) | `inject_cards_into_draft()` L439-446 | ✅ 일치 |
| CTA 결정 | `get_cta(blog_key, direction)` — config/sites/{blog}/card_cta | `get_cta()` L223 | ✅ 현재는 category 없음 (설계 차이) |
| conv CTA URL | `loop.cta.conv_cta_url` = `""` → `#` (dead link) | `DualCTAInjector.__init__()` L539, `build_dual_cta_html()` L550-552 | ⚠️ doc엔 "config에서 읽기"로 돼 있으나 실제로는 빈 값 |

**핵심 차이:** 코드는 `get_cta(blog_key, direction)`만 지원. Category awareness 없음. v1 설계에서 제안한 category→CTA mapping은 아직 구현되지 않았으며, 문구가 전 카테고리 통일되면 category 파라미터가 불필요해짐.

### 5.2 제안: 주입 위치 (단순화)

| 위치 | Step 1 | Step 2 | Step 3 |
|------|--------|--------|--------|
| 마지막 H2 후 | chain-card (Step+1) | chain-card (Step+1) | chain-card (hub) |
| 중간 H2 후 (3개 이상) | — | chain-card (Step+1) | — |
| 본문 내 링크 | 금지 | 금지 | 금지 (카드 shortcode만 허용) |

### 5.3 필수 규칙

1. **카드 shortcode만 사용** — 본문 내 단순 텍스트 링크 CTA 금지
2. `<!--next_link-->` 주석 위치 우선 사용 (현재 `inject_bottom_card` 동작 유지)
3. 중간 카드는 H2 **3개 이상**일 때 2번째 H2 직후 1개 (코드 기준 그대로)
4. Step 3 하단 카드는 hub CTA(`{{ENTRY_LINK}}`) 1종만 — 듀얼 CTA 폐기 ($6)

---

## 6. 플레이스홀더 — {{FUNNEL_LINK}} 폐기 (v2: 핵심 변경)

### 6.1 채택: `{{ENTRY_LINK}}` **만** 유지

| 플레이스홀더 | 의미 | 상태 |
|--------------|------|------|
| `{{ENTRY_LINK}}` | rotcha hub 유입 링크 (퍼널 입구) | **✅ 유지** — `loop_chains.hub_url` 컬럼 이미 존재 |
| `{{FUNNEL_LINK}}` | 최종 행동 링크 (예약/문의/구매/제휴) | **❌ 폐기** — 애드센스 모델에서 목적지 없음 |

### 6.2 {{FUNNEL_LINK}} 폐기 근거 (코드 조사 결과)

| 확인 항목 | 결과 |
|-----------|------|
| `loop_chains.hub_url` 컬럼 | ✅ 존재 (DB 스키마에 있음, 현재 3건 모두 NULL) |
| {{FUNNEL_LINK}}에 대응하는 테이블/컬럼 | ❌ **없음** — `action_url`, `funnel_url`, `conv_url` 컬럼 DB 어디에도 없음 |
| `DualCTAInjector.conv_cta_url` | ✅ `""` → `#` (하드코딩 dead link, config에서 읽지만 빈 값) |
| `chain_card_injector.py` 내 funnnel 관련 코드 | ❌ **없음** — `{{FUNNEL_LINK}}`는 현재 코드에서 전혀 치환되지 않음 |
| `chain_publisher_core.py` 내 플레이스홀더 치환 | ❌ **없음** — `_sanitize_markdown_body()`에 플레이스홀더 치환 코드 없음 |

**결론:** `{{FUNNEL_LINK}}`는 현재 코드에서 **정의되지 않았고**, 목적지(제휴/구매/예약 링크)도 없다. 애드센스 모델로 전환한 이후로는 이 플레이스홀더가 갈 곳이 없다. 이번 스코프에서 제외한다. 나중에 별도 링크 모델(예: 제휴 복귀)이 생기면 다시 도입.

### 6.3 {{ENTRY_LINK}} 치환 소스

- `loop_chains.hub_url` 컬럼에 저장 (이미 존재, 현재 NULL)
- 발행 시 `chain_card_injector.py` 또는 `chain_publisher_core.py`에서 치환
- hub URL은 체인 생성 시점에 결정 → `chain_deriver.py` 또는 `chain_publisher_core.py`에서 `loop_chains.hub_url` 업데이트
- **구체적 치환 시점:** 코드화 단계에서 결정 (config 기반 vs DB 조회)

---

## 7. 프롬프트 릭 방지 설계 (v2: Phase 19 계보 연결)

### 7.1 Phase 19 계보 분석 결과

Phase 19 릭 계보 분석에서 다음이 확인됨:

| 게이트 | 위치 | CTA 텍스트 릭 상태 |
|--------|------|-------------------|
| D3 (image prompt) | `chain_drafter.py` | CTA와 무관 |
| D6 (draft 생성) | `chain_drafter.py` → GPT output | **릭 발생 가능** — CTA 문구가 본문에 평문으로 생성됨 |
| D8 (markdown cleanup) | `chain_publisher_core.py` `_sanitize_markdown_body()` | CTA 텍스트 미검사 (markdown만 정리) |
| D9 (card injection) | `chain_card_injector.py` `inject_cards_into_draft()` | **릭 중복** — 기존 카드 제거는 하지만 본문 내 릭 CTA는 그대로 둠 |
| D11 (테스트) | pytest | **유일하게 막는 게이트** — `test_prompt_leak.py`가 CTA 문자열 검출 |

**구멍:** CTA 텍스트가 D6에서 생성되어 D8/D9를 뚫고 라이브까지 나간다. D11 테스트만 막고 있으나, 테스트가 모든 발행 건을 검사하는 것은 아니다.

### 7.2 발행 파이프라인 게이트 — CTA 텍스트 필터 삽입

| 게이트 | 조치 | 적용 항목 |
|--------|------|-----------|
| **D8 후 (`_sanitize_markdown_body` 종료 직후)** | CTA 릭 스캐너 추가: 본문에 CTA 문구("더 알아보기", "관련 주제", "아래 버튼") 있으면 **WARNING 로그 + 자동 제거** | 발행 전 마지막 검증 |
| **D9 (`inject_cards_into_draft` 시작 직전)** | 기존 shortcode 제거 + `{{...}}` 플레이스홀더 검출 → 있으면 WARNING | 플레이스홀더 잔존 방지 |
| **D11 (테스트)** | `test_prompt_leak.py` 유지 — 발행 건 샘플링 + CTA 문자열 검출 | 기존 유지 |

### 7.3 주입 지시 (Prompt Injection Guard)

CTA 관련 내용은 본문 생성 시 **주입 지시로만 전달**한다.

```yaml
# prompts.yaml draft_user 에 추가될 지시 블록
[CTA GUIDELINES — prompt leak 금지]
- CTA 문구(더 알아보기 →)는 시스템이 나중에 주입하는 카드용입니다.
- 본문 마지막 문단에 위 CTA 문구를 직접 쓰지 마세요.
- CTA를 언급하는 문장도 쓰지 마세요 ("아래 버튼", "링크를 클릭" 등 금지).
- 각 step의 마지막 문단은 다음 글로 자연스럽게 연결하는 1문장으로만 마무리하세요.
- 플레이스홀더({{ENTRY_LINK}})가 본문에 직접 노출되지 않아야 합니다.
```

### 7.4 출력 검증 체크리스트 (D8/D9 게이트 자동화)

```yaml
[Output Checklist — CTA 릭 검증]  # D8 후 실행
- 본문에 "더 알아보기", "관련 주제" 등 CTA 문구가 직접 포함되어 있지 않은가?
- 본문에 "아래 버튼", "링크를 클릭하세요" 등 행동 지시 문구가 없지 않은가?
- Step 3 마지막 문단이 CTA 언급 없이 다음 글로 연결되는가?
- 플레이스홀더({{ENTRY_LINK}})가 본문에 직접 노출되어 있지 않은가?
```

### 7.5 시스템 설계 체크리스트

| 검증 항목 | 방법 | 적용 게이트 |
|-----------|------|------------|
| prompt leak | `draft_system` / `draft_user`에 CTA 문구 문자열 직접 노출 금지 | D6 (프롬프트 설계) |
| 플레이스홀더 노출 | 본문 출력 전 정규식 `{{...}}` 패턴 검출 시 WARNING | D8 |
| CTA 텍스트 직접 노출 | CTA blocklist regex scan → 발견 시 자동 제거 + WARNING | D8 |
| 카드 중복 삽입 | `inject_cards_into_draft` 전 기존 `chain-card` shortcode 제거 | D9 |
| 억지 CTA 감지 | ABSOLUTE BAN 항목 (per §3.3) — "지금 구매", "한정 수량" 등 | D8 |

---

## 8. 대표님 검토용 요약

### v1 → v2 변경 사항

| # | 과제 | 변경 | 근거 |
|---|------|------|------|
| 1 | 문구 방침 충돌 | 5개 카테고리 테이블 → **단일 문구 "더 알아보기"** + 빨간 배경/흰 글씨 | 대표님 확정 방침 반영 |
| 2 | etc 커머스 CTA | 구매/가격비교 CTA **삭제**, 내부이동만 유지 | etc는 방향 미확정, 커머스 유도는 제휴 잔향 |
| 3 | 삽입 규칙 vs 실제 코드 | 5.1절 **실제 코드와 대조 완료** — 일치 확인, 단 category awareness는 아직 없음 | `get_cta(blog_key, direction)` 확인 |
| 4 | {{FUNNEL_LINK}} 존폐 | **폐기 결정** — DB에 대응 컬럼 없음, conv_cta_url = empty → `#` | 코드 조사 완료, 대표님 사업 판단 대기 |
| 5 | 릭 방지 vs Phase 19 계보 | D8/D9 게이트에 CTA 텍스트 필터 명시 + Phase 19 계보 연결 | D11만 막는 구멍 해소 |

### 변경 필요 파일

| 파일 | 변경 내용 | 비고 |
|------|-----------|------|
| `config/prompts.yaml` | `keyword_categories` 아래 `cta_phrases` 노드 추가 (next_post + entry_funnel만) + draft_user CTA guideline | section 4 + 7.3 참조 |
| `chain_card_injector.py` | `get_cta()` CTA 문구 통일 → "더 알아보기" + 스타일 변경. `DualCTAInjector` 전환성 CTA 폐기 | section 3 + 5 참조 |
| `chain_publisher_core.py` | `_sanitize_markdown_body()` 후 CTA 릭 스캐너 추가 | section 7.2 참조 |
| `chain_deriver.py` 또는 `chain_publisher_core.py` | `loop_chains.hub_url` 업데이트 로직 추가 (현재 NULL) | section 6.3 참조 |

### Definition of Done 체크리스트 (v2)

- [x] CTA 시나리오 설계 완성 (5개 카테고리 → 단일 문구 통일)
- [x] 내부이동 CTA만 유지, {{FUNNEL_LINK}} 폐기 결정
- [x] 플레이스홀더 명칭 정리 완료 (`{{ENTRY_LINK}}`만 유지)
- [x] 프롬프트 릭 방지 설계 + 파이프라인 게이트 명시 (Phase 19 계보 연결)
- [x] mc 주입 구조 설계 완료 (YAML 단순화)
- [x] **5건 정리 완료** (v2: 대표님 피드백 반영)
- [ ] **대표님 최종 확정** (특히 {{FUNNEL_LINK}} 존폐 사업 판단)
- [x] 설계안 저장 (`.planning/phase-17/` 내)

---

## 9. 잔존 위험

1. **{{FUNNEL_LINK}} 존폐 — 대표님 사업 판단 필요.** 코드 조사 결과 DB 컬럼 없음, 목적지 없음, 현재 dead link. 애드센스 모델에서 폐기가 합리적이나, 나중에 제휴 모델 복귀 시 재도입 필요. 대표님이 최종 결정.
2. **`loop_chains.hub_url` 3건 모두 NULL.** hub URL 저장 로직이 현재 없음. 코드화 시 `chain_deriver.py` 또는 발행 시점에 hub URL 생성 + DB 저장 로직 추가 필요.
3. **`get_cta(blog_key, direction)` → category 파라미터 불필요해짐.** 모든 카테고리 "더 알아보기" 통일이므로, `get_cta(direction)`으로 단순화하거나 CTA 텍스트를 config가 아닌 코드 상수로 고정 가능. 기존 호출 지점과의 호환성 확인 필요.
