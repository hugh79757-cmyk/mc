# ROADMAP.md — mc (Manual Chain)

## 완료된 Phase

| Phase | 상태 | 설명 |
|-------|------|------|
| Phase 1–10 | ✅ 완료 | 기반 구축, 체인 파이프라인, 광고, 이미지, 배포 |
| Phase 11 W1–W6 | ✅ 머지 완료 | Hugo 발행 안정화, Blowfish 테마 적용, CTA 개선, 광고 커버리지, 이미지 마커 보장 |
| Phase 12 | ✅ 머지 완료 | mc R2 업로더 분리, 썸네일 업로드 버그 수정 |
| Phase 13 | ✅ 머지 완료 | 마크다운 정제 + 테이블 보호 + CJK Bold 버그 수정 + contextual image + search providers |
| Phase 14 | ✅ 머지 완료 | CLI 단일 진입점 `mc <keyword>` — W1 argparse/W2 resume/W3 background+logging/W4 console_scripts |

## 현황

- **pytest:** 165/165 ✅ (130 기존 + 35 Phase 14 W1-W3)
- **라이브:** AI프롬프트마켓 체인 #71 — rotcha/infohot/techpawz 3/3 정상
- **작업 트리:** 깨끗함 (untracked만)

## 다음 Phase (예정)

### P1 (즉시)

| Phase | 작업 | 테스트 목표 | 상태 |
|-------|------|------------|------|
| 14.1 | P1 인계: frontmatter patch 정식화 — `_ensure_frontmatter()` 구현 + cli/mc.py patch 제거 + 2~3개 신규 테스트 + 라이브 재발행 회귀 확인 | 168/168 | 인계 대기 |
| 13.1 | 이미지 캐시 대시보드 + 사이트별 이미지 전략 분기 (이월) | — | 대기 |

### Phase 14.1 상세 (Planning)

| 작업 | 내용 |
|------|------|
| W1 | `chain_drafter.py`에 `_ensure_frontmatter(draft_md, meta)` 정식 구현 — FM 보존/생성 |
| W2 | `cli/mc.py`의 `patch("chain_drafter.draft_chain")` 제거, 정식 구현으로 위임 |
| W3 | frontmatter 보존 케이스 테스트 2~3개 추가 |
| W4 | 기존 draft 있는 체인 1건 `--publish` 재발행으로 라이브 회귀 확인 |

### 잔여 작업

| 작업 | 우선순위 |
|------|---------|
| (a) Phase 14.1: cron/launchd + dashboard + audit 통합 | P1 (P1 인계 후) |
| (b) 고아 NULL content_image_path 37건 백필 | P2 |
| (c) slug 고유화 + 비의도 체인 자동 감지 | P2 |
| (d) Blowfish CSS 복구 | P3 |