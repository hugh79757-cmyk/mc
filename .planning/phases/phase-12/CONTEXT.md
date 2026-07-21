# Phase 12: mc R2 업로더 분리 — mde2 의존성 제거

## Problem Statement

`mc` 프로젝트는 R2 이미지 업로드 시 `mde2/app/services/r2_uploader.py`를 직접 import하여 사용한다:
```python
# chain_publisher_core.py:23
from app.services.r2_uploader import get_r2_config, upload_all_images, HUGO_R2_DOMAINS
```

이 의존성 때문에:
1. mde2를 수정하면 mc에도 영향이 간다 (버그 재발 위험)
2. mde2의 `upload_all_images()`는 `thumbnail.webp`만 찾지만, mc는 `thumb_pexels_*.webp` 형태로 저장한다 → 파일명 불일치로 R2 업로드 누락
3. mde2와 mc의 개발 주기가 다름 — 분리 필요

## Root Cause

| 노드 | 파일 | 문제 |
|---|---|---|
| **원인** | `mc/image/thumbnail.py:336` | `thumb_{slug}_{source}_{id}.webp` 형태로 저장 |
| **現象** | `mde2/r2_uploader.py:113` | `thumbnail.webp`만 찾아서 R2 업로드 → 파일명 불일치로 스킵 |
| **잔여** | `mde2/r2_uploader.py` | mc 수정 시 mde2도 같이 바뀜 — 의존성 비용 |

## Constraints

- mde2는 현재 기능이 정상 동작하므로 절대 변경하지 말 것
- mc의 R2 업로더는 mde2의 `upload_all_images()` 로직을 기반으로 하되, `thumb_*` 패턴을 지원해야 함
- `HUGO_R2_DOMAINS` 매핑은 mde2에 유지하고, mc는 자체 매핑을 갖거나 mde2의 상수만 재사용

## Scope

- `mde2/app/services/r2_uploader.py` → 원복 (git checkout)
- `mc/image/r2_uploader.py` → 새로 생성 (mde2 로직 복사 + `thumb_*` 지원)
- `mc/chain_publisher_core.py` → import 경로 변경 (mde2 → mc 자체 모듈)

## Out of Scope

- img.techpawz.com 도메인 라우팅 (Cloudflare 설정 문제)
- 썸네일 생성 로직 변경 (`image/thumbnail.py`)
- mde2의 다른 기능 수정
