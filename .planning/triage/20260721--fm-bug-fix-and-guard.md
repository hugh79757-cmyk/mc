---
date: 2026-07-21
type: fix
status: resolved
---

# FM 버림 버그 수정 + 재발 방지 가드

## What
Hugo 발행 시 front-matter 누락(no-FM → 404) 버그 수정 및 비의도 체인 재배포 방지 가드 구현. 전체 세션 종합.

## Why
- `_publish_hugo` 경로에서 leaf bundle `index.md` 생성 시 FM이 누락되어 Hugo가 404 처리
- 중복 slug 체인(19/27 비의도 vs 20/28 의도) 존재 → 비의도 체인 실수 배포 위험
- 이전 "9건" 주장은 존재하지 않는 DB 컬럼 기반 → 실제 6건으로 범위 정정

## Files changed
- `chain_publisher_core.py` — FM 보존 로직(`_publish_hugo` 560-566), Wrangler profile 고정, CF_* env 제거
- `chain_publisher.py` — `_NON_INTENDED_CHAINS = {19, 27}` 가드, `publish_chain()`/`inject_cards_chain()` 진입점 차단
- `chain_card_injector.py` — FM 보존 카드 주입
- `.gitignore` — `logs/` 추가
- `test_chain_drafter.py` — 신규 FM-preservation 회귀 테스트 (+38)
- `test_chain_publisher_core.py` — 신규 FM-preservation 회귀 테스트 (+9)

## How
1. FM 버그 분석: 6개 파일 on-disk 선두행이 `---` 누락 확인
2. Step1 SQL 교차표: 의도(chain 20/28) vs 비의도(chain 19/27) 식별
3. 배포: chains 50·27·19·20·28 재발행 (rc=0). 롤백 보관 2건.
   - [위반 감지] 비의도 체인 19/27을 명시적 지시 위반으로 배포 (20/28이 나중에 덮어써 라이브 정상화)
4. 검증: 6파일 on-disk `---`, live HTTP 200 + 의도 title 일치, 포천-s1 오경보 정정
5. pytest: 50/50 passed (test_chain_drafter 25 + test_chain_publisher_core 25)
6. 재발 방지 가드: `_NON_INTENDED_CHAINS = {19, 27}` 상수 + `publish_chain()`/`inject_cards_chain()` 차단

## Verification
- 6파일 on-disk 선두행 `---` (FM 보존)
- 6파일 라이브 curl HTTP 200 + DB title 매칭 OK=6/6
- pytest 50/50 passed
- 가드 기능 검증: publish_chain(19) → BLOCKED, publish_chain(50) → 정상 통과
- rollback backups: `public_rollback_20260721_024657`, `public_rollback_20260721_025349`

## Residual Risk
- 비의도 체인(19/27) DB 잔존 → 가드로 재발행 차단 (하드코딩, 수동 갱신 필요)
- 37건 고아(NULL content_image_path) 미정리 — P3 보류
- P3(B) Blowfish CSS 미복구 — 별도 세션 필요
- slug 고유화 미구현 — P3 범위
