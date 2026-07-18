# Phase 3 Summary: 역순 발행 + 카드 주입 + 스케줄러

## What's Being Built

Phase 3 takes the drafted posts (from Phase 2) and publishes them to real websites in reverse order (Step 3 → 2 → 1), then injects cross-link cards between them.

## Deliverables (8 tasks, 3 waves)

| # | Task | File(s) | Type |
|---|------|---------|------|
| 3-1 | DB 스키마 확장 | `chain_db.py` | 수정 |
| 3-2 | Config 발행 설정 | `config/chain_config.yaml` | 수정 |
| 3-3 | Blogger API 클라이언트 | `shared/publishers/blogger_client.py` | 신규 |
| 3-4 | Publisher Core | `chain_publisher_core.py` | 신규 |
| 3-5 | Card Injector | `chain_card_injector.py` | 신규 |
| 3-6 | Scheduler 패키지 | `scheduler/*.py` (4 files) | 신규 |
| 3-7 | CLI 확장 | `chain_publisher.py` | 수정 |
| 3-8 | README 업데이트 | `README.md` | 수정 |

## Key Features

- **역순 발행**: Step 3→2→1 순서로 Hugo/Blogger/Manual 3가지 모드
- **카드 주입**: 하단 Next 카드 (필수) + 중간 관련 카드 (H2≥3개 조건부) — CTA 블로그별 동적
- **스케줄러**: macOS launchd / Linux cron 자동 발행
- **사용자 설정**: --blog-step1/2/3 강제 지정, --publish-interactive 1개씩 승인

## Verification

8개 검증 기준 (CONTEXT.md 참조), 필수: `--publish-manual` → `--publish` Hugo → `--publish` Blogger → `--inject` → `--schedule`
