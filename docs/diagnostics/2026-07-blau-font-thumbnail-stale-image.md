# 진단 보고서: 블라우풍트 체인 (#75) — 썸네일 스킵 + 예전 이미지 재사용

**작성일:** 2026-07-23
**진단 대상:** Chain #75 (블라우풍트 스마트워치)
**진단 방법:** DB/코드/라이브 실측값 (수정 금지)

---

## 문제 1: 썸네일 스킵 ("[Hugo] image_keyword 없음, 썸네일 생성 스킵")

### 1-1. DB image_keyword 실제값

체인 #75 3개 포스트의 `image_meta` JSON:

| depth | image_meta 필드 | 값 |
|-------|-----------------|-----|
| 0 | content_image_path | `/Users/.../output/images/블라우풍트-스마트워치-20260723-s1_1024x1024.webp` |
| 0 | content_image_source | pollinations |
| 0 | **image_keyword** | **없음** |
| 0 | **thumbnail_path** | **없음** |
| 1 | (동일) image_keyword | **없음** |
| 1 | (동일) thumbnail_path | **없음** |
| 2 | (동일) image_keyword | **없음** |
| 2 | (동일) thumbnail_path | **없음** |

**확정:** `image_meta`에 `image_keyword` 필드가 존재하지 않음.

### 1-2. image_keyword 누락 원인

`generate_chain_images()` (chain_publisher.py:204-218)가 이미지 생성 후 호출하는 DB 저장 함수:

```python
db.update_content_image(post_id, str(image_path), "pollinations")
db.update_post_image(post_id, image_url)
```

`update_content_image()`은 `content_image_path`와 `content_image_source`만 image_meta에 저장함. `image_keyword`, `thumbnail_path` 등은 저장하지 않음.

반면, AI draft 단계(chain_deriver)에서는 image_meta에 `image_keyword`, `image_type`, `angle` 등이 포함됨.

**결론:** `generate_chain_images()`가 image_meta의 image_keyword를 보존하지 않음(덮어씀?).

### 1-3. _publish_hugo() 동작

chain_publisher_core.py:396-398:
```python
if not _thumb_abs or not Path(_thumb_abs).exists():
    if not _kw:
        logger.warning(f"[Hugo] image_keyword 없음, 썸네일 생성 스킵: {slug}")
```

`_kw` = `_image_meta.get("image_keyword")` — image_meta에 image_keyword가 없으므로 `None` → 썸네일 스킵.

### 1-4. 썸네일 스킵 근인 확정

**`generate_chain_images()`가 image_meta의 `image_keyword` 필드를 제거/미설정함.**

초기 AI draft 시점의 image_meta에는 image_keyword가 있었으나, `generate_chain_images()`가 `update_content_image()`로 부분 갱신할 때 나머지 필드를 보존하지 않음.

---

## 문제 2: 예전 이미지 재사용 (손 5~6개 이미지 그대로)

### 2-1. 실제 이미지 크기 비교

| 이미지 | 위치 | 크기 | 생성 시각 |
|--------|------|------|-----------|
| R2 content image (라이브) | `img.rotcha.kr/.../s1_1024x1024.webp` | **70,364 bytes** | 첫 발행 |
| Local new image | `output/images/...s1_1024x1024.webp` | **48,588 bytes** | 11:53 (두 번째 resume) |
| R2 thumbnail | `img.rotcha.kr/.../thumb_*.webp` | **HTTP 404** | 업로드 안 됨 |

**확정:** R2 이미지(70KB) ≠ 신규 이미지(48KB). 라이브에 예전 이미지가 그대로 노출됨.

### 2-2. 이미지 미업로드 원인 — 체인 분석

첫 번째 발행 흐름:
1. `generate_chain_images()` → 이미지 생성 + DB 저장
2. `_publish_hugo()`:
   - 2a. 썸네일 생성 (image_keyword 있음) → OK
   - 2b. 내용 이미지 생성 (Pollinations) → 70KB 생성
   - 2c. `<!--todo:image-->` 마커 해결 → OK
   - 2d. `/images/` 경로 이미지 assets_dir 복사 → OK
   - 2e. `upload_all_images()` → R2 업로드 OK
   - 2f. Hugo 빌드 + wrangler deploy

