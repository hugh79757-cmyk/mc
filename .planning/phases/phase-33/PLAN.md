---
wave: 1
gap_closure: false
---

# PLAN.md — Phase 33 Wave 1: AI 출력 JSON 메타데이터 잔류 근본 수정 (코드+테스트)

**Phase:** 33
**Wave:** 1 (코드 수정 + Mocking 테스트)
**기반:** CONTEXT.md (조사 완료)
**현재 테스트:** 792개 (`pytest --co -q` 실측)

---

## 목표

AI 출력에 포함된 JSON 메타데이터(`image_type`, `chart_type`, `image_keyword` 등)가 본문에 섞여 들어와 배포 검증(`_verify_before_deploy`)에서 "JSON 잔류"로 차단되는 문제를 **파싱 시점 분리(1순위)**와 **2차 방어 강화(2순위)**로 근본 해결. 관측성 로깅(3순위)으로 재발 시 원인 즉시 식별 가능하게 함.

**핵심 원칙**: "사후 제거" → **"파싱 시점 분리"**. 반환 규약 변경 없음(하위호환 유지).

---

## Wave 1 범위: 코드 수정 + Mocking 테스트 (라이브 배포 제외)

Wave 1은 **코드 수정 + 로컬 Mocking 테스트(792 tests)** 까지만 수행한다.  
**실제 #378 재발행(T7)은 Wave 2(별도 승인)에서 수행**한다.

---

## Task 분해 (Wave 1)

### T1: 백업 (5분)
- [ ] 수정 대상 파일 4개 백업
  - `cp chain_models.py chain_models.py.bak`
  - `cp chain_publisher_core.py chain_publisher_core.py.bak`
  - `cp chain_publisher.py chain_publisher.py.bak`
  - `cp test_chain_models.py test_chain_models.py.bak` (테스트 확장 시)

**검증**: `ls *.bak` → 4개 확인

---

### T2: 파싱 분리 구현 — `chain_models.py` (40분)

#### 2-1. `_extract_meta_from_raw()` 재작성 (line 206)
**목표**: 코드펜스 유무·들여쓰기·다중라인 무관하게 JSON 블록을 **중괄호 깊이 카운팅**으로 탐지해 메타데이터 추출.

