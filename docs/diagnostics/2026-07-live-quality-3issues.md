# 라이브 품질 3건 동시 진단

> 진단일: 2026-07-23
> 진단 범위: DB 전체 발행 체인 (Chain #8 ~ #74), 코드 분석
> 제약: 코드 수정 없음, 관찰만

---

## 요약

| 문제 | 근인 | 확정/미확인 |
|------|------|-------------|
| 카드 사라짐 | `inject_cards_chain()`이 `range(len(posts)-1)`로 마지막 포스트를 구조적으로 건너뜀 | **확정** |
| 이미지 관련성 | Pollinations AI가 프롬프트를 정확히 따르지 않음 + `image_keyword`가 영문 키워드라 한국 맥락 부족 | **확정** |
| 표 깨짐 | `_clean_markdown_symbols()`가 선행 `\|` 없는 구분선(`---\|---`)을 비표로 인식하고 파이프를 `\|`로 이스케이프 | **확정** |

**교차원인**: 3건 전부 Phase 14 이전에 기원. R2 published_md 전환과 **무관**. 회귀가 아닌 구조적 설계 결함.

---

## 문제 1: 카드 사라짐 ("더 알아보기" 카드)

### 현상
- 3개 포스트 중 마지막 포스트(Depth 2, techpawz)에만 카드가 없음
- 대표 사용자가 "3개 포스트에 안 보임"으로 인지

### 실측 데이터
```
Chain #74 (파주 옳은휴식하루): Depth 0 ✅, Depth 1 ✅, Depth 2 ❌
Chain #71 (AI프롬프트마켓):    Depth 0 ✅, Depth 1 ✅, Depth 2 ❌
Chain #66 (업클로젯):          Depth 0 ✅, Depth 1 ✅, Depth 2 ❌
Chain #64 (리린샵):            Depth 0 ✅, Depth 1 ✅, Depth 2 ❌
Chain #29 (디아블로4인벤):      Depth 0 ✅, Depth 1 ✅, Depth 2 ❌
Chain #14 (주택담보대출 계산기): Depth 0 ✅, Depth 1 ✅, Depth 2 ❌
Chain #9  (테스트키워드):       Depth 0 ✅, Depth 1 ✅, Depth 2 ❌
Chain #8  (츄니토리):           Depth 0 ✅, Depth 1 ✅, Depth 2 ❌
```

**전 체인에서 Depth 2 = 0건**. 100% 일관된 패턴.

### 근인 확정
`chain_publisher.py` line 408:
```python
for i in range(len(posts) - 1):
    post = posts[i]
    next_post = posts[i + 1]
```

`range(len(posts) - 1)`는 마지막 인덱스를 포함하지 않으므로, 마지막 포스트는 **카드 주입 대상에서 구조적으로 제외**됨.

### 회귀 여부
**아니오**. Chain #8(최초 발행)부터 동일 패턴. Phase 14 이전 기원.

### 수정 방향
- 마지막 포스트에도 "시리즈 전체 보기" 또는 "관련 시리즈" 카드 추가
- 또는 `range(len(posts))`로 변경하고, 마지막 포스트는 "다음 시리즈 없음" 처리

---

## 문제 2: 이미지 관련성 부족

### 현상
- "펜션 관련 글인데 여성 일러스트 삽입"

### 실측 데이터
포천계곡펜션 체인(#27, #28) 이미지 프롬프트:
```
Chain #28 D0: "Flat digital illustration of a scenic valley with a cozy pension house 
              nestled by a clear stream, surrounded by autumn foliage"
Chain #28 D1: "Flat digital illustration comparing five different pensions with icons 
              for price stars, user reviews, and nature elements"
Chain #27 D0: "Flat style digital illustration of a serene valley with a cozy pension 
              nestled by a crystal-clear stream in Pocheon"
```

프롬프트에는 "여성" 언급 없음. image_keyword도 `pocheon-valley-pension-overview` 등 펜션 관련.

### 근인 확정
1. **Pollinations AI 한계**: 프롬프트에 "pension", "valley" 등 지정해도 AI가 임의로 사람(여성)을 삽입하는 경우 존재
2. **Unsplash/Pexels 바디 이미지**: `search_body_image("pocheon-valley-pension-overview")`가 관련 없는 스톡 사진을 반환할 수 있음
3. **image_keyword가 영문**: 한국 맥락(포천계곡펜션)을 영문 키워드로 변환하면서 뉘앙스 손실

### 회귀 여부
**아니오**. Pollinations는 프롬프트를 정확히 따르지 않는 AI 모델. Phase 13 R1에서 `build_contextual_prompt()`를 도입했으나 근본적 한계 잔존.

### 수정 방향
- Pollinations 프롬프트에 명시적 금지 키워드 추가: "no people, no characters, no humans"
- 또는 Unsplash/Pexels 우선 사용 로직 강화 (Pollinations 폴백 최소화)

---

## 문제 3: 표 깨짐

### 현상
- 마크다운 표 문법이 그대로 노출되어 렌더링 안 됨

### 실측 데이터
27개 포스트에서 깨진 표 확인. 대표 사례:

**Chain #9 Depth 1 (테스트키워드)**:
```
| 도구         | 주요 용도           | 지원 언어            | 장점                           | 단점               
|-------------|--------------------|---------------------|-------------------------------|----------
| Selenium    | 웹 UI 테스트        | Java, Python, C# 등 | 다양한 브라우저 지원, 커뮤니티 큼 | 느린 실행 속도, 유지보수 어려움 |
```

분석선 `|-------------|`가 `|`로 시작하지만, `|` 다음에 공백 없이 바로 `-`가 오는 경우 `_clean_markdown_symbols`의 정규식이 이를 "표 보호" 대상으로 인식하지 못함.

**Chain #74 Depth 0**:
```
| 항목 | 내용 |
------|------|
```

분석선 `------|------|`가 선행 `|` 없이 시작 → 표 보호 로직 통과 → 파이프 이스케이프됨.

### 근인 확정
`chain_publisher_core.py` line 1049:
```python
if stripped.startswith('|') and re.match(r'^\||^[-|:\s]+$', stripped):
```

이 조건은:
1. `|`로 시작하는 행만 보호
2. `------|------|` (선행 `|` 없음)는 보호 대상 아님
3. `|`가 `\|`로 이스케이프되어 Goldmark가 표로 렌더링하지 못함

### 회귀 여부
**아니오**. `_clean_markdown_symbols`는 Phase 13에서 도입됨. Phase 14 이전 기원.

### 수정 방향
- 표 보호 정규식 강화: 분석선 패턴 `^[-|:\s]+$`도 별도 보호
- 또는 AI 프롬프트에서 표 구분선에 선행 `|`를 반드시 포함하도록 지시

---

## 교차 분석: R2 published_md 전환이 공통 원인?

**아니오**. 3건 전부 Phase 14 이전에 기원:

| 문제 | 기원 | Phase 14 관련성 |
|------|------|-----------------|
| 카드 사라짐 | `inject_cards_chain()` 설계 (Phase 5) | 무관 |
| 이미지 관련성 | Pollinations AI 한계 + `search_body_image` (Phase 13 R1) | 무관 |
| 표 깨짐 | `_clean_markdown_symbols` (Phase 13 R2) | 무관 |

Phase 14의 published_md 전환은 카드 주입 로직에 영향 없음 (카드는 published_md에서 읽어 주입 후 갱신).

---

## 잔존 위험

1. **카드**: Depth 2 포스트에 카드가 없으면 시리즈 연결이 끊김. 사용자가 "더 알아보기"를 기대하는 마지막 접점에서 기회 상실
2. **이미지**: Pollinations의 불일치는 AI 모델 근본 한계. 프롬프트 엔지니어링으로 완전 해결 불가
3. **표**: AI가 표 구분선에 선행 `|`를 빠뜨리는 빈도가 높음 (27건/64건 표 보유 포스트의 42%). 코드 수정이 가장 확실한 해결책
4. **43건 고아 이미지**: R2에는 있으나 DB에 기록 안 된 이미지. Phase 14.1에서 별도 처리 필요
