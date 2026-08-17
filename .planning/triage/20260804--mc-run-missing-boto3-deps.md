---
date: 2026-08-04
type: fix
status: resolved
---

# mc run 의존성 누락 수정 (boto3, python-slugify, python-frontmatter)

## What
`mc run <keyword>` 실행 시 `ModuleNotFoundError: No module named 'boto3'` 오류로 즉시 실패. `requirements.txt`와 `pyproject.toml`에 `boto3`, `python-slugify`, `python-frontmatter`, `python-dotenv`가 누락되어 있었음.

## Why
- `image/r2_uploader.py:10`에서 `import boto3`를 사용하나, `requirements.txt`에 `boto3`가 없었음
- `requirements.txt`에 `python-slugify`와 `python-frontmatter`가 기록되어 있었으나 실제 환경에 설치되지 않았음
- `python-dotenv`는 `r2_uploader.py:13`에서 사용되나 `requirements.txt`에 없었음
- `requirements.txt`에 `python-frontmatter>=1.0.0`이 중복 기록(7행, 8행)되어 있었음

## Files changed
- `/Users/twinssn/projects2/mc/requirements.txt` — boto3, python-dotenv 추가 + 중복 python-frontmatter 제거
- `/Users/twinssn/projects2/mc/pyproject.toml` — boto3, python-dotenv dependencies에 추가

## How
1. `requirements.txt`에서 중복된 `python-frontmatter` 라인 제거
2. `boto3>=1.34.0`과 `python-dotenv>=1.0.0`을 `requirements.txt`에 추가
3. `pyproject.toml`의 `dependencies` 리스트에 동일 패키지 추가
4. `pip install boto3 python-slugify python-frontmatter python-dotenv` 실행

## Verification
- `python -c "from chain_publisher import run_chain; print('Import OK')"` → `[publisher] image/ package loaded (local file download)` + `Import OK` 출력 확인
- `python -m cli.mc run "테스트키워드" --dry-run` → Chain #10021 생성, 3개 포스트 파생, 4.6초 완료
- `python -m pytest test_chain_publisher_core.py test_chain_drafter.py test_chain_deriver.py` → 175개 테스트 통과 (4.09s)
- 핵심 모듈 12/12 임포트 정상
