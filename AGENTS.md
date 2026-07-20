# AGENTS.md — mc (Manual Chain)

## Persona
- 사용자에게는 항상 존대말을 사용합니다.
- 간결하고 직접적으로 답변합니다.

## Project Overview
**mc (Manual Chain)** — 키워드 하나 → 3개 도메인(rotcha/informationhot/techpawz)에 걸쳐 점점 깊어지는 블로그 포스트 3개를 자동 생성·발행하는 시스템.

## Tech Stack
- Python (체인 로직, AI 초안, 이미지, 차트)
- Hugo (정적 사이트, Blowfish 테마)
- Cloudflare Pages (배포, R2 이미지 저장소)
- SQLite (chain DB)
- OpenAI GPT (초안 생성)
- Blogger API (일부 사이트 발행)

## Core Paths
| Path | Description |
|------|-------------|
| `chain_publisher_core.py` | 발행 코어 (Hugo/Blogger/Manual 분기) |
| `chain_drafter.py` | AI 초안 생성 모듈 |
| `chain_deriver.py` | 키워드 분류 + 체인 방향 파생 |
| `chain_db.py` | SQLite 체인 DB |
| `config/chain_config.yaml` | 사이트·발행 설정 |
| `config/prompts.yaml` | AI 프롬프트 템플릿 |
| `image/` | 이미지 파이프라인 (thumbnail, injector, pollinations, krea) |
| `pillow_chart.py` | 차트 이미지 렌더러 |

## Hugo Sites
| Site | Path | CF Project |
|------|------|------------|
| rotcha | `/Users/twinssn/Projects/rotcha-blog` | rotcha-blog |
| informationhot | `/Users/twinssn/Projects/informationhot-hugo` | informationhot-hugo |
| techpawz | `/Users/twinssn/Projects/techpawz-hugo` | techpawz-hugo |

## Dev Commands
```bash
# 체인 발행
python chain_publisher.py --seed "키워드"
python chain_publisher.py --chain-id N --draft
python chain_publisher.py --chain-id N --image
python chain_publisher.py --chain-id N --publish

# Hugo 빌드 + 배포 (rotcha 예시)
cd /Users/twinssn/Projects/rotcha-blog && hugo --gc --minify
unset CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID CF_DNS_TOKEN CLOUDFLARE_WORKERS_AI_API_TOKEN R2_ENDPOINT
wrangler pages deploy ./public --project-name rotcha-blog
```

## Conventions
- 프롬프트 릭 방지: `_strip_prompt_leak()` (chain_drafter.py)
- 미해소 플레이스홀더 제거: `_sanitize_markdown_body()` (chain_publisher_core.py)
- 배포 시 `CLOUDFLARE_API_TOKEN` 등 env를 unset 후 hugh79757 프로필로 실행
- `.planning/` 디렉토리에 phase별 PLAN, RESEARCH, CONTEXT 관리
