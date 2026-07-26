# RESEARCH.md — Phase 23: 인프라 안정화 + 자동 스케줄링

**Phase:** 23  
**Date:** 2026-07-26  
**Status:** Research Complete

---

## 1. 기존 스케줄링 관련 코드 현황

### scheduler/ 패키지 (이미 구현됨)

| 파일 | 상태 | 설명 |
|------|------|------|
| `scheduler/__init__.py` | ✅ 완료 | CronManager, LaunchdManager, task_runner export |
| `scheduler/cron_manager.py` | ✅ 완료 | Linux/macOS cron 관리 (python-crontab + fallback) |
| `scheduler/launchd_manager.py` | ✅ 완료 | macOS launchd plist 관리 (StartCalendarInterval) |
| `scheduler/task_runner.py` | ✅ 완료 | 스케줄러에서 호출되는 래퍼 (`python task_runner.py <chain_id>`) |

**주요 기능:**
- Cron: `add_task(command, cron_expr, description)`, `remove_task(command)`, `list_tasks()`
- Launchd: `add_task(chain_id, hour=9, minute=0)`, `remove_task(label)`, `list_tasks()`
- task_runner: `run_chain_publish(chain_id)` — chain_publisher.publish_chain() 호출

**갭:**
- `mc` CLI에 `schedule` 서브커맨드 없음 (직접 스케줄러 모듈 import 필요)
- 키워드 큐 시스템 없음 (무엇을 발행할지 자동 결정 로직 부재)
- 스케줄 설정 후 로그 로테이션, 알림, 상태 확인 CLI 없음

---

## 2. Phase 14.1 이월 내용 (ROADMAP.md)

| 작업 | 상태 | 비고 |
|------|------|------|
| cron/launchd + dashboard + audit | 별도 milestone | 공수 큼, 무인 스케줄 자동발행 |
| (a) 43건 고아 content_image_path | 별도 milestone | 신규 발행 W6 게이트로 차단, 기존은 재발행 전까지 이미지 없음 |
| slug 고유화 + 비의도 체인 자동 감지 | P2 | - |
| P3 Blowfish CSS 복구 | P3 | 라이브 3/3 기능 정상, CSS 미세 복구 영역 |
| Chain #28 rotcha 복구 | 대표 결정 | ````json` 제거 후 재발행 |

**결론:** 스케줄링은 이미 구현됐으나 CLI 래핑과 키워드 큐가 없어 실사용 불가. Phase 23에서 `mc schedule` 서브커맨드 + 키워드 큐로 완성 필요.

---

## 3. 현재 키워드 선정 방식

**검색 결과:** `grep -rn "keyword\|topic\|seed" mc/ --include="*.py" | grep -i "select\|pick\|choose\|queue"` → **결과 없음**

**현재 상태:**
- 키워드는 사용자가 `mc "키워드"`로 직접 입력
- 큐 시스템, 우선순위, 자동 선택 로직 **전무**
- `--search` 플래그로 검색 컨텍스트 on/off만 가능

**필요 구현:**
- `keyword_queue` 테이블 (DB) 또는 `config/keyword_queue.yaml`
- `mc queue add/list/next` 서브커맨드
- `mc auto`가 `queue next`로 키워드를 꺼내 `run_chain()` 실행

---

## 4. 현재 에러 처리 및 알림

**검색 결과:** `grep -rn "notify\|alert\|slack\|webhook\|email\|telegram" mc/ --include="*.py"` → **결과 없음**

**현재 상태:**
- 에러 발생 시 `print()` / `logger.error()` / `traceback.print_exc()`만 수행
- 외부 알림 채널(Slack, Discord, 이메일, Telegram) **구현 없음**
- `mc auto` 실패 시 재시도 로직 없음 (다음 스케줄 실행까지 대기)

**필요 구현:**
- `config/notify.yaml` — 채널별 설정 (활성화 여부, URL)
- `mc/notify.py` — `send_alert(title, detail, level)` 통합 함수
- 에러 발생 시 try/except로 감싸 알림 전송 (알림 실패해도 발행 중단 안 함)

---

## 5. 현재 실행 환경

| 항목 | 값 |
|------|-----|
| OS | macOS (Darwin 25.5.0, arm64) |
| Python | 3.14.5 |
| launchctl | `/Users/twinssn/.local/bin/launchctl` ✅ |
| crontab | blogdex용 1개 등록됨 (0 1 * * * daily_sync) |
| 스케줄러 | launchd 권장 (macOS 표준) |

---

## 6. .env 구조

```
# 민감 정보 제외 후 구조만 파악
R2_ENDPOINT_URL=https://...
R2_BUCKET_NAME=md-editor
R2_PUBLIC_URL=https://img.aikorea24.kr
# + Cloudflare, OpenAI, Naver API 키 등
```

**구조:** 단일 `.env` 파일, 섹션 구분은 주석으로만 처리. 사이트별 override 복잡성 유발 우려로 현재 구조 유지 + 주석 섹션 구분 권장.

---

## 7. 현재 chain DB 이력

- **DB 경로:** `/Users/twinssn/Projects/5000/data/mc_chains.db`
- **총 체인 수:** 132개
- **최근 상태:** `derived` (derivation만 완료), `image_generated`, `completed` 등
- **주요 키워드:** 영덕파나크, 테스트키워드 반복

---

## 8. 결론 및 Phase 23 설계 방향

| 영역 | 현재 상태 | Phase 23 목표 |
|------|----------|---------------|
| 스케줄러 | ✅ 구현됨 (모듈만) | `mc schedule` CLI 래핑 + launchd/cron 자동 등록 |
| 키워드 큐 | ❌ 없음 | DB 테이블 + `mc queue` 서브커맨드 + `mc auto` |
| 알림 | ❌ 없음 | `config/notify.yaml` + `mc/notify.py` + 에러 시 자동 전송 |
| 상태 확인 | ❌ 없음 | `mc status` — 최근 7일 요약 출력 |
| 로그 로테이션 | ❌ 없음 | `logs/mc-auto-YYYY-MM-DD.log` 일자별 파일 |

**핵심 설계 원칙:**
1. `mc auto` 실패해도 시스템 안 깨짐 — 큐에서 꺼낸 후 실패 시 `status=failed` 기록, 다음 실행 때 skip
2. 스케줄러 없어도 수동 동일 동작 — `mc auto`는 스케줄러 없이도 직접 실행 가능
3. 알림 실패해도 발행 중단 안 함 — `notify`는 항상 try/except로 감싸고 로그만 남김