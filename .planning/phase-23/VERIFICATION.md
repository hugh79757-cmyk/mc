# VERIFICATION.md — Phase 23: 인프라 안정화 + 자동 스케줄링

**Phase:** 23  
**Created:** 2026-07-26  
**Status:** Pending

---

## Verification Strategy

각 Task별 단위 테스트 + 통합 테스트 + 파이프라인 E2E 검증

---

## Task 1: 키워드 큐 시스템

### 1.1 단위 테스트: `mc/queue.py`

| 테스트 케이스 | 입력 | 기대 결과 |
|-------------|------|----------|
| `test_add_keyword_success` | `add_keyword("테스트", "travel", 3)` | `{"success": True, "keyword": "테스트", "status": "added"}` |
| `test_add_keyword_duplicate` | 같은 키워드 두 번 추가 | 두 번째: `{"success": False, "status": "duplicate", "existing_status": "pending"}` |
| `test_add_keyword_priority_order` | priority 1, 3, 5 순서로 추가 | `get_next_keyword()` → priority 5 반환 |
| `test_add_keyword_same_priority_fifo` | 같은 priority 3인 키워드 A, B 순서 추가 | `get_next_keyword()` → A 반환 (FIFO) |
| `test_get_next_keyword_empty` | 빈 큐 | `None` 반환 |
| `test_get_next_keyword_sets_processing` | pending 키워드 1개 | 반환 후 DB에서 status = "processing" |
| `test_mark_done` | `mark_done("키워드")` | status = "done", processed_at 기록 |
| `test_mark_failed` | `mark_failed("키워드", "에러 메시지")` | status = "failed", error_msg 기록 |
| `test_list_queue_filter` | `list_queue(status="pending")` | pending만 반환 |
| `test_list_queue_all` | `list_queue()` | 전체 반환 (priority DESC, created_at ASC) |
| `test_remove_keyword` | `remove_keyword("키워드")` | DB에서 삭제, `True` 반환 |
| `test_remove_nonexistent` | 존재하지 않는 키워드 제거 | `False` 반환 |

### 1.2 단위 테스트: `cli/mc.py` queue 서브커맨드

| 테스트 케이스 | 검증 내용 |
|-------------|----------|
| `test_queue_add` | `mc queue add "키워드" --category travel --priority 4` → DB에 추가, 출력 확인 |
| `test_queue_add_duplicate` | 중복 추가 시 warning 출력 |
| `test_queue_list` | `mc queue list` → 포맷된 테이블 출력 |
| `test_queue_list_filter` | `mc queue list --status pending` → pending만 출력 |
| `test_queue_next` | `mc queue next` → processing으로 변경 후 키워드 출력 |
| `test_queue_remove` | `mc queue remove "키워드"` → DB에서 삭제 확인 |

### 1.3 단위 테스트: `mc auto` (통합)

| 테스트 케이스 | 검증 내용 |
|-------------|----------|
| `test_auto_empty_queue` | 빈 큐에서 `mc auto` → "No pending keywords" 출력, exit 0 |
| `test_auto_success` | 큐에 키워드 1개 → `run_chain` mock → mark_done 호출 확인, exit 0 |
| `test_auto_failure` | `run_chain` 예외 발생 → mark_failed 호출, 알림 전송 시도 (mock), exit 1 |
| `test_auto_notify_on_failure` | 실패 시 `send_alert` 호출 확인 (mock) |
| `test_auto_notify_failure_silent` | `send_alert` 예외 발생해도 `mc auto` 중단 안 함 |

### 1.4 마이그레이션 검증

- [ ] `chain_db.init_db()` 실행 후 `keyword_queue` 테이블 존재 확인
- [ ] 인덱스 `idx_keyword_queue_status`, `idx_keyword_queue_priority` 생성 확인
- [ ] 기존 DB에서 마이그레이션 실행 시 에러 없음

---

## Task 2: 스케줄러 설정 + 로그 로테이션

### 2.1 단위 테스트: `scheduler/launchd_manager.py`

| 테스트 케이스 | 검증 내용 |
|-------------|----------|
| `test_add_auto_task_plist_content` | 생성된 plist에 Label, ProgramArguments, StartCalendarInterval, WorkingDirectory 올바름 |
| `test_add_auto_task_load` | `launchctl load` 호출 확인 (mock) |
| `test_remove_task` | `launchctl unload` + plist 파일 삭제 확인 |
| `test_list_tasks` | `~/Library/LaunchAgents/com.mc.publisher.*.plist` 패턴 매칭 확인 |

### 2.2 단위 테스트: `scheduler/cron_manager.py`

| 테스트 케이스 | 검증 내용 |
|-------------|----------|
| `test_add_auto_task` | crontab에 `cd /project && python -m cli.mc auto >> logs/mc-auto-...` 등록 확인 |
| `test_list_tasks_filter` | `# mc-scheduler` comment가 있는 작업만 반환 |
| `test_remove_task` | mc 작업만 제거, 다른 크론 작업 보존 |

