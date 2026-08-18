# RESEARCH: Phase 45 — HTML 렌더링 중복 검사

## 기존 코드베이스 분석

### 1. HTML 렌더링 파이프라인

```
CardGenerator.generate_card() → card_spec dict
    → HtmlRenderer.render(spec) → HTML string
        → chain_card_injector.inject() → 최종 본문에 삽입
```

`html_renderer.py`는 상태 없는 순수 렌더러. `spec["type"]`으로 디스패치:
- `next`/`internal` → `_render_chain_card()` → `{{< chain-card >}}`
- `official` → `_render_official_card()` → `{{< chain-official-card >}}`
- `external` → `_render_external_card()` → HTML div

### 2. 기존 형식 검증 (audit_format.py)

| 함수 | 검증 항목 |
|------|----------|
| `check_card_count(body, depth)` | 카드 수 (D0/D1: max 2, D2: max 1) |
| `check_card_placement(body, depth)` | 카드 위치 (H2 기준) |
| `check_crosslinks(body, depth)` | 크로스링크 URL 정확성 |
| `check_h2_structure(body, depth)` | H2 구조 (템플릿 대비) |

**재사용 가능:** `check_card_count`, `check_card_placement`를 그대로 사용.

### 3. Hugo 빌드 (chain_publisher_core.py:842-854)

```python
result = subprocess.run(
    ["hugo", "--gc", "--minify"],
    cwd=hugo_site_path, capture_output=True, text=True, timeout=120
)
```

빌드 후 `public/` 디렉토리에서 HTML 파일 생성. 이 HTML을 파싱해야 중복 검증 가능.

### 4. BeautifulSoup 사용

기존 의존성에 BeautifulSoup이 있는지 확인 필요. `pyproject.toml` 또는 `requirements.txt` 확인.

## 통합 지점

1. **html_render_checker.py**: `check_html_duplicates(html_content) -> HtmlRenderResult`
2. **quality_gate.py**: `validate_html_render(html_content) -> GateResult`
3. **audit_format.py 연동**: 기존 check 함수 재사용

## 검증 대상

| 중복 유형 | 탐지 방법 |
|----------|----------|
| 동일 문단 반복 | 동일 텍스트가2회 이상 |
| 동일 이미지 반복 | 동일 src가2회 이상 |
| chain-card 중복 | `{{< chain-card`가 의도보다 많이 렌더링 |
| CTA 블록 반복 | "더 알아보기"가2회 이상 |
| 외부링크 카드 중복 | HTML div가2회 이상 |

## 리스크

- BeautifulSoup 의존성 추가 필요 → 기존 의존성 목록 확인
- Hugo 빌드 없이 HTML 검증 불가 → 빌드 후 검증 파이프라인 연결
- Hugo 빌드 시간 증가 → `--quick` 모드에서 빌드 스킵 가능하도록

## 권장 사항

1. BeautifulSoup4 사용 (이미 설치되어 있을 가능성 높음)
2. Hugo 빌드 후 `public/`에서 해당 HTML 파일 읽어서 검증
3. `audit_format.py`의 기존 check 함수를 `quality_gate.py`에서 래핑
