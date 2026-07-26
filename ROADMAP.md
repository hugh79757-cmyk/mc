# ROADMAP.md — mc (Manual Chain)

## 완료된 Phase

| Phase | 상태 | 설명 |
|-------|------|------|
| Phase 1–10 | ✅ 완료 | 기반 구축, 체인 파이프라인, 광고, 이미지, 배포 |
| Phase 11 W1–W6 | ✅ 완료 | Hugo 발행 안정화, Blowfish 테마, CTA 개선, 광고 커버리지, 이미지 마커 보장 |
| Phase 12 | ✅ 완료 | R2 업로더 분리, 썸네일 업로드 버그 수정 |
| Phase 13 | ✅ 완료 | 마크다운 정제 + 테이블 보호 + CJK Bold 버그 + contextual image + search providers |
| Phase 14 | ✅ 완료 | CLI `mc <keyword>` — argparse/resume/background+logging/console_scripts |
| Phase 14 P1 | ✅ 완료 | `_ensure_frontmatter()` 정식 구현 + cli/mc.py patch 제거 |
| Phase 14 P2 | ✅ 완료 | 고아 content_image_path 백필 15/15 |
| R2 이미지 수정 | ✅ 완료 | published_md 컬럼 + card injection R2 보존 + techpawz 버킷 분기 |
| W3 카드 재설계 | ✅ 완료 | 3단계 카드 + Naver API 외부링크 + 내용분담 + 이미지 프롬프트 + BS4 제거 |
| Phase 15 hotfix | ✅ 완료 | card URL 마이그레이션 — 26건 informationhot.kr → issue.techpawz.com |
| Phase 21 | ✅ 완료 | 이미지 파이프라인 최적화 + Smoke Test — 썸네일 재사용(R2 1회 업로드), sleep 제거+지수 백오프, 병렬화(3워커), 발행 후 smoke test(5개 테스트) |

## 현황

- **pytest:** 251/251 ✅ (Phase 21: +5 smoke test)
- **라이브:** 3/3 카드 주입 + 배포 (#74, #50, #28 2/3)
- **이미지 파이프라인:** 썸네일 재사용 + 병렬화 + 백오프 리트라이 (Phase 21 적용)
- **카드 URL:** issue.techpawz.com 마이그레이션 완료 (26건)
- **작업 트리:** 깨끗함 (untracked만)

## 차기 Phase

| Phase | 상태 | 설명 |
|-------|------|------|
| Phase 17 | ○ 계획 | CTA 시나리오 설계 — 카테고리별 행동유발 문구·강도·배치 + 릭 방지 설계 |

## 잔존 이월

| 작업 | 우선순위 | 비고 |
|------|---------|------|
| Phase 14.1: cron/launchd + dashboard + audit | 별도 milestone | 공수 큼, 무인 스케줄 자동발행 |
| (a) 43건 고아 content_image_path | 별도 milestone | 신규 발행 W6 게이트로 차단, 기존은 재발행 전까지 이미지 없음 |
| slug 고유화 + 비의도 체인 자동 감지 | P2 | |
| P3 Blowfish CSS 복구 | P3 | 라이브 3/3 기능 정상, CSS 미세 복구 영역 |
| Chain #28 rotcha 복구 | 대표 결정 | ````json` 제거 후 재발행 |
