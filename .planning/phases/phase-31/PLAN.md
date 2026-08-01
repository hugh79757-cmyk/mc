# PLAN.md — Phase 31: 동적 공식 링크 탐색 시스템

**Phase:** 31
**File:** `chain_card_injector.py` (변경 대상)
**Test:** `test_w3_cards_image.py` (갱신 필요)

---

## 핵심 변경 전략

**현재:** `_score_official()`이 개별 URL을 보고 정부 TLD면 무조건 "공공기관" 라벨
**변경:** 정부 TLD 결과가 `find_external_links()`에서 최고 점수로 선정된 경우, 비정부 TLD 대안이 있으면 우선 채택

### Approach: `find_external_links()`에서 정부 TLD 우선순위 조정

`_score_official()`의 점수/priority 로직은 유지하고, `find_external_links()`의 선택 로직에서:

1. 모든 검색 결과를 priority/score로 정렬 (기존 동작)
2. primary로 선정될 결과가 정부 TLD인 경우:
   - 비정부 TLD 결과 중 score가 55 이상(priority 1 자격)인 것이 있으면 → 그 중 최고 점수를 primary로 채택
   - 없으면 → 정부 TLD 결과를 그대로 primary로 유지 (기존 동작)
3. 라벨은 `_score_official()`이 반환한 값을 그대로 사용

**장점:**
- `_score_official()`의 점수 로직 변경 없음
- 기존 테스트 영향 최소화
- 검색 결과에 비정부 공식 사이트가 있으면 자동으로 우선 채택

---

## Task 1: 백업 생성

```bash
cp chain_card_injector.py chain_card_injector.py.bak
```

---

## Task 2: `find_external_links()` 로직 수정

**변경 위치:** `chain_card_injector.py` Lines 212-226 (`find_external_links` 메서드)

**변경 전:**
```python
# Sort by priority (lower = better), then by order of appearance
all_links.sort(key=lambda x: (x["priority"], -x.get("score", 0)))

primary = None
secondary = []
seen_urls = set()
for link in all_links:
    if link["url"] in seen_urls:
        continue
    seen_urls.add(link["url"])
    if link["priority"] == 1 and primary is None:
        primary = link
    elif link["priority"] == 2:
        secondary.append(link)
```

**변경 후:**
```python
# Sort by priority (lower = better), then by score (higher = better)
all_links.sort(key=lambda x: (x["priority"], -x.get("score", 0)))

def _is_gov_domain(url: str) -> bool:
    """정부 TLD 여부 확인."""
    domain = url.split("//", 1)[1].split("/", 1)[0] if "//" in url else url
    from constants import AUTHORITY_GOVERNMENT
    return any(domain.endswith(d) for d in AUTHORITY_GOVERNMENT) or domain.endswith(".gov")

primary = None
secondary = []
seen_urls = set()
gov_candidates = []  # 정부 TLD 우선순위 후보

for link in all_links:
    if link["url"] in seen_urls:
        continue
    seen_urls.add(link["url"])
    if link["priority"] == 1 and primary is None:
        primary = link
    elif link["priority"] == 1 and primary is not None:
        # 이미 primary가 있고, 현재 링크도 priority 1이면 정부 TLD 대안 수집
        if _is_gov_domain(primary["url"]) and not _is_gov_domain(link["url"]):
            # primary가 정부 TLD이고 현재 링크는 비정부 → 비정부를 primary로 교체
            gov_candidates.append(primary)  # 기존 primary는 후보로 이동
            primary = link
        elif _is_gov_domain(primary["url"]) and _is_gov_domain(link["url"]):
            # 둘 다 정부 TLD → score 비교
            if link.get("score", 0) > primary.get("score", 0):
                gov_candidates.append(primary)
                primary = link
            else:
                gov_candidates.append(link)
        else:
            # primary가 비정부, 현재도 비정부 → 기존 유지
            gov_candidates.append(link)
    elif link["priority"] == 2:
        secondary.append(link)
```

**변경 근거:**
- priority 1 결과가 정부 TLD이고, 다른 priority 1 비정부 결과가 있으면 비정부를 우선
- 기존 점수/priority 로직은 `_score_official()`에서 그대로 유지
- `secondary`는 기존대로 priority 2 결과만 수집

---

## Task 3: 구문 검증

```bash
python3 -c "import ast; ast.parse(open('chain_card_injector.py').read())"
```

---

## Task 4: 기존 테스트 확인 + 새 테스트 추가

**기존 테스트 영향:**
- `test_score_official_government`: `_score_official()` 단위 테스트 → 변경 없음 (라벨 로직은 `_score_official`에서 변경 안 함)
- `test_score_official_brand_signal`: `_score_official()` 단위 테스트 → 변경 없음

**새 테스트 추가:** `test_find_links_prefers_nongov_over_gov`

```python
def test_find_links_prefers_nongov_over_gov(self):
    """정부 TLD 결과가 priority 1이더라도, 비정부 priority 1이 있으면 비정부를 primary로 채택."""
    from chain_card_injector import CardInjector
    injector = CardInjector.__new__(CardInjector)
    
    # 모의 검색 결과: 정부 TLD + 비정부 TLD 둘 다 priority 1
    mock_links = [
        {"url": "https://www.gov.kr/poolheaven", "label": "공공기관", "priority": 1, "score": 85},
        {"url": "https://poolheaven.co.kr", "label": "공식 사이트", "priority": 1, "score": 75},
    ]
    # find_external_links 내부에서 sort 후 선택
    # 비정부가 primary로 채택되어야 함
```

---

## Task 5: 전체 테스트 실행

```bash
python -m pytest -q
```

목표: 762+ 테스트 통과, 회귀 없음.

---

## Task 6: 검증 재현

| 시나리오 | 검색 결과 모의 | 기대 primary |
|---------|--------------|-------------|
| 정부기관 only | gov.kr만 priority 1 | gov.kr (기존 동작 유지) |
| 정부+비정부 혼합 | gov.kr + 상용 site 둘 다 priority 1 | 상용 site 우선 |
| 비정부 only | 상용 site만 priority 1 | 상용 site (기존 동작) |

---

## 검증 기준

- [ ] `find_external_links()`에서 정부 TLD 우선순위 조정
- [ ] `_score_official()` 점수/priority 로직 변경 없음
- [ ] 구문 검증 통과
- [ ] 기존 762+ 테스트 전체 통과 (회귀 없음)
- [ ] 새 테스트 통과
- [ ] `.bak` 파일 1개만 생성
