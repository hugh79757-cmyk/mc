# Phase 41: 산출물 계약서 정의 (Output Contract)

**Milestone:** M3 — 9점 품질 달성
**Goal:** 블로그별 산출물 계약서를 YAML로 정의하고, 발행 전 계약 충족 여부를 자동 검증하는 인프라 구축

## Why

현재 파이프라인은 콘텐츠 생성 후 검증하지 않음. "테라 토마토 맥주" 수동 개선으로9/10 달성 가능함을 확인했으나, 자동화 없이는 일관된 품질 보장 불가. 계약서(contract) 정의 → 자동 검증 → 게이트 통합이 품질 달성의 기반.

## Plan

### W1: contracts/ 디렉토리 + 사이트별 YAML 정의

- `contracts/rotcha.yaml` — rotcha.kr (Step1, 정보성) 필수 섹션: [제품 개요, 핵심 특징, 선택 기준]. 금지: [가격 단정, 과대광고]. 제목 패턴: `[키워드]란? | 특징과 선택 가이드`
- `contracts/issue_techpawz.yaml` — issue.techpawz (Step2, 비교/검증) 필수 섹션: [A vs B 비교표, 검증 항목, 주의점]. 금지: [단일 제품 찬양, 편향 비교]. 제목 패턴: `[키워드] A vs B | 어떤 걸 고를까`
- `contracts/techpawz.yaml` — techpawz (Step3, 구매/실전) 필수 섹션: [구매 체크리스트, 가격·재고 확인, 최종 추천]. 금지: [미확인 최저가 단정, 검증 없는 리뷰]. 제목 패턴: `[키워드] 구매 가이드 | 가격 비교와 최종 추천`

### W2: contract_loader.py

- YAML 로드 + 검증 (jsonschema 대신 관대한 YAML 파싱)
- 필수 필드 존재 확인
- 금지 패턴 컴파일
- `load_contract(site: str) -> Contract` 인터페이스

### W3: quality_gate.py — 계약 기반 검증

- `validate_contract(post_md: str, contract: Contract) -> GateResult`
- 섹션 존재 검사 (H2/H3 기반)
- 금지 패턴 매칭 검사
- 제목 패턴 매칭 검사
- `GateResult(passed bool, violations: list[Violation])`

### W4: pytest 통과

- 계약 로드 테스트 (3 사이트 YAML)
- 검증 엔진 테스트 (통과/위반 케이스)
- pytest 전체 녹색 유지

## Dependencies

- 기존 `config/schema.yaml` 관례 준수
- 기존 `audit/audit_chain.py` 패턴 참고

## Risks

- YAML 계약서가 너무 엄격하면 기존 유효한 콘텐츠 거부 → 관대하게 시작, 점진적 강화
- 사이트별 계약서 차이가 미세하면 동일 계약으로 시작 후 분리