**설계**:
1. 코드펜스(```json) 패턴 3개 유지 (하위호환).
2. 평문/들여쓰기/다중라인 JSON 탐지: `raw` 전체를 순회하며 `{` 발견 시 깊이 카운팅(`depth++`), `}` 시 `depth--`. `depth == 0` 되면 후보 블록 완성.
3. 후보에 `"image_type"` 또는 `"chart_type"` 키 포함 시 → `json.loads()`로 파싱 시도. 성공 시 dict 반환.
4. 다중 JSON 객체 존재 시 **첫 번째** 유효 메타만 사용 (나머지는 본문 잔류 → 2차 방어로 처리).
5. 파싱 실패/키 미포함 시 폴백: 빈 dict 반환 (기존 `return {}` 유지).

**구현 상세**:
```python
def _extract_meta_from_raw(raw: str) -> dict:
    # 1. 코드펜스 패턴 (기존 유지)
    patterns = [...]
    for pattern in patterns:
        m = re.search(pattern, raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
                if isinstance(parsed, dict) and ("image_type" in parsed or "chart_type" in parsed):
                    return parsed
            except: pass

    # 2. 중괄호 깊이 카운팅으로 평문/다중라인 JSON 탐지
    for p in range(len(raw) - 1, -1, -1):
        if raw[p] == '}':
            depth = 0
            start = -1
            for q in range(p, max(0, p - 2000), -1):  # 500→2000자로 확대
                if raw[q] == '}':
                    depth += 1
                elif raw[q] == '{':
                    depth -= 1
                    if depth == 0:
                        start = q
                        break
            if start != -1:
                candidate = raw[start:p + 1]
                if '"image_type"' in candidate or '"chart_type"' in candidate:
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict):
                            return parsed
                    except: pass
    return {}
```

#### 2-2. `_extract_body_from_raw()` 재작성 (line 155)
**목표**: 메타데이터 JSON 블록(코드펜스 유무 무관)을 본문에서 **완전 제거**.

**설계**:
1. `_extract_meta_from_raw()`와 **동일한 탐지 로직** 공유(함수 분리 권장).
2. 탐지된 JSON 블록의 위치(start, end)를 기록해 본문에서 해당 구간 삭제.
3. 코드펜스 JSON 정규식 제거 로직 유지(하위호환).
4. 여러 JSON 블록 있을 수 있으므로 **전체 순회하며 모두 제거**.
5. `thumbnail/image/todo` 플레이스홀더 정리, 과도한 개행 정리 유지.

**구현 상세**:
```python
def _extract_body_from_raw(raw: str) -> str:
    # 1. AI가 출력한 FM 블록 제거 (기존 유지)
    _raw_cleaned = raw.lstrip()
    if _raw_cleaned.startswith("---"):
        _end = _raw_cleaned.find("---", 3)
        if _end != -1:
            _raw_cleaned = _raw_cleaned[_end + 3:].lstrip("\n")
        else:
            _raw_cleaned = _raw_cleaned[3:].lstrip("\n")
    cleaned = _raw_cleaned

    # 2. 코드펜스 JSON 제거 (기존 유지)
    cleaned = re.sub(r'```json\s*\n?\{.*?\}\s*\n?```', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'```json\s*\n?\{.*?\}\s*$', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'```\s*\n?\{.*?\}\s*\n?```', '', cleaned, flags=re.DOTALL)

    # 3. 중괄호 깊이 카운팅으로 평문/다중라인 JSON 블록 모두 제거
    # 탐지된 블록 위치를 리스트에 모아 역순으로 삭제(인덱스 시프트 방지)
    blocks = []
    for p in range(len(cleaned) - 1, -1, -1):
        if cleaned[p] == '}':
            depth = 0
            start = -1
            for q in range(p, max(0, p - 2000), -1):
                if cleaned[q] == '}':
                    depth += 1
                elif cleaned[q] == '{':
                    depth -= 1
                    if depth == 0:
                        start = q
                        break
            if start != -1:
                candidate = cleaned[start:p + 1]
                if '"image_type"' in candidate or '"chart_type"' in candidate:
                    try:
                        json.loads(candidate)  # 검증용
                        blocks.append((start, p + 1))
                    except: pass
    # 역순으로 삭제
    for start, end in sorted(blocks, reverse=True):
        cleaned = cleaned[:start] + cleaned[end:]

    # 4. 플레이스홀더/개행 정리 (기존 유지)
    cleaned = re.sub(r'<!--\s*(thumbnail|image)\s*:\s*.*?-->', '', cleaned)
    cleaned = re.sub(r'<!--\s*todo:\s*(image|chart)\s*-->', '', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    return cleaned.strip()
```

**공통 함수 추출 권장**: JSON 블록 탐지 로직(`find_json_blocks(raw) -> list[(start, end, dict)]`)을 별도 함수로 분리해 `_extract_meta_from_raw()`와 `_extract_body_from_raw()`가 공유 → 중복 방지·일관성 보장.

---

### T3: 2차 방어 강화 — `chain_publisher_core.py` (30분)

#### 3-1. `is_raw_json` 블록 단위 탐지로 변경 (line 117)
**현재**: `is_raw_json = stripped.startswith("{") and ("image_type" in stripped or "chart_type" in stripped)` — 줄 단위라 들여쓰기/다중라인 미탐지.

**변경**: 함수 내 헬퍼 `is_json_block_with_meta(line, next_lines)` 추가 또는 인라인 중괄호 카운팅으로 블록 단위 판단.

**구현**:
```python
# _extract_clean_body() 내부 헬퍼
def _is_json_block_with_meta(lines, idx):
    """lines[idx:]부터 중괄호 깊이 카운팅으로 JSON 블록 완성 여부 및 메타 키 포함 여부 판단"""
    depth = 0
    block = []
    for j in range(idx, min(len(lines), idx + 100)):  # 최대 100줄 앞까지
        l = lines[j]
        block.append(l)
        for ch in l:
            if ch == '{': depth += 1
            elif ch == '}': depth -= 1
        if depth == 0 and block:
            block_text = "\n".join(block)
            if '"image_type"' in block_text or '"chart_type"' in block_text:
                try:
                    json.loads(block_text)
                    return True
                except:
                    return False
        elif depth < 0:
            break
    return False

# 메인 루프에서 사용
for i, line in enumerate(lines):
    stripped = line.strip()
    # ... 기존 is_heading/is_list 등 계산 ...
    is_raw_json = _is_json_block_with_meta(lines, i)
    if is_html_comment or is_html_tag or is_raw_json:
        continue
    # ...
```

#### 3-2. `skip_json_block` 확대 (line 90-97)
**현재**: ``````json` 펜스만 스킵.

**변경**: `is_raw_json`이 True인 블록도 동일하게 스킵(`skip_json_block = True`). 중괄호 깊이 카운팅으로 블록 끝(`depth == 0`)까지 스킵 유지.

```python
if skip_json_block:
    if stripped.startswith("```"):
        skip_json_block = False
    continue

if stripped.startswith("```"):
    lang = stripped[3:].strip()
    if lang.lower() == "json":
        skip_json_block = True
        continue
    # ...

# 추가: 줄 단위 JSON 블록도 스킵
if is_raw_json:
    skip_json_block = True
    continue
```

---

### T4: 관측성 로깅 (20분)

#### 4-1. `chain_publisher.py:474-478` try-except 추가
**현재**: `core.publish_post()` 호출부 예외 처리 없음 → 빈 튜플 반환 시 상세 원인 미출력.

**변경**:
```python
try:
    url, method, file_path = core.publish_post(
        blog_key, draft_md, slug, title, labels, post_id=post["id"]
    )
except DeployValidationError as e:
    logger.error(f"[PUBLISH-FAIL] Step {step} ({blog_key}): 배포 검증 실패 — {e}")
    url, method, file_path = "", "hugo", ""
except BodyExtractionError as e:
    logger.error(f"[PUBLISH-FAIL] Step {step} ({blog_key}): 본문 추출 실패 — {e}")
    url, method, file_path = "", "hugo", ""
except ImageGenerationError as e:
    logger.error(f"[PUBLISH-FAIL] Step {step} ({blog_key}): 이미지 생성 실패 — {e}")
    url, method, file_path = "", "hugo", ""
except Exception as e:
    logger.exception(f"[PUBLISH-FAIL] Step {step} ({blog_key}): 예기치 않은 오류 — {e}")
    url, method, file_path = "", "hugo", ""
```

#### 4-2. `_verify_before_deploy()` 실패 컨텍스트 로깅 (chain_publisher_core.py:691)
**현재**: `logger.error(f"배포 검증 실패: {e}")`만 남기고 빈 튜플 반환.

**변경**:
```python
except DeployValidationError as e:
    logger.error(
        f"배포 검증 실패: {e} | slug={slug} | "
        f"stage={'index.md 검증' if 'index.md' in str(e) else 'HTML 산출물 검증'}"
    )
    return ("", "hugo", "")
```

---

### T5: 단위/통합 테스트 작성 (30분)

#### 5-1. `test_chain_models.py` 확장
```python
class TestParseAIOutputJSONSeparation:
    """parse_ai_output() JSON 메타 분리 검증"""

    def test_code_fence_json(self):
        raw = '''본문입니다.
```json
{"image_type": "photo", "image_keyword": "test"}
```
'''
        out = parse_ai_output(raw)
        assert out.meta.image_type == "photo"
        assert out.meta.image_keyword == "test"
        assert "image_type" not in out.body
        assert "image_keyword" not in out.body

    def test_plain_json_no_fence(self):
        raw = '''본문입니다.
{"image_type": "chart", "chart_type": "bar", "chart_data": {}}
'''
        out = parse_ai_output(raw)
        assert out.meta.image_type == "chart"
        assert out.meta.chart_type == "bar"
        assert "image_type" not in out.body

    def test_indented_multiline_json(self):
        raw = '''본문입니다.
  {
    "image_type": "photo",
    "image_keyword": "test"
  }
'''
        out = parse_ai_output(raw)
        assert out.meta.image_type == "photo"
        assert "image_type" not in out.body

    def test_no_meta(self):
        raw = "본문만 있습니다. JSON 없습니다."
        out = parse_ai_output(raw)
        assert out.meta.image_type == "none"
        assert out.body == "본문만 있습니다. JSON 없습니다."

    def test_broken_json_fallback(self):
        raw = '본문 {image_type: "photo"} 올바르지 않음'
        out = parse_ai_output(raw)
        assert out.meta.image_type == "none"  # 폴백: 기본값
        assert "image_type" in out.body  # 원문 유지

    def test_multiple_json_first_meta_only(self):
        raw = '''본문
{"image_type": "photo", "image_keyword": "first"}
다른 내용
{"image_type": "chart", "chart_type": "bar"}
'''
        out = parse_ai_output(raw)
        assert out.meta.image_type == "photo"  # 첫 번째만
        # 두 번째 JSON은 본문에 잔류 → 2차 방어(_extract_clean_body)가 처리
```

#### 5-2. `test_chain_publisher_core.py` 확장
```python
class TestExtractCleanBodyJSONBlock:
    """_extract_clean_body() 블록 단위 JSON 탐지 검증"""

    def test_indented_json_block_skipped(self):
        raw = '''---
title: "Test"
---
본문입니다.

  {
    "image_type": "photo",
    "image_keyword": "test"
  }

다음 문단입니다.
'''
        cleaned = _extract_clean_body(raw)
        assert "image_type" not in cleaned.body
        assert "image_keyword" not in cleaned.body
        assert "다음 문단입니다" in cleaned.body

    def test_multiple_json_blocks_all_skipped(self):
        raw = '''---
title: "Test"
---
첫 번째 JSON:
{
  "image_type": "photo"
}
중간 텍스트
두 번째 JSON:
{
  "chart_type": "bar",
  "chart_data": {}
}
마지막 텍스트
'''
        cleaned = _extract_clean_body(raw)
        assert "image_type" not in cleaned.body
        assert "chart_type" not in cleaned.body
        assert "첫 번째 JSON" in cleaned.body
        assert "중간 텍스트" in cleaned.body
        assert "마지막 텍스트" in cleaned.body
```

#### 5-3. `test_chain_publisher_core.py` 통합 테스트
```python
class TestPublishHugoWithJSONResidue:
    """_publish_hugo() JSON 잔류 케이스 통과 검증 (mock 사용)"""

    @pytest.mark.asyncio
    async def test_publish_hugo_with_plain_json_in_ai_output(self, tmp_path, monkeypatch):
        """AI 출력에 평문 JSON 포함 시에도 _verify_before_deploy 통과"""
        # mock AI 출력 생성
        raw_ai = '''본문입니다.
{"image_type": "photo", "image_keyword": "test"}
'''
        # _publish_hugo 내부에서 parse_ai_output 호출 → body에 JSON 잔류 없어야 함
        # Hugo 빌드/배포는 mock으로 대체
        ...
```

---

### T6: 전체 테스트 실행 + 회귀 확인 (10분)
- [ ] `pytest -q` → **792 tests 통과** (기존 792 + 신규 테스트 개수만큼 증가)
- [ ] `pytest test_chain_models.py -q` 통과
- [ ] `pytest test_chain_publisher_core.py -q` 통과
- [ ] `pytest test_chain_publisher.py -q` 통과

---

## Wave 1 완료 기준 (Definition of Done for Wave 1)

1. [ ] `pytest -q` → **792 tests 통과** (신규 테스트 포함하여 기존 792 + 신규)
2. [ ] Mocking 테스트에서 `_publish_hugo()` → `_verify_before_deploy()` 통과 검증
3. [ ] `.bak` 파일 4개만 생성, 기타 의도치 않은 파일 변경 없음 (`git status` 확인)
4. [ ] Mocking 테스트에서 `parse_ai_output()` JSON 분리 검증 통과

---

---

# Wave 2: 실제 #378 재발행 (별도 승인 후 실행)

**Wave:** 2 (실제 재발행 — 별도 승인 필요)
**사전 조건:** Wave 1 완료 기준 모두 충족 + 별도 실행 승인

---

---

## 리스크/롤백

```
Wave 1: T1 → T2 → T3 → T4 → T5 → T6
Wave 2: T7 (Wave 1 완료 + 별도 승인 후)
```
- T2, T3는 독립적 → 병렬 가능(동일 파일 수정이 아니므로)
- T4는 T2, T3 완료 후 (로깅 대상 함수 변경 반영)
- T5는 T2, T3 완료 후 (테스트 대상 함수 확정 후)
- T6은 T5 완료 후
- T7은 Wave 1 완료 + 별도 실행 승인 후

---

## 리스크/롤백

| 리스크 | 확률 | 영향 | 완화 | 롤백 |
|--------|------|------|------|------|
| JSON 탐지 과탐(일반 텍스트를 JSON으로 오인) | 낮 | 정상 텍스트 삭제 | `"image_type"/"chart_type"` 키 존재 조건 필수 + `json.loads()` 검증 | `git checkout chain_publisher_core.py` |
| JSON 탐지 미탐지(깊은 중첩/이상한 형식) | 낮 | 잔류 JSON 통과 | 2차 방어(`_extract_clean_body`)가 안전망 | 동일 |
| `_extract_body_from_raw()` 인덱스 시프트로 본문 손상 | 낮 | 본문 잘림 | 역순 삭제(sorted reverse) + 단위 테스트 | `git checkout chain_models.py` |
| 반환 규약 변경으로 호출부 오류 | 없음 | - | 반환 타입/규약 불변(위 표 검증) | N/A |
| 테스트 플래키 | 낮 | CI 실패 | mock 고정, 외부 의존성 제거 | 테스트 수정 |

**백업 파일**: T1에서 생성한 `*.bak` 4개로 즉시 복구 가능.

---

## 완료 기준 (Definition of Done)

### Wave 1 완료 기준
1. [ ] `pytest -q` → **792 tests 통과** (신규 테스트 포함하여 기존 792 + 신규)
2. [ ] Mocking 테스트에서 `_publish_hugo()` → `_verify_before_deploy()` 통과 검증
3. [ ] `.bak` 파일 4개만 생성, 기타 의도치 않은 파일 변경 없음 (`git status` 확인)
4. [ ] Mocking 테스트에서 `parse_ai_output()` JSON 분리 검증 통과

### Wave 2 완료 기준 (별도 승인 후)
1. [ ] Chain #378 `--publish` → Step 1/2/3 모두 `✅ Step X published: <url>` 출력
2. [ ] 배포 검증 통과: 로그에 `배포 검증 실패` 없음, `json_residue` 에러 없음
3. [ ] 카드 주입 정상: `✅ Step 1 next card injected`, `✅ Step 2 next card injected`, `✅ Step 3 external link card injected`
4. [ ] 3개 블로그(rotcha, issue.techpawz, techpawz) 모두 `wrangler pages deploy` 성공
5. [ ] `.bak` 파일 4개만 생성, 기타 의도치 않은 파일 변경 없음 (`git status` 확인)

---

**승인 대기 중 — 실행하지 않음** (Wave 1만 승인 대기, Wave 2는 별도 승인)