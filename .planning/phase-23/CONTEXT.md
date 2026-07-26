# CONTEXT.md — Phase 23: 인프라 안정화 + 자동 스케줄링

**Phase:** 23  
**Created:** 2026-07-26  
**Milestone:** mc를 수동 CLI에서 일 1회 자동 발행 시스템으로 전환  
**Mode:** execute (코드 착수)

---

## Objective

mc를 수동 CLI에서 일 1회 자동 발행 시스템으로 전환한다. 운영 중단 없이 안정적으로 동작하며, 문제 발생 시 자동 감지 + 알림한다.

---

## Background

### Phase 14 완료 (Phase 14.1 이월)
- `mc <keyword>` 단일 진입점 완성 (derive → draft → image → publish)
- `--dry-run`, `--draft`, `--image`, `--publish`, `--resume`, `--site`, `--background`, `--search` 플래그 지원
- logging: `logs/mc-cli-YYYYMMDD.log` (파일 + stdout 듀얼)

### Phase 14.1 이월 항목 (ROADMAP.md)
- cron/launchd + dashboard + audit → 별도 milestone
- 43건 고아 content_image_path 백필 → 별도 milestone
- slug 고유화 + 비의도 체인 자동 감지 → P2
- P3 Blowfish CSS 복구 → P3
- Chain #28 rotcha 복구 → 대표 결정

### 현재 스케줄러 상태
`scheduler/` 패키지에 이미 구현됨:
- `cron_manager.py` — python-crontab + fallback
- `launchd_manager.py` — macOS launchd plist (StartCalendarInterval)
- `task_runner.py` — 스케줄러에서 호출되는 래퍼 (`python task_runner.py <chain_id>`)

**갭:** `mc` CLI에 `schedule` 서브커맨드 없음 → 직접 모듈 import 필요

---

## Dependencies

### Upstream (완료)
- Phase 14: CLI 단일 진입점 (`mc <keyword>`), resume, logging, background
- Phase 21: 이미지 파이프라인 최적화 (썸네일 재사용, 병렬화, 백오프)
- Phase 22: 콘텐츠 품질 게이트 (글자수, CTA, SEO, 릭 방어)
- scheduler 패키지: 크론/런치디 관리 모듈

### Downstream (Phase 23 이후)
- Phase 24: 자동 재작성 루프 (품질 미달 시 retry with feedback)
- Phase 25: 키워드 큐 자동 보충 (트렌드/검색량 기반 추천)
- 대시보드 CLI (`mc status`, `mc list`, `mc stats`)

---

## Current State Summary

| 기능 | 현재 상태 | Phase 23 목표 |
|------|----------|---------------|
| 스케줄러 | 모듈만 존재 (CLI 없음) | `mc schedule setup/status/remove` |
| 키워드 큐 | 없음 | DB 테이블 + `mc queue add/list/next` + `mc auto` |
| 알림 | 없음 | `config/notify.yaml` + `mc/notify.py` (webhook) |
| 상태 확인 | 없음 | `mc status` (최근 7일 요약) |
| 로그 로테이션 | 단일 파일 | `logs/mc-auto-YYYY-MM-DD.log` |

---

## Scope

### In Scope (Phase 23)
1. **키워드 큐 시스템** — DB 테이블 `keyword_queue`, `mc queue` 서브커맨드, `mc auto` 실행
2. **스케줄러 설정** — `mc schedule setup --daily --hour 9` (launchd plist 생성/등록), `mc schedule status/remove`
3. **에러 알림 + 운영 모니터링** — `config/notify.yaml`, `mc/notify.py` (Slack/Discord webhook), `mc status` (최근 7일 요약)
4. **로그 로테이션** — `logs/mc-auto-YYYY-MM-DD.log` 일자별 분리

### Out of Scope (향후 Phase)
- 대시보드 HTML/웹 UI (Phase 24)
- 트렌드 기반 키워드 자동 추천 (Phase 25)
- 품질 미달 시 자동 재작성 루프 (Phase 24)
- 멀티 유저/권한 관리

---

## Constraints

- `chain_publisher.py`, `chain_publisher_core.py` 등 기존 파이프라인 코드 **수정 금지** — import만 사용
- 이미 통과 중인 테스트(251개) **깨지지 않게** 수정
- 알림 실패해도 발행 중단 안 함 — `notify`는 try/except로 감싸 로그만 남김
- `mc auto` 실패 시 큐에서 꺼낸 키워드 `status=failed` 기록, 다음 실행 때 skip
- 스케줄러 없어도 수동 실행 가능 — `mc auto`는 스케줄러 없이도 직접 실행 가능
- 로그 파일은 매일 자동 분리 (`mc-auto-YYYY-MM-DD.log`)

---

## Risks

| 위험 | 가능성 | 영향 | 완화 방안 |
|------|--------|------|-----------|
| launchd plist 권한/경로 문제 | Medium | High — 스케줄 미작동 | `launchctl load` 실패 시 에러 출력 + 수동 복구 가이드 |
| 키워드 큐 중복/경합 | Low | Medium — 동일 키워드 중복 발행 | DB unique constraint + `mc queue add` 중복 체크 |
| 알림 webhook 실패 시 발행 중단 | Low | High — 핵심 파이프라인 블록 | `notify` 함수 내 모든 예외 catch, 로그만 기록 |
| 스케줄러 중복 등록 | Low | Medium — 이중 발행 | `mc schedule setup` 시 기존 작업 제거 후 재등록 |
| 큐가 비어있는데 mc auto 실행 | Medium | Low — 정상 종료 | exit 0, 로그만 남김 |
| 로그 파일 용량 증가 | Low | Low — 디스크 부족 | 일자별 분리 + 30일 이상 자동 정리 옵션(향후) |

---

## Key Decisions

1. **알림 채널:** Webhook 우선 (Slack/Discord/Telegram 통합 가능) → 이메일은 Phase 24
2. **스케줄러:** macOS는 launchd 표준 사용, Linux는 cron fallback
3. **로그:** `logs/mc-auto-YYYY-MM-DD.log` 일자별 파일, 30일 보관(수동 정리)
4. **키워드 큐:** DB 테이블 (`keyword_queue`) — 트랜잭션 지원, 동시성 안전
5. **상태 출력:** `mc status`는 터미널 텍스트 (HTML 대시보드는 Phase 24)