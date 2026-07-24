# CONTEXT.md — mc 열린 잔존 과제

**생성:** 2026-07-24  
**이유:** Phase 18~19 작업 종료 (품질 평가 → P0 릭 → P1 depth 연결 → 릭 계보 → 카드 라이브)  
**성격:** 새 코드 금지, 기존 설계/분석 산출물만 정리

---

## Phase 19 오진 인지

Phase 19에서 "카드 렌더링 실패"라고 진단했으나, **라이브 rotcha.kr에서 카드가 정상 렌더링 중**이었다 (curl 3건 1 match each).  
실제 위험은 **shortcode 파일 git 미추적**이었고, Phase 19가 이 latent risk를 active failure로 과잉 진단한 것.

**교훈:** `git status`를 진단의 첫 단계로 삼을 것. "disk에 파일이 있음" != "git에 있음".

---

## 열린 잔존 과제

### 1. P2 — 글자수·travel 비교 대상 구체화

- **소스:** Phase 15~16 설계에서 이월
- **내용:**
  - `prompts.yaml` 글자수 제한이 영문/한글/숫자 혼합 시 기준 불명확
  - travel/lateral 카테고리 비교 대상 사이트 목록이 구체화되지 않음 (호텔스컴바인? 야놀자? 어떤 기준?)
- **상태:** 설계 미착수
- **Priority:** P2

### 2. Persona 어조

- **소스:** Phase 13 콘텐츠 고도화 이후 미처리
- **내용:**
  - 사이트별(depth별) persona/어조를 설계하지 않음
  - rotcha.kr(Step 1)은 정보성, techpawz(Step 3)는 실행/구매 지향 → 각 site/depth에 맞는 persona tone이 prompt에 명시적으로 주입되지 않음
- **상태:** 설계 미착수
- **Priority:** P3

### 3. 발행 파이프라인 CTA 텍스트 필터 부재

- **소스:** Phase 17 CTA-SCENARIO.md 설계 완료 후 코드화 단계
- **내용:**
  - 현재 CTA 텍스트는 `chain_card_injector.py` `get_cta()`가 site×direction만 보고 고정 문구를 반환
  - 플레이스홀더 잔존({{CPA_LINK_PLACEHOLDER}} 등), 프롬프트 릭 CTA, 어색한 CTA가 발행 전 검증되지 않음
  - `chain_publisher_core.py` `_sanitize_markdown_body()`는 본문 cleanup만 하고 CTA 텍스트는 건드리지 않음
  - Phase 17 설계(카테고리별 CTA + 내부이동/최종행동 분리) 구현 전 단계
- **상태:** Phase 17 대표님 검토 대기 중 → 설계 확정 후 코드 착수 필요
- **Priority:** P1

### 4. 릭 방어 패턴 상수 통합

- **소스:** Phase 9~11에서 여러 파일에 분산 추가
- **내용:**
  - `chain_drafter.py::_strip_prompt_leak()` — 문자열 리스트 하드코딩
  - `chain_publisher_core.py::_sanitize_markdown_body()` — 별도 리스트
  - `chain_publisher_core.py::_inject_card_cta()` — 또 다른 검증
  - 동일한 성격의 방어 패턴(거부 문구, 명령 주입, 마크다운 탈출)이 각 파일에 중복됨
  - 상수(blocklist, regex 패턴)를 한 곳에 모아서 `config/leak_defense.yaml` 또는 별도 모듈로 통합 필요
- **상태:** 식별만 됨, 통합 미착수
- **Priority:** P2

---

## 잠재 위험 — Shortcode 파일 git 미추적

| 사이트 | shortcode 3개 파일 | git 상태 | 영향 |
|--------|-------------------|---------|------|
| rotcha-blog | `chain-card.html`, `chain-official-card.html`, `dual-cta.html` | `? layouts/shortcodes/` — 디렉토리 전체 **UNTRACKED** | clone/CI 빌드 시 shortcode 누락 → `{{< chain-card >}}` 가 raw text로 렌더링 또는 Hugo build 실패 |
| techpawz-hugo | 동일 3개 파일 | `? layouts/shortcodes/` — 동일 **UNTRACKED** | 동일 |
| issue-techpawz-hugo | 해당 없음 (card_injected=0) | — | 해당 없음 |

**왜 지금 라이브가 정상인가:** disk에 .html 파일이 존재하므로 `hugo build`는 정상. git clone 또는 CI/CD(wrangler pages deploy가 source를 fetch해서 자체 빌드하는 경우)에서 단절됨.  
**해결:** `git add layouts/shortcodes/ && git commit` — 3개 파일, 추정 1분 작업.

---

## Phase 20 실측 결과 — 검색 유효성 카테고리별 차이

Phase 20의 `--search` global default와 STOCK & AUTOMOTIVE GROUNDING block 적용 후 실측 결과:

| 카테고리 | 검색 유효성 | 실측 근거 |
|---------|------------|----------|
| **Stock** | ✅ **효과적** | Investing.com 구조화 데이터(주당배당금, 배당락일, 배당수익률) 직접 반환. Chain 113 모든 숫자가 검색 자료에서 검증됨. |
| **Travel** | ✅ **효과적** | 실제 펜션명, 거리, 리뷰 수, 시설 정보 반환. Chain 114 S2에 `토담 독채 단체 풀빌라` 등 4개 펜션명 등장. |
| **Automotive** | ❌ **무효** | Naver → 현대자동차 기업 일반 정보(Wikipedia 수준)만 반환. 제품 스펙·가격·연비 데이터 전혀 없음. AI가 빈 데이터로 작동. |
| **Real Estate** | ⚠️ **미측정** | 아직 실측 안 함. |

**Automotive 함정:** Naver는 자동차 리뷰·스펙 페이지를 크롤링하지 않음 (cars.com, edmunds 등과 달리 국내 포털은 자동차 스펙 DB가 없거나 API로 제공 안 함). 해결하려면 별도 데이터 소스(R2에 주기적 동기) 또는 search_retriever에 automotive-specific search template 필요.

---

## 팩트 기준선 정책 (Phase 18-A 확정)

> **상위노출 검색 결과를 사실 기준선으로 신뢰(무한검증 회피 목적). 최신성·홍보성 출처 판별은 사람 체크리스트로 이월.**

---

| 작업 | 결과 |
|------|------|
| Phase 18: 품질 측정 인프라 검증 | RESEARCH.md + 5-Min 품질 체크리스트 |
| Phase 19 전반: P0 프롬프트 릭 탐지 | `_strip_prompt_leak()` 정상, 단 릭 계보 작성 완료 |
| Phase 19 중반: P1 depth 연결 사각지대 | 실제 라이브 링크 3건 정상 확인 |
| Phase 19 후반: 릭 계보 작성 | `.planning/phase-17/`에 정리 |
| 정보화면 오염 롤백 | informationhot-hugo revert + clean deploy 확인 |
| 카드 라이브 백필 | rotcha 25건, techpawz 21건 — 라이브 렌더링 확인 |

---

## 다음 착수 (대표님 우선순위 배정 대기)

```
1. Phase 17 검토 완료 → CTA 코드화 (발행 파이프라인 CTA 텍스트 필터 부재 해소)
2. Shortcode git add (잠재 위험 해소, 1분)
3. 릭 방어 패턴 상수 통합
4. P2 설계: 글자수 기준 + travel 비교 대상 구체화
5. Persona 어조 설계
```
