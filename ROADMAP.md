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

- **pytest:** 171/171 ✅ (130 기존 + 35 Phase 14 W1-W3 + 6 P1 frontmatter)
- **라이브:** AI프롬프트마켓 체인 #71 — rotcha/infohot/techpawz 3/3 정상
- **patch 제거:** cli/mc.py — W4 임시 patch 완전 제거
- **작업 트리:** 깨끗함 (untracked만)

## 다음 Phase (예정)

### P1 (즉시)

| Phase | 작업 | 테스트 목표 | 상태 |
|-------|------|------------|------|
| 14.1 | ~~P1 인계: frontmatter patch 정식화~~ | ~~168/168~~ **171/171** | ✅ 완료 |
| 13.1 | 이미지 캐시 대시보드 + 사이트별 이미지 전략 분기 (이월) | — | 대기 |

### Phase 14.1 상세 (Planning)

| 작업 | 내용 | 상태 |
|------|------|------|
| W1 | `_ensure_frontmatter()` 정식 구현 | ✅ 완료 |
| W2 | `cli/mc.py` patch 제거 | ✅ 완료 |
| W3 | frontmatter 보존 케이스 테스트 6개 추가 | ✅ 완료 (171/171) |
| W4 | Chain #72 --draft 라이브 회귀 확인 | ✅ 완료 |

### 잔여 작업

| 작업 | 우선순위 |
|------|---------|
| (a) Phase 14.1: cron/launchd + dashboard + audit 통합 | P1 (P1 인계 후) |
| (b) 고아 NULL content_image_path 37건 백필 | P2 |
| (c) slug 고유화 + 비의도 체인 자동 감지 | P2 |
| (d) Blowfish CSS 복구 | P3 |