---
date: 2026-07-22
type: fix
status: resolved
---

# R2 썸네일 업로드 버그 수정 + mc 업로더 분리

## What
1. `mde2/app/services/r2_uploader.py`의 `upload_all_images()`가 `thumbnail.webp`만 찾아 `thumb_pexels_*.webp`, `thumb_unsplash_*.webp` 패턴 파일을 R2에 업로드하지 못하는 버그 수정
2. Phase 12 실행: mc가 mde2 없이 자체 R2 업로드를 수행하도록 분리
3. 클라우드이모션 키워드로 3개 사이트 발행 (rotcha/informationhot/techpawz)

## Why
- `mc/image/thumbnail.py`는 `thumb_{slug}_{source}_{id}.webp` 형태로 저장
- `mde2/r2_uploader.py`는 `thumbnail.webp`만 검색 → 파일명 불일치로 R2 업로드 누락
- `img.techpawz.com` 도메인이 R2를 향하지 않아 404 발생 (Cloudflare 라우팅 미설정)

## Files changed
- `mc/image/r2_uploader.py` — 새로 생성 (mde2 로직 기반 + thumb_* 지원)
- `mc/chain_publisher_core.py` — import를 `app.services.r2_uploader` → `image.r2_uploader`로 변경
- `mde2/app/services/r2_uploader.py` — 원복 (git checkout)
- `.planning/phases/phase-12/PLAN.md` — Phase 12 플랜 생성
- `.planning/phases/phase-12/CONTEXT.md` — Phase 12 컨텍스트
- `.planning/ROADMAP.md` — Phase 12 추가

## How
1. mde2 원복: `git checkout HEAD -- app/services/r2_uploader.py`
2. mc 자체 업로더 생성: mde2 로직 복사 + `assets/thumb_*` 패턴 검색 추가
3. import 경로 변경: `chain_publisher_core.py`에서 mde2 의존성 제거
4. E2E 테스트: `upload_all_images()` → R2 업로드 성공 확인

## Verification
- `python -c "from image.r2_uploader import upload_all_images; print('OK')"` → 통과
- R2 업로드 테스트: `head_object`로 파일 존재 확인 → 통과
- `chain_publisher_core.py` import 변경 후 `python -c "from chain_publisher_core import *"` → 통과
- 클라우드이모션 발행: 3개 사이트 HTTP 200 확인

## 잔존 이슈
- `img.techpawz.com` 도메인 라우팅 미설정 (Cloudflare Dashboard에서 Pages 연결 필요)
- rotcha `featureimage` 누락 시 발행 실패 → 검증 로직 완화 필요
