# RESEARCH: Phase 41 — 산출물 계약서 YAML

## 기존 코드베이스 분석

### 1. 검증 패턴 (audit/audit_chain.py)

기존 `audit_chain.py`는 다음 검증 함수들을 제공:

| 함수 | 역할 | 리턴 |
|------|------|------|
| `check_prompt_leak(body)` | 프롬프트 릭 탐지 | `list[dict]` — findings |
| `check_unresolved_markers(body)` | 미해소 마커 탐지 | `list[dict]` |
| `check_cta_leak(body)` | AI CTA 블록 탐지 | `list[dict]` |
| `check_featureimage_url(fm)` | featureimage URL 검증 | `list[dict]` |
| `check_content_by_whitelist(body)` | 허용 마크다운만 통과 | `list[str]` |
| `check_images_exist(body)` | R2 이미지 존재 확인 | `list[dict]` |

**핵심 패턴:** 모든 검증 함수가 `list[dict]`를 반환하고, findings가 비어있으면 통과. `label` 파라미터로 포스트 식별.

### 2. 형식 검증 (audit/audit_format.py)

Phase 29에서 추가된 검증:

| 함수 | 역할 |
|------|------|
| `check_card_count(body, depth)` | 카드 수 검증 (D0/D1: max 2, D2: max 1) |
| `check_card_placement(body, depth)` | 카드 위치 검증 (H2 기준) |
| `_load_step_sections()` | prompts.yaml에서 category별 H2 템플릿 로드 |
| `_extract_keyword_from_template(tpl)` | H2 템플릿에서 시맨틱 패턴 추출 |

**D0→rotcha, D1→issue.techpawz, D2→techpawz** 매핑: `DEPTH_TO_SITE = {0: "rotcha", 1: "issue.techpawz", 2: "techpawz"}`

### 3. 계약 모델 (chain_models.py)

기존 패턴:
- `DeployValidationError(PipelineError)` — 배포 전 검증 실패
- `Result` dataclass — ok/value/error 패턴
- pydantic BaseModel 사용 (AIOutputMeta 등)

**재사용 가능 패턴:** `GateResult`를 `Result`와 유사하게 설계하되, `violations` 리스트를 추가.

### 4. 프롬프트 릭 방어 (config/leak_defense.yaml)

YAML 구조:
```yaml
prompt_leak:
  patterns: [regex list]
  action: "remove_block"
reasoning_leak:
  min_signals: 2
  patterns: [low-specificity]
  ultra_high_signals:
    min_signals: 1
    patterns: [high-specificity]
```

**계약서 YAML도 동일한 구조 사용 가능:** patterns, required_sections, forbidden_sections 등.

## 통합 지점

1. **contract_loader.py**: `config/` 디렉토리에 `contracts/*.yaml` 저장. `yaml.safe_load()`로 로드.
2. **quality_gate.py**: `audit_chain.py`의 findings 패턴을 재사용. `GateResult(passed, violations)` 반환.
3. **기존 audit 통합**: `audit_chain.py` `run_all_checks()`에 계약 검증 추가 가능.

## 리스크

- YAML 계약서가 너무 엄격하면 기존 유효한 콘텐츠 거부 → 관대하게 시작
- 사이트별 계약서 차이가 미세하면 동일 계약으로 시작 후 분리

## 권장 사항

1. `contracts/` 디렉토리를 `config/` 아래에 생성
2. `Contract` dataclass에 `required_sections`, `forbidden_patterns`, `title_pattern` 포함
3. `quality_gate.py`에서 `validate_contract(post_md, contract) -> GateResult` 구현
4. `GateResult`에 `violations: list[Violation]` — 각 Violation에 `rule`, `detail`, `severity` 포함
