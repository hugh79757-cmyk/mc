# CONTEXT.md — Phase 24: YAML Frontmatter Structural Fix

## Background

현재 시스템은 **AI 모델에게 YAML frontmatter 작성을 직접 위임**하고, 이후 `_ensure_frontmatter()`에서 사후 보정하는 구조입니다. 이로 인해 AI가 `---` 블록 바깥에 `title:`/`description:`/`tags:`/`categories:` 등을 출력하는 **frontmatter 누수(FM leak)** 버그가 주기적으로 발생합니다.

### Threads JSON 해결 사례

이전에 Threads 자동화에서는 `response_format={"type": "json_object"}`로 **모델 출력 형식을 구조적으로 강제**하여 JSON 줄바꿈 문제를 근절했습니다. "모델에게 형식을 맡기지 말고 코드가 제어하자"는 접근이 효과를 입증했습니다.

### 현재 구조의 문제점

| 영역 | 현재 방식 | 문제 |
|------|----------|------|
| 프롬프트 | `draft_system`에 `[Frontmatter — 필수]` 섹션 포함 (`---\ntitle:...\ndescription:...\ndraft: false\ntags:[...]\ncategories:[...]\n---`) | AI가 FM 형식을 실수함 |
| 생성 | AI가 FM + body를 한 번에 출력 | `---` 닫는 위치 혼동, YAML 필드 누출 |
| 사후 보정 | `_ensure_frontmatter()`가 패턴 매칭으로 FM 수리 | 방어적이지만 근본 해결 아님 |
| 발행 | `_publish_hugo()`가 FM을 **완전히 재생성** (AI의 title/tags/categories 무시) | AI가 생성한 FM이 사실상 무시됨 |

### 핵심 인사이트

**AI가 생성한 FM 필드(title/tags/categories)는 발행 시 전부 무시되고 DB 값으로 대체된다.** 즉, AI에게 FM 작성을 시키는 것은:
1. 모델 출력 길이 낭비 (토큰 소모)
2. FM 누수 버그 발생 (수익/안정성 리스크)
3. 사후 보정 코드 복잡성 증가 (`_ensure_frontmatter` 90라인+)
4. 유일하게 살아남는 `description`만 따로 처리 가능

### 구조적 해결 방안

AI에게 **body content만 생성**하게 하고, FM은 **코드에서 직접 조립**합니다.

```
변경 전:
  AI: [FM + body] → _ensure_frontmatter() → ... → _publish_hugo() [FM 재생성]

변경 후:
  AI: [body only] → [코드에서 FM 조립 + body 결합] → _publish_hugo() [FM 재생성 (변경 없음)]
```

### 적용 대상 파일

| 파일 | 변경 범위 | 비고 |
|------|----------|------|
| `config/prompts.yaml` | `draft_system`에서 `[Frontmatter — 필수]` 섹션 제거 | AI가 FM을 출력하지 않게 |
| `chain_drafter.py` | `_ensure_frontmatter()` 단순화, FM 코드 조립 로직 이관 | `draft_chain()`에서 FM 조립 |
| `chain_models.py` | 변경 없음 | `parse_ai_output()`은 FM 무관하게 동작 |
| `chain_publisher_core.py` | 변경 불필요 | 이미 FM을 재생성함 |
| `test_chain_drafter.py` | `TestEnsureFrontmatter` 케이스 업데이트 | 단순화된 동작 반영 |

### 검증 기준

1. 기존 362개 테스트 전부 통과
2. `_ensure_frontmatter()`가 단순화되었음 (더블 FM 병합 로직 제거)
3. AI가 FM을 출력해도 `strip_leaks`/`parse_ai_output`가 정상 동작
4. 실제 chain draft 생성 시 schema validation 통과
5. 발행된 글의 FM이 정상 (기존과 동일한 형식)

### 리스크

- `strip_leaks`가 FM이 없는 body를 예상대로 처리하는지 확인 필요
- `parse_ai_output._extract_body_from_raw()`가 FM 없이도 정상 동작하는지 확인
- 일부 AI 모델이 지시를 무시하고 여전히 FM을 출력할 경우 → `_ensure_frontmatter()`가 안전장치로 처리
