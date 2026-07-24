# Phase 18 Plan — Measurement Infrastructure Verification

## Phase Redesignation
**Phase 18은 신규 구현이 아닌, 기존 mc 시스템의 발행 품질·측정 인프라를 조사·검증하는 phase로 재지정함.**

## Objectives
1. 기존 발행 인프라(AdSense, Analytics, Naver)의 실제 적용 상태를 조사하고 Evidence로 정리
2. 실제 발행된 게시물을 추출하여 category/site/depth 분포를 정량화
3. 발행 후 5분 내 통과 가능한 Pass/Fail 품질 체크리스트 초안을 확정

## Hard Constraints
- **코드 수정 금지** — mc 코드베이스의 production 코드를 수정하지 않음
- **신규 발행 금지** — 새 글을 발행하거나 기존 글을 수정·재발행하지 않음
- **미커밋 변경 사항 건드리지 않음** — git working tree의 uncommitted changes를 수정하지 않음
- **연구 보고서만 생성 가능** — `.planning/phase-18/` 디렉토리에 RESEARCH.md, PLAN.md만 생성

## Task Breakdown

### T1: 측정 인프라 조사 (완료)
- [x] AdSense Publisher ID / Slot ID 조사 (3개 사이트 템플릿 + 라이브 HTML)
- [x] Google Analytics (gtag) 조사 (3개 사이트)
- [x] Naver Search API 조사 (mc 코드베이스 내 사용 위치)
- [x] Naver Webmaster/Analytics 연동 조사
- [x] 자체 성능 측정 인프라 조사 (DB 테이블, 컬럼, 코드 로직)

**Output:** `.planning/phase-18/RESEARCH.md` 섹션 1

### T2: 실제 발행 게시물 추출 (완료)
- [x] DB 스키마 확인 (`chain_posts`, `publish_log`, `loop_chains`, `chains`)
- [x] 발행 게시물 수 집계 (`status='published'`)
- [x] Depth별 분포 집계
- [x] Category별 분포 집계
- [x] 최근 발행 체인 샘플링 (chain_id 76, 75, 74 등)

**Output:** `.planning/phase-18/RESEARCH.md` 섹션 2

### T3: 5-Minute 품질 체크리스트 초안 작성 (완료)
- [x] AdSense Publisher ID 정합성 체크
- [x] 광고 슬롯 ID 정합성 체크
- [x] Depth별 URL 패턴 정합성 체크
- [x] Category assign 정합성 체크
- [x] 필수 메타데이터 존재 체크
- [x] 플레이스홀더 잔존 여부 체크
- [x] gtag/AdSense 스크립트 중복 로드 체크

**Output:** `.planning/phase-18/RESEARCH.md` 섹션 3

### T4: 검증 루프 실행 (다음 단계)
- [ ] 품질 체크리스트를 실제 최신 발행 게시물 3건에 적용하여 Pass/Fail 확인
- [ ] AdSense 스크립트 정합성을 실제 게시물 HTML 3건에서 수동 검증
- [ ] gtag ID가 3개 사이트 모두 일관되게 삽입되어 있는지 확인
- [ ] DB의 `publish_log` 와 `chain_posts` 의 published_url 일치 여부 샘플링

## Verification Protocol

| 검증 항목 | 방법 | 기준 |
|---|---|---|
| AdSense ID 정합성 | 실제 게시물 3건 HTML grep | 사이트별 단일 ID 일치 |
| 광고 슬롯 ID | 실제 게시물 3건 HTML grep | 사이트별 고정 슬롯 사용 |
| gtag 삽입 | 실제 게시물 3건 HTML grep | `<head>` 내 1세트만 존재 |
| Depth-사이트 매핑 | DB 쿼리 + URL 패턴 매칭 | depth 0→rotcha, 1→informationhot, 2→techpawz |
| 카테고리 분포 | DB group by 쿼리 | 상위 카테고리 편중도 확인 |
| 메타데이터 완전성 | DB 쿼리 (published_url, published_at, hugo_file_path) | NULL 비율 0% |

## Success Criteria
- [ ] RESEARCH.md 에 3개 태스크의 findings가 evidence와 함께 기록됨
- [ ] 5-Minute 품질 체크리스트가 7개 항목으로 구성됨
- [ ] 검증 루프 결과가 체크리스트에 PASS/FAIL로 기록됨
- [ ] 코드 수정·신규 발행·미커밋 변경이 없음이 확인됨

## Next Actions
1. T4 검증 루프 실행 (실제 게시물 3건 샘플링)
2. 체크리스트 결과를 RESEARCH.md 에 보완
3. Phase 18 완료 후 다음 Phase(구현 또는 추가 검증)로 이동

## 잔존 위험
- DB lock 오류로 일부 집계 쿼리가 반복적으로 실패함. 필요 시 SQLite 연결 재시도 로직 또는 백업 DB 복사본 사용 검토
- AdSense 실제 렌더링은 브라우저 Live test가 필요함. 현재는 템플릿/HTML 존재만 확인
- Naver Webmaster Tools 설정은 Cloudflare Pages/Custom domain 레벨에서 이루어질 수 있어 코드베이스에서 확인 불가