### 2.3 단위 테스트: `cli/mc.py` schedule 서브커맨드

| 테스트 케이스 | 검증 내용 |
|-------------|----------|
| `test_schedule_setup_macos` | macOS에서 `mc schedule setup --daily --hour 9` → `LaunchdManager.add_auto_task` 호출 |
| `test_schedule_setup_linux` | Linux에서 `--no-launchd` → `CronManager.add_auto_task` 호출 |
| `test_schedule_status` | 등록된 작업 목록 출력 |
| `test_schedule_remove` | 모든 mc 스케줄 제거 |

### 2.4 로그 로테이션 검증 (통합)

```bash
# 수동 검증
mc "테스트키워드" --auto  # 또는 mc auto 직접 실행
# logs/ 디렉토리에 mc-auto-YYYY-MM-DD.log 생성 확인
# 다음 날 실행 시 별도 파일 생성 확인
```

| 검증 항목 | 기대 결과 |
|----------|----------|
| `mc auto` 실행 시 로그 파일명 | `mc-auto-YYYY-MM-DD.log` (오늘 날짜) |
| 날짜 변경 후 실행 | 새로운 날짜 파일 생성 (기존 파일 보존) |
| 로그 내용 | `[mc] Starting chain...`, `Cost Summary` 등 포함 |

---

## Task 3: 에러 알림 + 상태 확인

### 3.1 단위 테스트: `mc/notify.py`

| 테스트 케이스 | 검증 내용 |
|-------------|----------|
| `test_send_alert_disabled` | `enabled: false` → `False` 반환, 호출 안 함 |
| `test_send_alert_level_filter` | `levels.error: false` → error 알림 `False` 반환 |
| `test_send_alert_success` | webhook URL 설정 + 200 응답 → `True` 반환, 로그 기록 |
| `test_send_alert_webhook_error` | 4xx/5xx 응답 → `False` 반환, warning 로그 |
| `test_send_alert_network_error` | 연결 실패/타임아웃 → `False` 반환, warning 로그 (예외 전파 안 함) |
| `test_send_alert_invalid_url` | URL 미설정 → `False` 반환 |
| `test_send_test_alert` | `send_test_alert()` → info 레벨로 전송 |

### 3.2 단위 테스트: `cli/mc.py` status 서브커맨드

| 테스트 케이스 | 검증 내용 |
|-------------|----------|
| `test_status_empty` | 체인 없음 → "No chains in last 7 days" |
| `test_status_counts` | 완료 3, 실패 1, 진행 2 → 카운트 정확 |
| `test_status_site_breakdown` | rotcha 2, techpawz 1, informationhot 1 → 사이트별 집계 |
| `test_status_smoke_test_rate` | smoke test 5개 중 4개 pass → "4/5 passed (80.0%)" |
| `test_status_json` | `--json` → 유효한 JSON 출력, 필드 모두 존재 |
| `test_status_custom_days` | `--days 30` → 최근 30일 조회 |

### 3.3 `chain_db.py` 추가 함수 검증

| 테스트 케이스 | 검증 내용 |
|-------------|----------|
| `test_get_chains_since` | 날짜 이후 체인만 반환, 내림차순 정렬 |

### 3.4 알림 통합 검증 (통합 테스트)

```bash
# config/notify.yaml에 테스트용 webhook URL 설정 (예: https://httpbin.org/post)
mc "테스트키워드" --dry-run  # 성공 케이스

# 실패 케이스 강제 생성
# chain_publisher.py에 의도적 에러 주입 후 mc auto 실행
# → 알림 전송 로그 확인 (send_alert 호출됨, 실패해도 mc auto는 계속 진행)
```

| 검증 항목 | 기대 결과 |
|----------|----------|
| `mc auto` 성공 시 | 알림 전송 안 함 (levels.info: false 기본값) |
| `mc auto` 실패 시 | error 알림 전송 시도 (send_alert 호출) |
| 알림 전송 실패 시 | mc auto 중단 안 함, warning 로그만 남김 |
| webhook 타임아웃 10초 | 10초 후 타임아웃 처리 |

---

## 전체 검증 (E2E)

### 3.5 파이프라인 E2E 검증

```bash
# 1. 큐에 키워드 추가
mc queue add "영덕파나크" --category travel --priority 3

# 2. 큐 확인
mc queue list
# 출력: 3 | pending      | 영덕파나크                   | travel

# 3. 다음 키워드 꺼내기
mc queue next
# 출력: [queue] Next: 영덕파나크 (id=1, priority=3)

# 4. 자동 발행 실행 (dry-run으로 검증)
mc auto --dry-run
# 또는
mc "영덕파나크" --dry-run

# 5. 실제 자동 발행 (큐 비워짐)
mc auto
# 로그 확인: logs/mc-auto-YYYY-MM-DD.log

# 6. 상태 확인
mc status
# 출력:
#   Total chains:   1
#   ✅ Completed:    1
#   ❌ Failed:       0
#   Site breakdown:
#     rotcha.kr: 1
#     techpawz.com: 1
#     informationhot.kr: 1
#   Smoke test: 3/3 passed (100.0%)

# 7. 스케줄 등록 (실제로는 cron/launchd 등록)
mc schedule setup --daily --hour 9
mc schedule status

# 8. 알림 테스트 (config/notify.yaml에 webhook URL 설정 후)
mc auto --fail-test  # 또는 의도적 실패 유도
# webhook 수신 확인
```

