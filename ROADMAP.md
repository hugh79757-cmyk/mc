# ROADMAP.md — mc (Manual Chain)

## 완료된 Phase

| Phase | 상태 | 설명 |
|-------|------|------|
| Phase 1–10 | ✅ 완료 | 기반 구축, 체인 파이프라인, 광고, 이미지, 배포 |
| Phase 11 W1–W5 | ✅ 머지 완료 | Hugo 발행 안정화, Blowfish 테마 적용, CTA 개선, 광고 커버리지 |
| Phase 11 W6 | ✅ 머지 완료 | 이미지 마커 보장, 스키마 검증 게이트, image_keyword fallback |
| Phase 12 | ✅ 머지 완료 | mc R2 업로더 분리, 썸네일 업로드 버그 수정 |

## 현황

- **pytest:** 112/112 ✅
- **라이브:** 리린샵 체인 #64 — 3/3 사이트 정상
- **작업 트리:** 깨끗함

## 다음 Phase (예정)

### P1 (즉시)

| Phase | 작업 | 상태 |
|-------|------|------|
| — | (a) W3 잔여: 신규 발행 card_injector shortcode 적용 확인 | 대기 |
| — | (b) 고아 NULL content_image_path 37건 백필 | 대기 |

### P2 (중기)

| Phase | 작업 | 상태 |
|-------|------|------|
| — | (c) slug 고유화 + 비의도 체인 자동 감지 | 대기 |

### P3 (장기)

| Phase | 작업 | 상태 |
|-------|------|------|
| — | (d) Blowfish CSS 복구 | 대기 |
