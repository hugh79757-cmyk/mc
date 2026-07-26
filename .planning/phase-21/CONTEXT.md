# CONTEXT.md — Phase 21: 이미지 병목 해결 + CLI 기본값 수정 + Smoke Test

**Phase:** 21
**Created:** 2026-07-26
**Goal:** `mc "키워드"` 한 줄로, 플래그 없이, 60초 이내에 3개 사이트 발행 완료 + URL 자동 검증

---

## Constraints

1. **새 기능 추가 금지.** 기존 코드만 개선한다.
2. **각 태스크 완료 시 pytest로 회귀 확인 (246/246 유지).**
3. **추측 금지.** 코드를 읽고, 시간을 측정하고, 로그를 남겨라.

---

## Task A: 이미지 파이프라인 병목 해결 (목표: 182s → 60s 미만)

### A-1: Thumbnail 재사용
- **현재:** Content image (`img_gen()`)와 Thumbnail (`img_thumb()`)이 각각 별도 API 호출로 Unsplash/Pexels에서 사진 다운로드
- **해결:** Content image를 thumbnail으로 재사용. 별도 API 검색/다운로드 제거. Download된 content image에 Pillow로 text overlay만 추가.
- **파일:** `chain_publisher.py` `generate_chain_images()`, `image/thumbnail.py`

### A-2: R2 업로드 병합
- **현재:** Content image와 thumbnail을 각각 R2에 별도 업로드 (2회 PUT/post)
- **해결:** Content image 업로드 후 thumbnail은 로컬에서 text overlay 추가 후 재업로드하거나, content image 업로드 시 thumbnail도 같은 파일로 key만 다르게 처리
- **파일:** `chain_publisher.py` `generate_chain_images()`

### A-3: Sleep 제거
- **현재:** `time.sleep(15)` 고정 대기 (post 간 15초, 총 45초)
- **해결:** Unsplash/Pexels API rate limit (50/시간, 200/시간)에 걸리지 않으므로 제거. 필요시 retry with backoff로 대체.
- **파일:** `chain_publisher.py` line 316-318

### A-4: 병렬화
- **현재:** 3개 포스트 이미지 생성 직렬 처리
- **해결:** `concurrent.futures.ThreadPoolExecutor`로 병렬 처리 (3개 포스트 독립적)
- **파일:** `chain_publisher.py` `generate_chain_images()`

---

## Task B: CLI 기본 publish_mode 수정

### B-1: 현재 상태 확인
- `cli/mc.py` `_run_full()` line 140-142: 이미 `publish_mode = "auto"` 기본값
- `mc "키워드"` (플래그 없음) → publish_mode="auto" → 전체 파이프라인 실행

### B-2: Deploy 누락 확인
- `run_chain()` line 762-765: `publish_chain()` + `inject_cards_chain()` 호출
- `_deploy_blogs_after_inject()`는 `inject_cards_chain()` 내부에서 호출됨 → 배포 포함
- 단, `_deploy_blogs_after_inject()`의 Hugo build + Wrangler deploy 성공 여부 검증 부재

### B-3: 확인 사항
- 기존 --dry-run, --draft, --image, --resume 플래그 유지
- pytest 246/246 확인
- `publish_mode` 기본값이 `None`이 아닌 `"auto"`인지 문서화

---

## Task C: 발행 후 Smoke Test

### C-1: smoke_test() 함수
- `_deploy_blogs_after_inject()` 완료 직후 실행
- 3개 URL을 DB/체인 결과에서 추출
- 각 URL에 HTTP GET (timeout=10s)
- 검증: HTTP 200, `<title>` 존재, `og:image` → R2 이미지 HTTP 200
- 결과를 DB `smoke_test_passed` 컬럼에 기록
- 실패 시 경고 로그만 (롤백 없음)

### C-2: DB 스키마 변경
- `chain_posts` 또는 `publish_log` 테이블에 `smoke_test_passed` 컬럼 추가
- 필요시 `chain_posts`에 `smoke_test_checked_at` 컬럼

### C-3: 단위 테스트
- `test_smoke.py` 또는 기존 test 파일에 smoke_test 단위 테스트 추가 (mock HTTP)

---

## Inputs

- `chain_publisher.py` — `generate_chain_images()` (line 178–321), `_deploy_blogs_after_inject()` (line 608–658)
- `cli/mc.py` — `_run_full()`, `main()`
- `image/thumbnail.py` — `generate_thumbnail()`, `generate_content_image()`, `add_text_overlay()`
- `chain_db.py` — DB 스키마
- `mc_paths.py` — 설정 로딩
- `image/r2_uploader.py` — R2 업로드 함수
- `test_cli_mc.py` — CLI 테스트
- `test_image_pipeline.py` — 이미지 테스트

---

## 잔존 위험

- **Unsplash/Pexels API rate limit:** 50/시간, 200/시간. 3개 포스트 동시 호출 시 rate limit 가능성 낮음. 병렬화 후에도 문제 없을 것으로 예상.
- **Thumbnail 텍스트 오버레이 품질:** Content image 재사용 시 thumbnail이 content image와 동일한 포토가 되어 시각적 다양성 감소. 중요도 낮음 (thumbnail은 주로 og:image/SNS 공유용).
- **Deploy 시간:** Hugo build (~5s) + Wrangler deploy (~20-30s)는 이미지 최적화와 무관. 전체 60s 목표는 이미지 생성 시간만 해당.
- **pytest 유지:** 모든 최적화 후 246/246 유지 필요. 병렬화로 인한 테스트 깨짐 가능성.
