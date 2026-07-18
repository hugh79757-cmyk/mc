# Phase 3 Context: 역순 발행 + 카드 주입 + 스케줄러

## Phase Goal

3개 초안(Step 1/2/3)을 역순(Step 3→2→1)으로 실제 사이트에 발행하고, 발행된 URL을 다음 단계 글에 카드로 주입. Hugo + Blogger 양쪽 자동발행 지원. cron/launchd 스케줄러 포함.

## Current State (Phase 2 완료)

- `chain_deriver.py`, `chain_drafter.py`, `chain_publisher.py`, `chain_db.py`, `mc_paths.py` 구현 완료
- `image/` 패키지 (pollinations_client.py, prompt_builder.py, injector.py) 구현 완료
- `config/prompts.yaml`, `config/chain_config.yaml` 구성 완료
- `output/drafts/{chain_id}/`, `output/images/` 디렉토리 활성
- DB 스키마: chain_type, step, angle, draft_md, slug 등 Phase 2 컬럼 존재
- 테스트 체인: Chains #1~#7 (츄니토리, AI 트렌드 2026, 제주도 여행 패키지)

## Dependencies

- 5000 프로젝트 (`/Users/twinssn/Projects/5000`): `shared/publishers/hugo_writer.py` (공유), `shared.ai_writer`
- Hugo roots: `/Users/twinssn/Projects/rotcha-blog`, `informationhot-hugo`, `techpawz-hugo`
- Blogger blog IDs: 2.techpawz.com (5484205249958557854), 65.informationhot.kr (TBD)
- OAuth2 credentials 필요: `config/blogger_credentials.json`

## Key Design Decisions

### 결정 1: 발행 인프라 — 3종 모두 구현
- Hugo 자동발행 (techpawz.com, rotcha.kr, informationhot.kr)
- Blogger 자동발행 (2.techpawz.com, 65.informationhot.kr) — OAuth2 API
- 수동 발행 모드 — 초안 HTML 출력 + 클립보드 복사 + URL 수동 입력
- 체인 구성 사용자 설정 가능 (--blog-step1/2/3)

### 결정 2: 발행 자동화 수준 — 원클릭 + 설정 + 1개씩 승인
- 원클릭 전체 자동: --publish 시 3개 글 역순 자동 발행 + 카드 주입
- 설정 모드: config/chain_config.yaml에서 각 step별 블로그 지정
- 1개씩 승인 발행: --publish-interactive 시 각 step 발행 전 Enter 대기

### 결정 3: 카드 삽입 위치 정규화
- 하단 Next 카드: 모든 글 기본 삽입 (본문 마지막 H2 섹션 이후)
- 중간 관련 카드: H2가 3개 이상일 때 2번째 H2 직후 1개 삽입
- 상단: 카드 금지
- 삽입 위치는 코드로 정규화, AI가 임의 결정하지 않음

### 결정 4: CTA 문구 동적
- chain_config.yaml의 blog별 card_cta 블록에서 읽기
- 방향별(depth/swallow/lateral) + 블로그별 조합
- 빈 값 시 기본값 사용

## Verification Criteria

1. `--publish-manual`: HTML 파일 생성 + 클립보드 복사 + URL 입력 → DB 저장
2. `--publish` Hugo: techpawz에 글 발행 → 실제 URL 접속 → git push 확인
3. `--publish` Blogger: 2.techpawz.com에 글 발행 → 실제 URL 접속 (OAuth2 설정 후)
4. `--inject`: 발행된 체인에 카드 주입 → 본문에 카드 HTML 존재 확인
5. 카드 위치: 하단=마지막 H2 이후, 중간=2번째 H2 이후 (H2≥3)
6. CTA 문구: blog별 card_cta 값 반영 확인
7. `--schedule --launchd`: plist 생성 → launchctl load → 확인
8. 역순 발행: Step 3→2→1 순서 DB published_at 확인

## New Dependencies

```
google-api-python-client>=2.0
google-auth-oauthlib>=1.0
google-auth>=2.0
markdown>=3.4
pyperclip>=1.8
python-crontab>=2.7
```
