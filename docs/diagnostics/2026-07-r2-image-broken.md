# 이미지 깨짐 근본 진단 — R2 업로드 연결 누락

**진단 일시:** 2026-07-22
**진단 범위:** 코드 수정 없음, 읽기/조회만

---

## 1. content_image_path 실제값 (5건 샘플)

| post_id | chain | slug | content_image_path | 유형 |
|---------|-------|------|--------------------|------|
| #172 | #71 s3 | ai프롬프트마켓-20260722-s3 | `/Users/twinssn/projects2/mc/output/images/...webp` | LOCAL_PATH |
| #171 | #71 s2 | ai프롬프트마켓-20260722-s2 | `/Users/twinssn/projects2/mc/output/images/...webp` | LOCAL_PATH |
| #170 | #71 s1 | ai프롬프트마켓-20260722-s1 | `/Users/twinssn/projects2/mc/output/images/...webp` | LOCAL_PATH |
| #157 | #66 s3 | 업클로젯-20260722-s3 | `/Users/twinssn/projects2/mc/output/images/...webp` | LOCAL_PATH |
| #156 | #66 s2 | 업클로젯-20260722-s2 | `/Users/twinssn/projects2/mc/output/images/...webp` | LOCAL_PATH |

**확인:** 전부 로컬 절대 경로. R2 URL 아님.

---

## 2. 라이브 HTML img src (3건)

| 사이트 | 이미지 유형 | src 값 | HTTP | 상태 |
|--------|-----------|--------|------|------|
| rotcha | og:image (썸네일) | `https://img.rotcha.kr/images/rotcha/.../thumb_unsplash_93QRBJ_OcHc.webp` | 200 | ✅ 정상 |
| rotcha | 본문 이미지 | `https://rotcha.kr/images/ai프롬프트마켓-20260722-s1_1024x1024.webp` | **404** | ❌ 깨짐 |
| infohot | og:image (썸네일) | `https://img.informationhot.kr/images/informationhot/.../thumb_unsplash_IEZQLvWp-kU.webp` | 200 | ✅ 정상 |
| infohot | 본문 이미지 | `https://informationhot.kr/images/ai프롬프트마켓-20260722-s2_1024x1024.webp` | **404** | ❌ 깨짐 |

**확인:** 썸네일(og:image)은 R2 URL → 정상 로드. 본문 이미지는 상대 경로 `/images/...` → 404.

---

## 3. R2 업로더 연결 상태

### R2 설정

`image/r2_uploader.py`의 `get_r2_config()` → Hugo 사이트 경로에서 R2 prefix/domain 자동 매핑:

| 사이트 | hugo_root | R2 prefix | R2 domain |
|--------|-----------|-----------|-----------|
| rotcha | `/Users/twinssn/Projects/rotcha-blog` | `images/rotcha` | `https://img.rotcha.kr` |
| informationhot | `/Users/twinssn/Projects/informationhot-hugo` | `images/informationhot` | `https://img.informationhot.kr` |
| techpawz | `/Users/twinssn/Projects/techpawz-hugo` | `images/techpawz` | `https://img.techpawz.com` |

### R2 업로드 흐름

`chain_publisher_core.py` `_publish_hugo()` (line 487-575):

```
1. output/images/에서 본문 이미지를 post_temp_dir/assets/로 복사 (line 490-494)
2. upload_all_images(post_temp_dir, slug, r2_prefix, r2_domain) 호출 (line 498)
   → assets/ 내 모든 파일을 R2에 업로드
   → url_map = {filename: r2_url} 반환
3. Hugo 파일 작성 (line 567-568)
4. 본문 이미지 경로 R2 URL로 교체 (line 570-575):
   text = text.replace("/images/" + local_name, r2_url)
```

**확인:** `upload_all_images`는 본문 이미지도 R2에 업로드함. `url_map`에 본문 이미지 키 포함 확인 (직접 시뮬레이션).

### R2 버킷 퍼블릭 접근

R2 업로드 후 `head_object` 검증 포함 (line 124-126). R2 URL 직접 확인:

