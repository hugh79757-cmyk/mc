# STATE.md — mc (Manual Chain)

**Updated:** 2026-07-22
**Phase:** Phase 11 W1~W6 — 전체 완료
**Status:** ✅ 머지 완료

## Current Baseline

| 항목 | 값 |
|------|-----|
| pytest | **112/112** ✅ |
| 라이브 (리린샵 체인 #64) | **3/3** HTTP 200 + H2 + img ✅ |
| 작업 트리 | 깨끗함 (`git status --short` = untracked only) |
| 브랜치 | `main` (최신) |

## Phase 11 W6 완료 항목

### 스키마 검증 게이트 (`_validate_draft_schema`)
- `chain_drafter.py`에 함수 구현
- 검증 항목: H2 헤딩 ≥1, 이미지 마커 존재, frontmatter 필수 필드, image_keyword
- chart 마커(`<!--todo:chart-->`)는 image_keyword 검증 예외
- `chain_publisher.py`에서 draft 완료 후 호출

### image_keyword 자동 보강
- draft 단계에서 `image_keyword`가 비어 있으면 포스트 제목으로 fallback
- photo/chart 모두 대상 (chart는 썸네일 OG 태그용)
- LLM 재요청 없음 (이미 생성된 초안의 meta만 보강)

### 프롬프트 릭 필터 강화
- `_PROMPT_LEAK_RE`에 `**[...]**` 패턴 추가
- 정규식 이스케이프 오류 수정 (`r"\("` → 이스케이프)

### 테스트
- `TestValidateDraftSchema` 클래스 추가 (7개 메서드)
- 기존 `TestCLI::test_cli_entry_functions_exist` 제거 (중복 커버리지)
- 순 증감: +6 (106 → 112)

## 라이브 검증

| Step | Site | URL | HTTP | H2 | img |
|------|------|-----|------|----|-----|
| 1 | rotcha.kr | 리린샵-20260722-s1 | 200 ✅ | 1 ✅ | 2 ✅ |
| 2 | informationhot.kr | 리린샵-20260722-s2 | 200 ✅ | 3 ✅ | 1 ✅ |
| 3 | techpawz.com | 리린샵-20260722-s3 | 200 ✅ | 3 ✅ | 2 ✅ |

## Recent Commits

```
5b7267a fix(11-w6): chart fallback image_keyword auto-fill + prompt leak regex fix
b42f081 wip: Phase 11 W6 — image marker fix, button text fix, schema gate prep
8605e21 wip: Phase 12 완료 — mc R2 업로더 분리 + .continue-here.md handoff
e9c3431 fix(audit): read Hugo file frontmatter for featureimage check
9ce35f2 docs(state): add Phase 10 deliverables, W4 manual E2E procedure
```

## 인계 사항 (잔여 작업)

1. **W3 잔여**: 신규 발행 card_injector만 shortcode 적용. 기존 1,086건 HTML 제거는 이미 완료.
2. **고아 content_image_path 정리**: 37건 NULL content_image_path (image_meta에는 chart_data 있음). 백필 필요.
3. **slug 고유화/비의도 체인 감지**: 자동 감지 로직 부재. 중복 slug 방지 필요.
4. **Blowfish CSS 복구**: P3(B) 우선순위. CSS 누락으로 레이아웃 일부 깨짐.

## Resume Instructions

```bash
cd /Users/twinssn/projects2/mc

# pytest 확인
python -m pytest --tb=short -q

# 체인 발행 (예시)
python chain_publisher.py --seed "새키워드"
python chain_publisher.py --chain-id <id> --draft
python chain_publisher.py --chain-id <id> --image
python chain_publisher.py --chain-id <id> --publish

# 라이브 검증
curl -s -o /dev/null -w "%{http_code}" https://rotcha.kr/posts/<slug>/
curl -s -o /dev/null -w "%{http_code}" https://informationhot.kr/posts/<slug>/
curl -s -o /dev/null -w "%{http_code}" https://techpawz.com/<slug>/
```
