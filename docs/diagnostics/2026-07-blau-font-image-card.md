# 진단 보고서: 블라우풍트 스마트워치 체인 (#75) — 이미지 + 카드 2건

**작성일:** 2026-07-23
**진단 대상:** Chain #75 (블라우풍트 스마트워치)
**진단 방법:** DB/코드/라이브 HTML 실측 (수정 금지)

---

## 문제 1: 이미지 — 손 5~6개 생성

### 1-1. DB의 image_prompt 실제값

체인 #75 3개 포스트의 `image_prompt` (DB 저장값):

| depth | image_prompt (DB) | image_url |
|-------|-------------------|-----------|
| 0 | "Flat style digital illustration of a Blaupunkt smartwatch **on a wrist**..." | /images/블라우풍트-스마트워치-20260723-s1_1024x1024.webp |
| 1 | "Flat digital illustration of **a person wearing** a Blaupunkt smartwatch..." | /images/블라우풍트-스마트워치-20260723-s2_1024x1024.webp |
| 2 | "Flat digital illustration showing a cross-section of a Blaupunkt smartwatch..." | /images/블라우풍트-스마트워치-20260723-s3_1024x1024.webp |

**확인:** DB의 `image_prompt`는 AI(chain_deriver)가 생성한 초안 프롬프트가 저장됨. "on a wrist", "a person wearing" 포함.

### 1-2. 실제 Pollinations에 전달된 프롬프트

`mc` 실행 로그 (터미널 출력):
```
[image] 요청: https://image.pollinations.ai/prompt/detailed%20still%20life%20of%20%EB%B8%94%EB%9D%BC%EC%9A%B0%ED%92%8D%ED%8A%B8%20%EC%8A%A4%EB%A7%88%ED%8A%B8%EC%9B%8C%EC%B9%98...
```

`generate_chain_images()`에서 `build_full_prompt()` 호출 → 실제 Pollinations 전달 프롬프트:
```
detailed still life of 블라우풍트-스마트워치. soft pastel illustration, gentle color palette, artistic. no people, no humans, no characters, no faces, no portraits, no figures, no hands, no eyes, no person, no crowd, no portrait. step 1 of depth chain blog series, Korean cultural context. masterpiece, best quality, 8k, trending on ArtStation. negative: text, watermark, signature, logo, text on image, blurry, low quality, distorted face, nsfw, explicit, violent, scary, ugly, deformed, people, person, woman, man, character, human, portrait, face, crowd, figure
```

**확인:** DB `image_prompt` ≠ 실제 전달 프롬프트. `build_full_prompt()` 출력이 실제 사용됨 (mc 로그로 확인).

### 1-3. Pollinations API 호출 방식

`pollinations_client.py` `generate_image(prompt, slug)`:
- GET `https://image.pollinations.ai/prompt/{urlencode(prompt)}?width=1024&height=1024&model=flux`
- **별도 negative 파라미터 없음.** 프롬프트 텍스트 내 `negative: ...` 포함 (Pollinations가 이를 해석한다는 보장 없음)

### 1-4. 프롬프트 내 negative 키워드

`NO_PEOPLE_BLOCK` (prompt_builder.py:44-47):
```
no people, no humans, no characters, no faces, no portraits, no figures, no hands, no eyes, no person, no crowd, no portrait
```

`POLLINATIONS_NEGATIVE` (prompt_builder.py:55-59):
```
text, watermark, signature, logo, text on image, blurry, low quality, distorted face, nsfw, explicit, violent, scary, ugly, deformed, people, person, woman, man, character, human, portrait, face, crowd, figure
```

**확인:** "hands"는 `NO_PEOPLE_BLOCK`에 포함됨. "wrist"는 포함 안 됨.

### 1-5. 주제 유형 분기

`_infer_topic_type("블라우풍트 스마트워치")`:
- `landscape_words` 매칭: 없음
- `abstract_words` 매칭: "tech"가 "스마트워치"에 포함 안 됨 (단어 단위 매칭)
- 결과: **"object"** (기본값)

→ `scene = "detailed still life of 블라우풍트 스마트워치"`

**확인:** 풍경/추상 스타일이 아닌 "사물 정물화" 스타일로 생성됨.

### 1-6. 근인 확정

1. **Pollinations API 미지원:** `negative: ...` 텍스트를 Pollinations가 무시함 (별도 negative 파라미터 없음)
2. **"wrist" 누락:** `NO_PEOPLE_BLOCK`에 "wrist" 없음 → 손목 묘사 허용
3. **주제 오분류:** "스마트워치"가 "object"로 분류되어 풍경/추상 스타일 미적용
4. **DB-실제 불일치:** `image_prompt` DB값이 실제 Pollinations 프롬프트와 다름 (보고 혼선)