두 번째 발행 흐름 (resume 후):
1. `generate_chain_images()` → 신규 이미지 생성 (48KB) + `content_image_path` 갱신
2. `_publish_hugo()`:
   - 2a. 썸네일: `image_keyword` 없음 → **스킵**
   - 2b. 내용 이미지: `_has_content_image = True` (이미 설정됨) → **스킵** (line 416)
   - 2c. `<!--todo:image-->` 마커: draft_md에 없음 → **스킵** (line 490)
   - 2d. `/images/` regex: draft_md가 R2 절대 URL 사용 중 → **매칭 실패** (line 511)
   - 2e. `upload_all_images()`: assets_dir에 새 이미지 없음 → **업로드 없음**
   - 2f. Hugo 빌드 + wrangler deploy (R2 URL은 예전 이미지 그대로)

### 2-3. 근인 확정

**`_publish_hugo()`가 `_has_content_image`가 이미 True일 때 이미지 재생성/재업로드를 하지 않음.**

`generate_chain_images()`가 새 이미지를 생성했지만, `_publish_hugo()`는 `content_image_path`가 이미 존재하므로(line 416 `not _has_content_image` = False) 이미지 생성을 스킵. 또한 draft_md가 이미 R2 절대 URL을 포함하므로 local 경로 치환도 발생하지 않음.

### 2-4. W2 수정이 발행에 적용 안 된 이유

**W2 수정 자체는 Pollinations 호출에 적용됨** (로그: `[image] 요청: ... NO%20PEOPLE.%20NO%20HANDS.%...` → 48KB 신규 이미지 생성 성공).

그러나 생성된 신규 이미지가 **R2에 업로드되지 않아** 라이브에는 반영되지 않음.

라이브에 노출된 이미지는 R2의 예전 이미지(70KB, 첫 발행 시 생성된 "손 5~6개" 이미지).

---

## 교차 분석: "재발행" ≠ "이미지 갱신"

| 단계 | 첫 발행 | 두 번째 resume |
|------|---------|---------------|
| 이미지 생성 | Pollinations 호출 → 70KB | Pollinations 호출 → 48KB ✅ |
| image_meta 저장 | image_keyword + image_type 등 포함 | content_image_path만 갱신 ❌ |
| thumbnail 생성 | image_keyword 있음 → 생성 | image_keyword 없음 → 스킵 ❌ |
| 이미지 R2 업로드 | 70KB 업로드 | 48KB 미업로드 (content_image_path 이미 있음) ❌ |
| draft_md 이미지 경로 | `<!--todo:image-->` → R2 URL | R2 URL 그대로 (변경 없음) ❌ |
| Hugo 빌드 | R2 URL 포함 → OK | R2 URL 그대로 → 예전 이미지 ❌ |

**핵심:** "재발행"이 실행됐지만, 이미지 파이프라인이 예전 content_image_path 존재를 감지하고 재생성을 스킵함. 결과적으로 Hugo 빌드는 동일한 R2 URL을 참조 → 예전 이미지.

---

## 수정 방향 제안 (다음 세션)

1. **`generate_chain_images()` image_meta 보존 강화**
   - `update_content_image()` 호출 시 기존 image_meta의 image_keyword 등을 유지

2. **`_publish_hugo()` 재발행 시 이미지 재업로드**
   - `content_image_path`가 이미 있어도 새 이미지 파일이 기존과 다르면 assets_dir 복사 + R2 재업로드
   - 또는 재발행 전용 플래그 추가

3. **W1~W3 테스트 통과 + 라이브 검증 프로토콜**
   - DB image_prompt값 확인만 하지 말고, R2 이미지 파일 크기/해시로 실제 업로드 확인
   - 라이브 페이지 <img src>에서 다운로드하여 실제 이미지 내용 확인

---

## 잔존 위험

- 썸네일 누락: image_keyword 없는 모든 체인에서 썸네일 없음
- 이미지 재업로드 구조적 한계: content_image_path 존재 시 재발행해도 이미지 갱신 안 됨
- 모든 R2 URL은 첫 발행 시점에 고정, 재발행 시 바뀌지 않음
