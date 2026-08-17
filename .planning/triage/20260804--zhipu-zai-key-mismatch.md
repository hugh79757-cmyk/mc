---
date: 2026-08-04
type: config
status: resolved
---

# Zhipu AI API 키 환경변수명 불일치 수정

## What
`config/models.yaml`의 zhipu provider가 `ZAI_API_KEY`를 참조했지만, 실제 `~/.env.common`에 등록된 키 이름은 `ZHIPU_API_KEY`. 16번째 tier(GLM 4.5 Flash)가 "API 키 없음"으로 즉시 스킵되는 버그.

## Why
LLM 폴백 체인(17개 모델) 구현 시 zhipu provider의 `api_key_env` 값을 잘못 지정. LLM_FALLBACK_CHAIN.md 문서에는 `ZHIPU_API_KEY`로 기록되어 있었으나, models.yaml에는 `ZAI_API_KEY`로 불일치.

## Files changed
- `/Users/twinssn/Projects/5000/config/models.yaml` — `api_key_env: ZAI_API_KEY` → `api_key_env: ZHIPU_API_KEY`

## How
models.yaml zhipu provider 섹션의 `api_key_env` 값을 `ZAI_API_KEY`에서 `ZHIPU_API_KEY`로 수정. LLM_FALLBACK_CHAIN.md는 이미 올바르게 `ZHIPU_API_KEY`로 기록되어 있어 변경 불필요.

## Verification
- `python -c "from shared import env_loader; import os; print(os.getenv('ZHIPU_API_KEY'))"` → 키 값 정상 출력 확인
- `mc run --dry-run` → 정상 동작 확인
- 전체 tier api_key_env 매핑 검증: 7개 프로바이더 환경변수 전부 `~/.env.common`과 일치 확인