### 3.6 회귀 테스트 — 기존 기능 영향 없음

```bash
# 기존 테스트 스위트 전체 통과
python -m pytest -q
# 251 + Phase 23 신규 테스트 모두 통과

# 기존 CLI 플로우 정상 동작
mc "테스트키워드" --dry-run
mc "테스트키워드" --draft
mc "테스트키워드" --image
mc "테스트키워드" --publish

# resume 정상 동작
mc --chain-id 1 --resume

# background 실행
mc "테스트키워드" --background
```

---

## Test Count Summary

| Task | 단위 테스트 | 통합/E2E 테스트 | 예상 신규 테스트 수 |
|------|-----------|----------------|-------------------|
| Task 1 | 12 (queue) + 6 (CLI) + 4 (auto) + 1 (migration) = 23 | 1 (E2E 파이프라인) | 24 |
| Task 2 | 4 (launchd) + 3 (cron) + 4 (CLI) = 11 | 1 (로그 로테이션) | 12 |
| Task 3 | 7 (notify) + 6 (status) + 1 (DB) = 14 | 1 (알림 통합) | 15 |
| **Total** | **48** | **3** | **51** |

**예상 최종 테스트 수:** 251 (기존) + 51 = **302+**

---

## Verification Commands

```bash
# 1. 전체 테스트 스위트
python -m pytest -q
# 302+ passed 확인

# 2. Task 1 테스트만
python -m pytest test_mc_queue.py -v
python -m pytest test_cli_mc.py -k "queue or auto" -v

# 3. Task 2 테스트만
python -m pytest test_scheduler.py -v
python -m pytest test_cli_mc.py -k "schedule" -v

# 4. Task 3 테스트만
python -m pytest test_notify.py -v
python -m pytest test_cli_mc.py -k "status" -v

# 5. E2E 파이프라인 검증
mc queue add "테스트키워드" --category travel
mc queue list
mc auto --dry-run
mc status --json

# 6. 스케줄러 등록 확인 (실제 등록은 주의)
mc schedule setup --daily --hour 9
mc schedule status
mc schedule remove

# 7. 알림 테스트 (webhook URL 설정 후)
mc auto  # 실패 케이스 유도 시 알림 전송 확인

# 8. 로그 로테이션 확인
ls -la logs/mc-auto-*.log

# 9. 기존 기능 회귀 확인
python -m pytest test_chain_publisher_core.py -q
python -m pytest test_chain_drafter.py -q
```

---

## Acceptance Criteria (Definition of Done)

### Task 1 완료 조건
- [ ] `keyword_queue` 테이블 마이그레이션 성공
- [ ] `mc queue add/list/next/remove` 모두 동작
- [ ] `mc auto` 빈 큐 → exit 0, 키워드 있음 → run_chain 실행 → done/failed 기록
- [ ] 중복 키워드 add 시 warning, 중복 아님 → 정상 추가
- [ ] 실패 시 `mark_failed` + 알림 전송 시도 (실패해도 중단 안 함)
- [ ] 단위 테스트 23개 + E2E 1개 통과

### Task 2 완료 조건
- [ ] `mc schedule setup --daily --hour 9` → launchd plist 생성 + load 성공 (macOS)
- [ ] `mc schedule setup --no-launchd` → cron 등록 (Linux)
- [ ] `mc schedule status` → 등록된 스케줄 출력
- [ ] `mc schedule remove` → 스케줄 제거
- [ ] 로그 파일이 `logs/mc-auto-YYYY-MM-DD.log` 일자별 분리 저장
- [ ] 단위 테스트 11개 + 로그 로테이션 1개 통과

### Task 3 완료 조건
- [ ] `config/notify.yaml` 생성, webhook URL 설정 가능
- [ ] `mc/notify.py` `send_alert()` — Slack/Discord webhook 전송 동작
- [ ] 알림 실패 시 예외 전파 안 하고 로그만 기록
- [ ] `mc auto` 실패 시 자동 알림 전송
- [ ] `mc status` 최근 7일 요약 출력 (체인 수, 완료/실패, 사이트별, smoke test 통과율)
- [ ] `mc status --json` JSON 출력
- [ ] 단위 테스트 14개 + 통합 1개 통과

### 전체
- [ ] pytest 전체 **302+ passed**
- [ ] `git diff chain_publisher.py chain_publisher_core.py` → 0 changes
- [ ] `mc auto --dry-run` E2E 흐름 검증 완료
- [ ] 커밋 및 푸시 완료