# RESEARCH.md — Phase 16 실전 검증 파이프라인

**생성일:** 2026-07-23  
**조사자:** orchestrator (direct codebase analysis)

---

## 1. 현재 시스템 상태

| 항목 | 값 |
|------|-----|
| pytest | 231/231 ✅ |
| 총 체인 | 73개 |
| 라이브 사이트 | 3/3 (rotcha.kr, issue.techpawz.com, techpawz.com) |
| DB 칼럼 | `chain_posts` — content_image_path 없음, content_image 없음 |
| 이미지 파이프라인 | Phase 13 종료, R2 라이브 |

## 2. 검증 대상 핵심 코드

### chain_publisher_core.py
- `generate_chain_images()` — 줄 370~409: 썸네일 생성 + content_image_path 체크
- R2 업로드: `r2_uploader.py`의 `upload_all_images()` 사용
- Hugo publish: `_publish_hugo_post()` — 줄 720~800

### chain_card_injector.py
- `inject_cards_into_draft()` — 줄 398~: 카드 3단계 삽입
- Depth 2: 외부 링크 카드 (`build_external_link_card()`, 줄 240)
- `find_external_links()` — 줄 118: Naver API + fallback
- `_naver_fallback()` — 줄 189: Naver 검색 fallback
- 외부 링크 우선순위: place.naver.com > 인증 플랫폼 > Naver 검색

### config/prompts.yaml
- `draft_system` (줄 167): 현재 Phase 15에서 개선된 프롬프트 — 5000 스타일 적용, ABSOLUTE BAN, ANTI-HALLUCINATION
- `draft_user` (줄 255): 블로그별 역할 분담 명시 — rotcha(기초) / issue.techpawz(응용) / techpawz(심화)
- 각 depth별 H2 구조 고정 (Step 1/2/3 각 4개 H2)

## 3. 알려진 이슈

| 이슈 | 현황 |
|------|------|
| 43건 고아 이미지 | 신규 발행 W6 게이트로 차단 중. DB 컬럼명 content_image_path 없음 (content_image_path는 오래전 제거된 필드) |
| W6 게이트 | 현재 코드에서 content_image_path 참조는 줄 390에서 `_image_meta.get("content_image_path")`로 존재 |
| 테스트 커버리지 | 231/231 — 카드/이미지/프롬프트 관련 테스트 포함 |

## 4. 검증 키워드

**키워드:** 하이바이풀빌라  
**예상 체인 방향:** travel/lateral (숙소/여행 키워드)
