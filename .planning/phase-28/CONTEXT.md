# CONTEXT.md — Phase 28: 상품(electronics/product) 카테고리 추가

**Phase:** 28
**Created:** 2026-07-28
**Mode:** feature

## Objective

"갤럭시 폴드8 울트라 자급제" 같은 전자기기/상품 키워드로 글 작성이 가능하도록 새 카테고리를 추가한다.

## Background

- 현재 10개 카테고리 체계: travel, real_estate, automotive, stock, customer_service, gov_finance, shopping_brand, golf_course, medicine, etc
- "갤럭시 폴드8 울트라 자급제" 같은 키워드는 현재 `etc` 카테고리로 분류됨
- `etc`는 depth 방향 + generic 프롬프트를 사용하므로, 상품 특화 콘텐츠(스펙 비교, 구매 가이드, 가격 분석)가 생성되지 않음
- 새 카테고리 `product`(또는 `electronics`)를 추가하여 상품 키워드 전용 프롬프트와 흐름을 제공

## 사용자 예시 키워드

- "갤럭시 폴드8 울트라 자급제"
- "아이폰 16 프로 가격"
- "갤럭시 S25 울트라 자급제"
- "에어팟 프로 3세대"
- "맥북 프로 M4"
- "PS5 가격"
- "닌텐도 스위치2"

## 검증 대상

| 검증 항목 | 기대 결과 |
|-----------|-----------|
| classify_keyword("갤럭시 폴드8 울트라 자급제") | `product` 반환 |
| classify_keyword("아이폰 16 프로 가격") | `product` 반환 |
| classify_keyword("에어팟 프로 3세대") | `product` 반환 |
| resolve_chain_type("갤럭시 폴드8 울트라 자급제") | `lateral` (비교/선택형) |
| derive_user_lateral_product 프롬프트 존재 | prompts.yaml에 정의됨 |
| s1→s2→s3 흐름 | 스펙 정보 → 비교 분석 → 구매 가이드 |

## 수정 대상 파일

| 파일 | 수정 내용 |
|------|-----------|
| `config/prompts.yaml` | `keyword_categories.product` 패턴 + `derive_user_lateral_product` 프롬프트 + step_sections |
| `config/chain_config.yaml` | `keyword_mapping.product: lateral` |
| `chain_deriver.py` | 해당 없음 (config 기반 자동 인식) |
| `mc_paths.py` | 해당 없음 (config 기반 자동 인식) |

## 참고 자료

- `config/prompts.yaml` — 기존 카테고리 프롬프트 패턴 (travel, real_estate 등 참조)
- `config/chain_config.yaml` — keyword_mapping, chain_blog_mapping
- `chain_deriver.py` — derive 로직 (config 기반, 코드 수정 불필요)
- `mc_paths.py` — classify_keyword() (config 기반, 코드 수정 불필요)
- Phase 24~25 커밋 기록 — 기존 카테고리 추가 프로세스 참조

## 제약 조건

- 기존 카테고리 동작 변경 금지 (additive, non-destructive)
- `etc` 카테고리 fallback 동작 유지
- classify_keyword()의 priority 시스템 활용 (product의 priority를 설정하여 기존 카테고리와 충돌 방지)
- step_sections는 상품 특화: 스펙 정보 → 비교 분석 → 구매 가이드 흐름