---

## 문제 2: 카드 — D0에 외부 링크 카드

### 2-1. 라이브 HTML 카드 추출

| 포스트 | 발견된 카드 | 텍스트 | 링크 |
|--------|------------|--------|------|
| rotcha (D0) | 3개 | "다음 글" (중간) + "다음 글" (하단) + **"공식 안내"** | → infohot, → infohot, → Naver search |
| infohot (D1) | 3개 | "다음 글" (중간) + "다음 글" (하단) + **"공식 안내"** | → techpawz, → techpawz, → Naver search |
| techpawz (D2) | 1개 | "더 많은 정보" | → Naver search |

**확인:** D0, D1에 "공식 안내" 카드(외부 링크)가 주입됨. W3 설계 위반.

### 2-2. 분기 로직 실제 동작

`inject_cards_into_draft()` (chain_card_injector.py:439-460):

```python
if is_last:
    # Depth 2: 외부 링크 카드
    ...
else:
    # Depth 0/1: 다음 글 카드
    ...
    # 공식 안내 링크 카드 (Depth 0/1도 마지막에)  ← BUG
    official_link = self.find_official_link(...)
    official_card = self.build_official_card_html(official_link)
    if official_card:
        body = self.inject_bottom_card(body, official_card)
```

**확인:** `is_last=False` (D0, D1)일 때도 `official_card` 주입됨. 코드 주석에 "Depth 0/1도 마지막에"라고 명시됨 (의도된 버그).

### 2-3. W3 설계 vs 실제 동작

| 설계 (W3 보고) | 실제 코드 | 라이브 결과 |
|----------------|----------|-----------|
| D0: 다음 글만 | D0: 다음 글 + 공식 안내 | 2개 카드 ✗ |
| D1: 다음 글만 | D1: 다음 글 + 공식 안내 | 2개 카드 ✗ |
| D2: 외부 링크 | D2: 외부 링크만 | 1개 카드 ✓ |

**확인:** W3 설계와 실제 코드 불일치. `inject_cards_into_draft()` 456-460행이 원인.

### 2-4. 보고-실제 불일치 원인

W3 완료 보고 시 "D0 카드: 다음 글 → infohot ✅" 검증 방법:
- DB `card_injected=1` 확인 (실제 카드 내용 미확인)
- 라이브 HTML 검증 시 "다음 글" 텍스트만 확인 (공식 안내 카드 존재 무시)

**확인:** 단위 테스트 통과 + DB 플래그 확인만으로 "완료" 보고. 라이브 HTML 전체 검증 누락.

---

## 교차 분석

### W2·W3 머지 후 보고-실제 불일치 패턴

1. **이미지:** `build_full_prompt()`가 올바른 프롬프트를 생성하지만 Pollinations가 negative 무시 → "no hands" 포함됐으나 5~6개 손 생성
2. **카드:** W3 설계서는 "D0/D1: 다음 글만"이나 실제 코드는 "D0/D1: 다음 글 + 공식 안내"로 구현 → 퍼널 붕괴

### 구조적 원인

- **단위 테스트 통과 ≠ 실제 발행 동작 보장 안 됨:** Pollinations API 동작, Hugo 빌드, 카드 HTML 주입은 통합 테스트 필요
- **DB 값 ≠ 실제 동작:** `image_prompt` DB값이 실제 Pollinations 전달값과 다름 (보고 시 혼선)
- **W3 설계서-코드 불일치 방치:** `inject_cards_into_draft()` 주석에 "Depth 0/1도 마지막에"라고 명시하고도 머지됨

---

## 수정 방향 제안 (다음 세션)

### 이미지
1. `NO_PEOPLE_BLOCK`에 "wrist", "finger", "arm" 추가
2. `_infer_topic_type()`에 "스마트워치", "watch", "tech" 등의 단어 추가 → "abstract" 분기
3. Pollinations 프롬프트에 "NO PEOPLE, NO HANDS, NO WRIST"를 프롬프트 앞부분에 강조 배치
4. DB `image_prompt` 필드에 실제 Pollinations 전달 프롬프트 저장 (현재는 AI 초안 프롬프트만 저장)

### 카드
1. `inject_cards_into_draft()` 456-460행 제거 (D0/D1의 `official_card` 주입 제거)
2. W3 설계서대로 D0/D1은 "다음 글" 카드만, D2만 외부 링크 카드

---

## 잔존 위험
- Pollinations API가 negative 프롬프트를 무시하는 구조적 한계 → 이미지 품질 보장 불가
- 기존 체인 25건 미닫힌 펜스 (이번 세션 스캔 완료, 수정은 별도)
- (a) 43건 고아 이미지, P3 Blowfish, Phase 14.1 — 이번 세션 미건드림
