# CONTEXT.md — Phase 29: 블로그 형식/외형 검증

**Phase:** 29
**Created:** 2026-07-28
**Mode:** verification

## Objective

카테고리 11종 체계에서 생성되는 블로그 포스트의 **형식/외형**이 설계대로 동작하는지 검증한다. 콘텐츠 품질이 아닌, 구조적/시각적 완결성을 확인한다.

## Background

- Phase 27에서 콘텐츠 품질(글자수, H2 구조, 릭 방어) 검증 완료
- Phase 28에서 product 카테고리 추가 완료 (11종 체계)
- 남은 검증 영역: **발행 후 실제 블로그에 나타나는 형식/외형**
- 현재 `_verify_before_deploy()`가 소스/산출물 기본 검증을 하나, 다음 항목은 미검증:
  - 썸네일이 featureimage로 정상 주입되는가
  - 카드가 설계대로 본문에 2개(mid + bottom) 삽입되는가
  - 3개 블로그(rotcha → issue.techpawz → techpawz)가 유기적으로 연결되는가
  - Hugo 테마(Blowfish)가 형식을 정상 렌더링하는가

## 검증 대상

| 검증 항목 | 기대 결과 | 검증 방법 |
|-----------|-----------|-----------|
| 썸네일(featureimage) | frontmatter에 R2 URL로 설정 | 발행 후 index.md featureimage 필드 확인 |
| 썸네일 렌더링 | Hugo HTML에서 og:image + 본문 상단에 표시 | public/posts/slug/index.html 확인 |
| 카드 삽입 (하단) | 마지막 H2 섹션 이후에 카드 HTML 존재 | index.md에서 카드 HTML 패턴 검색 |
| 카드 삽입 (중간) | H2>=3일 때 2번째 H2 직후 카드 존재 | index.md에서 중간 카드 위치 확인 |
| 카드 수 | 포스트당 최대 2개 (mid + bottom) | 카드 HTML 카운트 |
| 블로그 간 연결 | Depth 0→1→2 순서대로 다음 글 URL 카드 존재 | 각 포스트의 카드 URL이 다음 단계 블로그를 가리키는지 |
| H2 구조 | step_sections에 정의된 H2가 본문에 존재 | index.md에서 H2 라인 추출 + 비교 |
| frontmatter 완결성 | draft=false, slug, date, featureimage, images 모두 존재 | index.md 파싱 |
| Hugo 빌드 | warnings/errors 없이 빌드 성공 | hugo --gc --minify 출력 |
| 라이브 접근 | 배포 후 HTTP 200 | curl -I |

## 수정 대상 파일

이번 Phase는 **코드 수정이 없는 검증 전용**이다. 검증 결과에 따라 향후 Phase에서 수정이 필요할 수 있다.

| 파일 | 역할 | 수정 여부 |
|------|------|-----------|
| 검증 스크립트 (신규) | E2E 형식 검증 자동화 | ✅ 생성 |
| config/prompts.yaml | 검증 대상 (read-only) | ❌ |

## 참고 자료

- `chain_card_injector.py` — 카드 삽입 로직 (3단계 체계, inject_bottom_card, inject_mid_card)
- `chain_publisher_core.py` — 발행 코어 (_verify_before_deploy, featureimage 설정)
- `chain_publisher.py` — inject_cards_chain() 전체 흐름
- `chain_db.py` — chain_posts 테이블 (card_injected, published_url, published_md)
- `.planning/phase-16/` — 이전 형식 검증 기록 (STEP-2, STEP-3)
- `config/chain_config.yaml` — blog 매핑, 카드 CTA 설정

## 제약 조건

- 기존 코드 수정 금지 (read-only 검증)
- 검증은 자동화 가능한 스크립트로 수행
- 라이브 사이트에 영향을 주는 작업 금지 (dry-run 또는 로컬 Hugo 빌드)
- 검증 결과는 `.planning/phase-29/VERIFICATION.md`에 기록