| URL | HTTP |
|-----|------|
| `https://img.rotcha.kr/.../thumb_unsplash_93QRBJ_OcHc.webp` | 200 ✅ |
| `https://img.rotcha.kr/.../ai프롬프트마켓-20260722-s1_1024x1024.webp` | 200 ✅ |

**확인:** R2에 본문 이미지 존재, 퍼블릭 접근 가능.

---

## 4. 근인 확정 — card injection이 R2 URL을 덮어쓰기

### 흐름 분석

```
publish_chain(chain_id=71, mode="auto")
  → PublisherCore._publish_hugo()
    → R2 업로드 + url_map 생성
    → Hugo 파일에 /images/xxx → R2 URL 교체 ✅
    → index.md에 R2 URL 기록됨

  → inject_cards_chain(chain_id=71)
    → CardInjector.inject_into_post()
      → DB에서 draft_md 조회 (image_url="/images/xxx" 포함)
      → 기존 frontmatter 추출 (R2 URL이 Featureimage에 있음)
      → updated_md = 기존FM + 본문(/images/xxx 경로)
      → PublisherCore.update_post_content()
        → Hugo 파일에 updated_md 그대로 기록 (R2 교체 없음) ❌
```

### 핵심

1. **`_publish_hugo()`**: R2 업로드 + `/images/xxx` → R2 URL 교체 → Hugo 파일 기록 ✅
2. **`inject_cards_chain()`**: DB의 `draft_md` (원본 `/images/xxx` 경로) 사용 → 기존 FM과 결합 → Hugo 파일 덮어쓰기 ❌
3. **`update_post_content()`**: `new_content`를 그대로 파일에 기록. R2 URL 교체 로직 없음.

**결론:** card injection이 `_publish_hugo`의 R2 URL 교체 결과를 덮어씀. `draft_md`에는 항상 원본 `/images/` 경로가 남아있으므로, card injection 재발행 시 R2 URL이 손실됨.

---

## 5. 썸네일 vs 본문 이미지 분리 확인

| 항목 | 경로 | R2 업로드 | 상태 |
|------|------|----------|------|
| og:image (썸네일) | `featureimage` frontmatter 필드 | `_publish_hugo`에서 R2 URL로 교체됨 | ✅ 정상 |
| 본문 이미지 (body) | `![alt](/images/xxx)` 마크다운 | `_publish_hugo`에서 R2 URL로 교체됨 → card injection이 덮어쓰기 | ❌ 깨짐 |

**확인:** 썸네일만 R2에 올라가고 본문은 누락된 것이 아님. 둘 다 R2에 업로드되지만, 본문만 card injection에 의해 원복됨.

---

## 수정 방향 (다음 세션)

1. **방안 A (권장):** `inject_into_post()`에서 `draft_md`의 `/images/xxx` → R2 URL 교체 후 기록
   - `CardInjector`에 `url_map` 파라미터 추가
   - `inject_cards_chain()`에서 `upload_all_images` 결과를 `inject_into_post`에 전달

2. **방안 B:** `update_post_content()`에 R2 URL 교체 로직 추가
   - `PublisherCore`에 `r2_url_map` 속성 추가
   - `_publish_hugo`에서 `url_map`을 저장, `update_post_content`에서 재사용

3. **방안 C:** `draft_md` 자체를 R2 URL로 업데이트
   - `_publish_hugo` 완료 후 DB의 `draft_md`에서 `/images/xxx` → R2 URL 치환
   - card injection이 항상 최신 경로를 사용하도록 보장
   - 단점: DB의 원본 draft가 변경됨 (복구 어려움)

---

## 잔존 위험

- **Chain #71 외 모든 체인**: 동일 문제. card injection을 거친 모든 체인의 본문 이미지가 깨져있을 가능성.
- **Phase 14 이전 체인**: card injection 없이 발행된 체인은 정상일 수 있음 (확인 필요).
- **pytest**: 171/171 유지 (진단만 수행, 수정 없음).
