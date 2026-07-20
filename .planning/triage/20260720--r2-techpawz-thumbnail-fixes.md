---
date: 2026-07-20
type: fix
status: resolved
---

# R2 도메인·썸네일·발행 sanitization 종합 수정

## What
- `img.rotcha.kr`·`img.informationhot.kr`이 이미지가 실제로 업로드된 `md-editor` 대신 `hotissue-images` 버킷을 가리키도록 커스텀 도메인 재연결
- `img.techpawz.com` 도메인을 다시 `techpawz-images` 버킷으로 복원하고, `hotissue-images`에 저장된 `images/techpawz/` 10개와 `wp-content` 이미지들을 서버 사이드 copy로 `techpawz-images`에 복사
- 발행 코드(`chain_publisher_core.py`) 본문 sanitization 2건 추가: `featureimage: ""` stray 라인 제거, malformed table dash line 정리
- `image/thumbnail.py` 썸네일 중복 프리픽스(`thumb_thumb_`) 버그 수정

## Why
- `R2_BUCKET_NAME` 쉘 env가 `hotissue-images`로 오버라이드되어 mc 발행이 새 이미지를 `hotissue-images`에 업로드하고 있었으나, `img.rotcha.kr`·`img.informationhot.kr` 커스텀 도메인은 여전히 `md-editor` 버킷에 연결되어 있었음 → 404
- `img.techpawz.com`은 기존 `techpawz-images`(워드프레스 구 `wp-content/` 포함)에서 `hotissue-images`로 옮겼다가 구 이미지 소실 확인 후 원래 버킷으로 복원
- DB draft_md에 `featureimage: ""`가 남아 발행시 본문으로 유출되는 문제
- GPT 산출 malformed table(`-|--|`)을 발행 sanitization이 걸러내지 못하던 문제

## Files changed
- `/Users/twinssn/projects2/mc/chain_publisher_core.py` — 본문 sanitization 2건 패치
- `/Users/twinssn/projects2/mc/image/thumbnail.py` — `thumb_` 프리픽스 중복 방지
- `/Users/twinssn/projects2/mc/audit_posts.py` — 전수검사 스크립트 신규 작성

## How
1. `wrangler r2 bucket domain remove` → `add`로 `img.rotcha.kr`·`img.informationhot.kr`을 `md-editor`에서 `hotissue-images`로 이동
2. `hotissue-images`에 있는 `images/techpawz/` 10개 + 구 포스트 544개 이미지 보존을 위해 `techpawz-images`에 서버 사이드 copy 완료
3. `img.techpawz.com` 커스텀 도메인을 다시 `techpawz-images`로 복원 (총 1040개+ 이미지)
4. `chain_publisher_core.py`의 `_rest_body` 할당 직후 `featureimage:\s*["']*\s*["']$` 정규식 sanitization 삽입
5. `_sanitize_markdown_body()`에 malformed table 구분선 제거 정규식 추가
6. `image/thumbnail.py add_text_overlay()`에서 `safe_slug`의 선행 `thumb_`를 strip 후 재부여하도록 수정

## Verification
- `img.rotcha.kr/images/rotcha/…/thumb_…jpg` → 200 OK 확인
- `img.informationhot.kr/images/informationhot/…/thumb_…jpg` → 200 OK 확인
- `img.techpawz.com/wp-content/uploads/2025/12/4.webp` → 200 OK 확인
- 체인 #15 재발행 후 `informationhot.kr/posts/배재고등학교야구-20260719-s2/` 본문에서 `featureimage: ""` 및 `-|--|` 라인 제거 확인
- 3개 Hugo 사이트 wrangler pages deploy 완료
