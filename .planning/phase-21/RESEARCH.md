# RESEARCH.md — Phase 21: 이미지 병목 해결 + CLI 기본값 수정 + Smoke Test

**Date:** 2026-07-26
**Source:** Code reading of `chain_publisher.py`, `cli/mc.py`, `image/thumbnail.py`, `image/__init__.py`

---

## 1. 이미지 파이프라인 병목 분석

> Source: `chain_publisher.py` `generate_chain_images()` (line 178–321)

### 1a. Content Image ↔ Thumbnail 중복 API 호출

| 단계 | 함수 | API 호출 | 파일 |
|------|------|---------|------|
| Content image | `img_gen()` → `generate_content_image()` | Unsplash 검색 + 다운로드 | `image/thumbnail.py:442` |
| Thumbnail | `img_thumb()` → `generate_thumbnail()` | Unsplash/Pexels 검색 + 다운로드 + 텍스트 오버레이 | `image/thumbnail.py:344` |

**문제:** Content image와 thumbnail이 **별도 API 호출**로 각각 Unsplash/Pexels에서 사진을 내려받는다. 동일 포스트에 대해 API 2회 호출, HTTP 다운로드 2회 발생.

**차이점:** thumbnail만 `add_text_overlay()`로 제목 텍스트를 입힌다.

### 1b. R2 업로드 중복

- Content image 업로드: `chain_publisher.py:237-244`
- Thumbnail 업로드: `chain_publisher.py:274-281`
- 각각 별도 `put_object` 호출 (동일 R2 bucket, 동일 slug prefix)

### 1c. 고정 sleep

```python
# chain_publisher.py:316-318
if i < len(posts) - 1:
    print(f"  [publisher]     waiting {pol_cfg.get('rate_limit_seconds', 15)}s...")
    time.sleep(pol_cfg.get("rate_limit_seconds", 15))
```

- 3개 포스트 × 15초 = **45초 순수 대기**
- 고정 sleep — API rate limit 여부와 무관하게 항상 대기
- Unsplash/Pexels API rate limit: 각각 50/시간, 200/시간 — 3회 호출로 rate limit에 걸리지 않음

### 1d. 직렬 처리

- 3개 포스트의 이미지 생성이 **독립적** (서로 의존 없음)
- 현재 단일 for 루프로 순차 처리

### 1e. 추정 병목 내역 (3개 포스트 기준)

| 단계 | 현재 | 최적화 후 |
|------|------|----------|
| Content image API (3회) | ~15s (5s × 3) | ~5s (1회, thumbnail 재사용) |
| Thumbnail API (3회) | ~15s (5s × 3) | **0s** (content image 재사용) |
| R2 upload (6회) | ~6s (1s × 6) | ~3s (1s × 3, 하나만 업로드) |
| Sleep (3×) | 45s (15s × 3) | **0s** (제거) |
| 병렬화 | 직렬 | **~5s** (ThreadPoolExecutor) |
| **합계** | **~81s** | **~13s** |

---

## 2. CLI publish_mode 분석

> Source: `cli/mc.py` (line 115–181), `chain_publisher.py` `run_chain()` (line 703–787)

### 현재 상태

- `cli/mc.py` `_run_full()` line 140-142:
  ```python
  else:
      publish_mode = "auto"
  ```
- 이미 `mc "키워드"` (플래그 없음) → `publish_mode = "auto"` → 전체 파이프라인 실행

### 전체 파이프라인 흐름 (publish_mode="auto")

```
run_chain(publish_mode="auto")
  → derive_chain()       # ① 체인 도출
  → draft_chain()        # ② 초안 작성
  → _validate_draft_schema()  # ③ 스키마 검증
  → generate_chain_images()   # ④ 이미지 생성
  → publish_chain(mode="auto")  # ⑤ Hugo 발행
  → inject_cards_chain()       # ⑥ 카드 주입
  → deploy (내부: _deploy_blogs_after_inject 호출)  # ⑦ 배포
```

**결론:** CLI는 이미 `mc "키워드"`로 전체 파이프라인이 동작한다. `--publish` 플래그가 없어도 line 142에서 `publish_mode = "auto"`가 설정된다.

### 개선 필요 사항

1. `deploy`가 `run_chain()` 내부가 아닌 `_deploy_blogs_after_inject()`로만 호출됨 → `publish_chain()`의 `mode="auto"`에서 deploy까지 포함하는지 확인 필요
2. `publish_chain(mode="auto")`는 Hugo 발행 + 카드 주입까지 하지만, **배포는 별도 호출**하도록 되어 있을 수 있음

실제로 `run_chain()` line 762-765:
```python
publish_chain(chain_id, mode=publish_mode, blog_overrides=blog_overrides, ...)
if publish_mode != "manual":
    inject_cards_chain(chain_id)
```

그리고 체인 완료 후 배포는 `_deploy_blogs_after_inject()`가 호출되지 않고 end-to-end 완료 처리로 간다. 이 부분이 **배포 누락** 원인일 수 있다.

---

## 3. 기존 Test Coverage

- `pytest`: **246/246 통과** ✅
- Smoke test: **없음** — 발행 후 URL 자동 검증 기능 부재

---

## 4. 발행 후 배포 확인

> Source: `chain_publisher.py` `publish_chain()` → `_publish_hugo()` chain_publisher_core 위임

- `publish_chain(mode="auto")`: 각 포스트를 Hugo 파일로 작성
- `inject_cards_chain()`: 카드 주입 후 `_deploy_blogs_after_inject()` 호출
- `_deploy_blogs_after_inject()`: Hugo build → Wrangler deploy

**문제:** `_deploy_blogs_after_inject()`의 Hugo build + Wrangler deploy가 성공했는지 검증하는 장치가 없음. 또한 배포 후 발행된 URL의 HTTP 200을 확인하지 않음.

---

## 5. 핵심 측정값

| 항목 | 값 |
|------|-----|
| 현재 pytest | 246/246 |
| 이미지 생성 sleep/post | 15s (고정) |
| Content/thumbnail API 중복 | 2회 호출/post |
| R2 upload 중복 | 2회/post |
| 병렬화 | 미적용 (직렬) |
| Smoke test | 미구현 |
| 배포 URL 검증 | 미구현 |
