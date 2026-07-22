# Phase 14 — CLI 단일 진입점 `mc <keyword>`

## Objective
Phase 1–13에서 `chain_publisher.py`로 개별 스텝 호출. Phase 14는 `mc <키워드>` 하나로 draft→image→publish를 순차 실행하는 단일 진입점 CLI를 구축한다.

## Requirements (from user)

### R1: `mc <keyword>` — Full pipeline
- `mc 업클로젯` 실행 시 derive → draft → image → publish 순차 실행
- `chain_publisher.py --seed "업클로젯" --publish` 호출과 동등한 결과
- 체인 ID를 stdout에 출력 (후속 `--resume`용)

### R2: Pipeline stage flags
- `mc <keyword> --dry-run` — derive only (체인 생성 + 미리보기, DB 쓰기 X)
- `mc <keyword> --draft` — derive + draft (이미지 생성 X)
- `mc <keyword> --image` / `mc <keyword> --skip-publish` — derive + draft + image
- `mc <keyword> --publish` — full pipeline (기본값, `--publish` 생략 가능)
- `mc --help` — 사용법 출력

### R3: Resume (`--resume`)
- `mc --chain-id N --resume` — 기존 체인의 중단 지점부터 재개
- 상태 감지: `seed`만 있음 → draft, `draft_md`는 있음 → image, `image_meta.content_image_path`는 있음 → publish, `published_url` 있음 → 완료
- 중복 발행 방지: 완료된 스텝은 건너뛰고 미완료 스텝만 실행

### R4: Single-site override (`--site`)
- `mc 업클로젯 --site rotcha` — 오버라이드된 사이트에만 발행
- `--site` 미지정 시 3개 사이트 모두 발행 (기존 `chain_blog_mapping` 사용)

### R5: Background execution (`--background`)
- `mc 업클로젯 --background` — nohup + `&` 방식으로 백그라운드 실행
- 로그 파일에 PID 기록, tail 가능

### R6: Logging
- 로그 파일: `logs/mc-cli-YYYYMMDD.log`
- 각 스텝 (derive/draft/image/publish) 시작/종료/실패 타임스탬프
- 실행 완료 시 cost summary (LLM 토큰 추정치, 이미지 생성 수, 발행된 URL 목록)
- stderr와 stdout 모두 로그에 기록

## Existing Pipeline Context
- `chain_publisher.py` (855 lines): `run_chain()`, `generate_chain_images()`, `publish_chain()`, `inject_cards_chain()` — Phase 14는 이 함수들을 import/subprocess로 호출
- `chain_publisher_core.py`: `PublisherCore.publish_post()` — Hugo 발행
- `chain_db.py`: `get_chain()`, `get_chain_posts()`, `get_chain_posts_ordered()` — 체인 상태 조회
- `chain_deriver.py`: `derive_chain()` — 시드→체인 생성
- `chain_drafter.py`: `draft_chain()` — 초안 작성

## Key Design Decisions (PLAN에서 확정)

1. **신규 파일**: `cli/mc.py` — wrapper 전용. `chain_publisher.py`를 import하여 함수 재사용.
2. **`chain_publisher.py` 수정 금지** — 130/130 pytest 보존. Phase 14는 신규 파일만 생성.
3. **진입점**: `pip install -e .`의 `console_scripts` (`mc = cli.mc:main`) — `which mc` 감지 가능.
4. **Resume 로직**: `chain_db`의 체인/포스트 상태를 읽어 미완료 스텝 판별. `chain_publisher.py`의 함수에 적절한 인자 전달.
5. **Logging**: Python `logging` 모듈 사용. 파일 핸들러 + stdout 핸들러 동시 출력.
6. **Background**: `subprocess.Popen` 또는 `os.fork()` → stdout/stderr를 로그 파일로 리디렉션.

## Constraints
- `chain_publisher.py` 수정 금지 (기존 130/130 pytest 보존)
- 19/27 guard (`_NON_INTENDED_CHAINS`) 미건드림
- FM preservation (`_ensure_featureimage`) 미건드림
- W1~W6, Phase 11–13 code 미건드림
- `_extract_clean_body()` 수정 금지
- 새 파일만 생성 (예시: `cli/mc.py`)
- pytest baseline: **130/130 유지 + N개 신규** (N은 PLAN.md에서 명시)

## Test Baseline
- pytest 130/130 (현재: 112 기존 + 18 Phase 13 신규)
- 목표: **130 + N/130 + N** (신규 테스트는 `cli/mc.py` 단위 테스트)
- 신규 테스트: mocking `chain_publisher.py` 함수, resume 로직, logging, CLI 인자 파싱
- 라이브 3/3 (Phase 13: 업클로젯 체인 #66)

## Phase 14.1 (이월, Phase 14 구현 후)
- cron/launchd 스케줄링 (`mc --schedule`)
- Dashboard CLI (`mc status`, `mc list`, `mc stats`)
- `audit_chain.py` 통합 (`mc audit --chain-id N`)
