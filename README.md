# mc (Manual Chain)

하나의 시드 키워드 → 3개 블로그 체인(연관 포스트) 자동 생성 → 발행 파이프라인.

## Quick Start

```bash
# 전체 파이프라인 (derive → draft → image → publish)
python chain_publisher.py --seed "츄니토리" --publish

# 단계별 실행
python chain_publisher.py --seed "츄니토리" --dry-run        # derive only
python chain_publisher.py --seed "츄니토리" --draft          # derive + draft
python chain_publisher.py --seed "츄니토리" --image          # derive + draft + image

# 기존 체인 발행/카드 주입
python chain_publisher.py --chain-id 5 --publish             # 역순 발행 (Step 3→2→1)
python chain_publisher.py --chain-id 5 --publish-interactive  # 1개씩 승인
python chain_publisher.py --chain-id 5 --publish-manual      # 수동 발행
python chain_publisher.py --chain-id 5 --inject              # 카드 주입만

# 블로그 지정
python chain_publisher.py --seed "츄니토리" \
  --blog-step1 65_informationhot \
  --blog-step2 infohot \
  --blog-step3 techpawz \
  --publish

# 스케줄러
python chain_publisher.py --chain-id 5 --schedule --launchd --hour 9 --minute 0
python chain_publisher.py --chain-id 5 --schedule --cron "0 9 * * *"
python chain_publisher.py --schedule-list
python chain_publisher.py --schedule-remove --chain-id 5
```

## Architecture

```
chain_deriver.py        키워드 분류 → 방향 라우팅 → AI 주제 도출
chain_drafter.py        체인 컨텍스트 주입 → AI 초안 작성
chain_publisher.py      CLI 진입점 (모든 플래그 통합)
chain_publisher_core.py Hugo/Blogger/Manual 발행 분기
chain_card_injector.py  하단/중간 카드 정규화 삽입
chain_db.py             SQLite 스키마 + CRUD 마이그레이션
mc_paths.py             5000 import + config 로더
image/                  Pollinations.ai flux 이미지 생성
scheduler/              cron + launchd 스케줄러
```

## 체인 방향

| 방향 | 적합 키워드 | 흐름 |
|------|-----------|------|
| depth (깊이) | IT/기술/이슈/시사 | 기초 → 분석 → 전문 |
| swallow (역방향) | 쇼핑/소비/브랜드 | 구매 → 절약 → 재테크 |
| lateral (횡방향) | 여행/지역/맛집 | 정보 → 비교 → 비즈니스 |

## Blogger OAuth2 설정

1. Google Cloud Console → 프로젝트 생성
2. Blogger API 활성화
3. OAuth2 클라이언트 ID (Desktop app) 발급
4. credentials.json → `config/blogger_credentials.json`
5. 최초 실행 시 브라우저 인증

## 의존성

```
# 필수
pip install pyyaml markdown

# Blogger API
pip install google-api-python-client google-auth-oauthlib google-auth

# 스케줄러 (선택)
pip install python-crontab pyperclip
```
