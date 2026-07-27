# CONTEXT.md — Phase 25: 고객센터 키워드 카테고리 설계

**Phase:** 25
**Created:** 2026-07-27
**Milestone:** 신규 키워드 카테고리 "고객센터" 설계 + 체인 깊이 프로그레션 + 체류시간 극대화
**Mode:** execute (설계 + 코드 착수)

---

## Objective

"여행(풀빌라/글램핑)", "주식(LG전자 주가전망)" 카테고리처럼 고품질 콘텐츠를 자동 생성할 수 있는 신규 키워드 카테고리 **"고객센터"**를 설계한다. Depth 0→1→2 점진적 깊이 프로그레션을 설계하여, 검색 유입 독자의 체류시간을 극대화하고 만족도를 높인다.

---

## Background

### 현재 카테고리 체계

| 카테고리 | 체인 방향 | Depth 0 (rotcha) | Depth 1 (issue.techpawz) | Depth 2 (techpawz) |
|---------|----------|-------------------|--------------------------|---------------------|
| travel | lateral | 주제/정보형 | 비교/탐색형 | 실전/확정형 |
| stock | depth | 기본 개념과 시장 흐름 | 실전 투자 전략 | 매수 타이밍/포트폴리오 |
| real_estate | depth | 단지 기본 정보 | 청약/계약 전략 | 계약서 조항/입주 |
| automotive | depth | 제품 개요/스펙 | 구매 전략 비교 | 인도 점검표/유지비 |

### "고객센터" 카테고리가 적합한 이유

1. **검색 의도 명확**: "고객센터 전화번호", "고객센터 연결 방법", "AS 접수 방법" 등 구체적 문제 해결형 검색
2. **Industry-agnostic**: IT, 이커머스, 금융, 통신, 항공, 공공기관 등 모든 산업군에 존재
3. **점진적 깊이 자연스러움**: 채널 소개 → 비교/운영 → 고도화/자동화 흐름이 자연스러움
4. **수익화 가능**: CRM 도구, 헬프데스크 솔루션, 아웃소싱 서비스 등 B2B 연계
5. **검색 트래픽 지속적**: "고객센터" 관련 검색은 계절성 없이 꾸준

### 체류시간 극대화 설계 원칙

1. **Depth 0 (rotcha)**: "무엇인가" — 고객센터의 개념, 채널별 특징, 업종별 차이. 독자가 자기 업종/상황에 맞는 채널을 찾게 유도
2. **Depth 1 (issue.techpawz)**: "어떻게 하는가" — 운영 비교, KPI 설정, 고객 응대 스킬, 시스템 도입 전략. 독자가 구체적 행동을 취하게 유도
3. **Depth 2 (techpawz)**: "왜 그런가" — AI 챗봇, CRM 트렌드, 산업별 벤치마크, 미래 전망. 독자가 심층 이해→의사결정하게 유도

### 검색 만족도 극대화 전략

- **Q&A 매칭**: 검색 쿼리("고객센터 전화번호", "AS 접수")에 직접 답하는 H2 섹션 배치
- **테이블/리스트**: 채널별 비교표, 업종별 고객센터 목록 등 구조화된 정보
- **실용적 정보**: 실제 전화번호, 운영시간, 연결 방법 등 즉시 활용 가능한 정보
- **체인 연결**: Depth 0→1→2 자연스러운 흐름으로 체류시간 증대

---

## Scope

### In Scope (Phase 25)

**Task 1: "고객센터" 키워드 카테고리 설계**
- `config/prompts.yaml`에 `customer_service` 카테고리 추가
  - patterns (정규식): 고객센터, 고객지원, helpdesk, AS, 상담, 문의, 클레임, 서비스센터 등
  - char_count: site별 (rotcha 1000-1500, issue_techpawz 1500-2500, techpawz 1500-2500)
  - step1/2/3_sections: Depth별 H2 가이드라인
  - cta_phrases: 통일 ("더 알아보기 →")

**Task 2: Depth별 콘텐츠 프로그레션 설계**
- Depth 0 (rotcha): 고객센터 개요, 채널별 특징, 업종별 비교, 핵심 요약
- Depth 1 (issue.techpawz): 운영 비교, KPI/CSAT, 시스템 도입, 응대 스킬
- Depth 2 (techpawz): AI/자동화, CRM 트렌드, 산업 벤치마크, 미래 전망

**Task 3: `chain_config.yaml` 키워드 매핑 추가**
- `keyword_mapping`에 `customer_service: depth` 추가 (깊이 방향)

**Task 4: `derive_user` 프롬프트 템플릿 추가**
- `prompts.yaml`에 `derive_user_lateral_customer_service` 또는 `derive_user_depth_customer_service` 신규 추가
- 고객센터 특화 chain 생성 지시

**Task 5: 단위 테스트**
- 패턴 매칭 테스트: "고객센터 전화번호", "AS 접수 방법" 등이 `customer_service` 카테고리로 분류되는지
- H2 가이드라인 테스트: step1/2/3 sections가 올바르게 선택되는지

**Task 6: 체류시간 극대화 설계 검증**
- Depth 0→1→2 자연스러운 흐름 검증
- 검색 의도(Informational→Navigational→Transactional) 매칭 검증
- 체인 연결(bridge_logic) 품질 검증

### Out of Scope

- 실제 키워드 10개 자동 발행 (Phase 24 Task 3에서 별도 진행)
- AI 챗봇/CRM 시스템 실제 구현
- 특정 기업 고객센터 리뷰/비교 (일반적 설계)

---

## Constraints

- 기존 테스트(291개) 깨지지 않게 수정
- CTA 문구는 Phase 17 확정안("더 알아보기 →") 준수
- 기존 카테고리(travel/stock/etc)에 영향 없는 증분 변경
- personas.yaml (Phase 24)과 충돌 없이 설계

---

## Risks

| 위험 | 완화 방안 |
|------|-----------|
| "고객센터" 패턴이 기존 "etc"와 겹침 | patterns를 구체적으로 설정 (고객센터, 고객지원, helpdesk, AS, 상담 명시) |
| Depth 2에서 AI 콘텐츠가 얕아질 수 있음 | grounding: true 유지 + Naver 검색으로 최신 트렌드 반영 |
| 업종별 차이가 너무 커서 범용 설계 어려움 | "일반 고객센터" 중심 설계, 업종별 차이는 키워드 수준에서 분리 |

---

## Success Criteria

1. `customer_service` 카테고리가 prompts.yaml에 올바르게 추가됨
2. "고객센터 전화번호" 같은 키워드가 `customer_service`로 분류됨
3. Depth 0→1→2 H2 가이드라인이 자연스러운 프로그레션을 보임
4. 기존 테스트 291개 전부 통과 (회귀 없음)
5. 신규 테스트 5개 이상 추가 통과
6. derive_user 프롬프트가 고객센터 체인을 올바르게 생성함
