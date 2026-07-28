# STATE.md — mc (Manual Chain)

**Updated:** 2026-07-28
**Phase:** Phase 26 리팩토링 계획 수립 + 카테고리 10종 체계 구축 + 파서 안정성 개선
**Status:** ✅ 309/309, 카테고리 10종 lateral prompt 완비, golf_course/medicine E2E 검증, 파서 BOM/텍스트 대응 강화

## Current Baseline

| 항목 | 값 |
|------|-----|
| pytest | **309/309** ✅ (기존 297 + 파서 안정성 테스트 12) |
| 브랜치 | `feat/keyword-category-template` |
| 카테고리 | 10종: travel, real_estate, automotive, stock, customer_service, gov_finance, shopping_brand, golf_course, medicine, etc |
| 라이브 | 3/3 R2 200 ✅ (rotcha/infohot/techpawz) |
| 파서 | `_parse_derivation()` BOM/제로폭/코드펜스/텍스트 전후 대응 강화 |

## 카테고리 체계 (10종)

| 카테고리 | 방향 | 분류 패턴 | E2E 검증 | 비고 |
|----------|------|-----------|----------|------|
| travel | lateral | 여행/코스/펜션/숙소/관광 | ✅ 기존 | --search ground |
| real_estate | depth | 아파트/부동산/분양/시세 | ✅ 기존 | |
| automotive | depth | 전기차/자동차/차량/SUV | ✅ 기존 | 검색 무효 (Naver 한계) |
| stock | depth | 주가/ETF/투자/배당 | ✅ 기존 | --search ground |
| customer_service | lateral | 고객센터/전화번호/상담/문의 | ✅ #234 | |
| gov_finance | lateral | 지원금/장려금/신청/세금 | ✅ #235 | |
| shopping_brand | lateral | 브랜드/쇼핑몰/골프웨어 | ✅ #236 | |
| golf_course | lateral | CC/골프장/컨트리클럽/라운딩 | ✅ #231 | priority: 10 |
| medicine | lateral | 정/캡슐/시럽/복용법/부작용 | ✅ #230 | 의료 안전 가드 포함 |
| etc | depth | fallback | ✅ | |

## 주요 변경 내역 (2026-07-24 이후)

### 카테고리 확장 (Phase 24~25)
- customer_service, gov_finance, shopping_brand, golf_course, medicine 신규 추가
- `config/prompts.yaml`에 카테고리별 lateral 프롬프트 + step_sections 추가
- `config/chain_config.yaml` keyword_mapping에 5종 추가
- golf_course priority: 10 (travel보다 높음 — "CC" 패턴이 travel 가로채기 방지)

### D9 게이트 확장
- Raw HTML 외부 링크 카드 중복 제거 (3 패턴: primary/secondary/fallback)
- dual-cta shortcode 중복 제거 로직 추가
- 테스트 5건 추가

### 중간 카드 삽입
- H2>=3일 때 2번째 H2 직후 + 하단 = 총 2개 카드 주입

### _parse_derivation 안정성 개선 (이 세션)
- BOM(\ufeff), 제로폭 문자(\u200b~\u200f) 자동 제거
- 코드펜스(```json`, ```) 대응
- JSON 앞뒤 텍스트 삽입 대응 (fallback: 첫 `[`~마지막 `]` 추출)
- dict 응답에서 인식된 키(chain/posts/articles/items)만 추출, topics 등 비인식 키는 빈 리스트 반환
- 단위 테스트 12건 추가 (BOM, 제로폭, 텍스트 전후, 코드펜스, dict 키 분리)

## 파일별 수정 이력 (최근 주요 커밋)

```
9d30dec fix: golf_course 분류가 travel에 가로채이던 우선순위 버그 수정
b268398 feat: medicine derive_user_lateral 프롬프트 추가 (의료 안전 가드 포함)
0d3389e feat: medicine 카테고리 골격 추가 (의약품·증상)
eed9707 feat: 카테고리 3종 신규 추가(gov_finance/shopping_brand/golf_course)
3ec065d feat: 중간 카드 삽입 구현 (H2>=3일 때 2번째 H2 직후 + 하단)
02dcece fix: chain_card_injector 중복 클래스 오염 제거 + 플랫폼 판정 순서 버그 수정
3b0ea43 feat: customer_service 카테고리 추가 + 카테고리 확장 구조 리팩토링
ad839a7 refactor: 외부 링크 카드 신호 기반 스코어링 전환 + 손상 라인 복구
40628e9 fix: 섬네일 실사 이미지 복구 + 오버레이 디자인 개선
```

## Phase 26 (리팩토링 계획)

`.planning/phase-26/`에 3-wave 리팩토링 계획 수립 완료:
- Wave 1: 공통 유틸리티 추출 (frontmatter_utils, url_utils, constants)
- Wave 2: 카드 주입 시스템 모듈화 (card_generator, html_renderer, link_finder)
- Wave 3: 파이프라인 아키텍처 + 설정 검증

## Resume Instructions

```bash
cd /Users/twinssn/projects2/mc

# pytest 확인
python -m pytest --tb=short -q

# 전체 카테고리 derive 테스트
for kw in "삼성전자서비스 고객센터" "근로장려금 신청자격" "골프웨어 브랜드 추천" "남서울CC 예약" "타이레놀정 복용법" "제주도 여행 코스" "청주 아파트 시세" "삼성전자 주가"; do
  python3 chain_deriver.py "$kw" 2>&1 | tail -5
done

# draft 생성 (golf_course 예시)
python3 chain_drafter.py 231

# 분석 스크립트
python3 /tmp/analyze_drafts.py <chain_id>

# Phase 26 리팩토링 착수
# .planning/phase-26/PLAN.md 참고

# Hugo 배포 (rotcha 예시)
cd /Users/twinssn/Projects/rotcha-blog && HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify && env -u CLOUDFLARE_API_TOKEN wrangler pages deploy ./public --project-name rotcha-blog
```

## 잔존 위험

1. **Phase 26 리팩토링 미착수** — 계획만 수립됨, 구현 시작 안 됨
2. **Persona 어조 설계 미착수** — site/depth별 tone 설정 필요
3. **Shortcode git 미추적** — rotcha/techpawz layouts/shortcodes/ UNTRACKED
4. **(a) 40건 고아 이미지** — 재발행 전까지 이미지 없음
5. **Automotive 검색 무효** — Naver에서 자동차 스펙 데이터 미제공
6. **Chain #28 rotcha 복구 미완** — ````json` 제거 후 재발행 필요
