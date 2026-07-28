# CONTEXT.md — Phase 30: audit_format.py gap closure

**Phase:** 30
**Created:** 2026-07-28
**Mode:** gap_closure (from Phase 29 VERIFICATION.md)

## Objective

Phase 29에서 생성한 `audit/audit_format.py`의 계약 미이행 3건을 해소한다.
검증 전용 스크립트를 완성하여, 블로그 형식/외형 검증이 계약된 10개 항목 전부를 커버하도록 한다.

## Gap Source: Phase 29 VERIFICATION.md

Phase 29 실행 후 self-audit에서 발견한 3건:

| # | 계약 (must_haves) | 약속된 함수 | P29 상태 | P30 해소 |
|---|-------------------|------------|---------|---------|
| 1 | "Hugo build completes without errors for all 3 sites" | `check_hugo_build(site_name, site_path, skip=False)` | 미구현 | 구현 |
| 2 | "og:image, 카드 HTML 렌더링" | `check_html_render(site_path, slug, label)` | 부분구현 (원시마크다운만) | og:image + card 렌더링 검증 추가 |
| 3 | "HTTP 200 확인" | `check_live_access(published_url, label)` | 미구현 | 구현 |

## 수정 대상 파일

| 파일 | 수정 내용 |
|------|----------|
| `audit/audit_format.py` | 3개 함수 추가 + scan 함수 통합 + CLI 업데이트 |
| `test_audit_format.py` | 3개 함수 단위테스트 추가 |

## 기존 코드 참고

### audit_chain.py의 check_hugo_build (재사용 패턴)
```python
def check_hugo_build(skip: bool = False) -> list:
    hugo_bin = shutil.which("hugo") or "/opt/homebrew/bin/hugo"
    for name, site in HUGO_SITES.items():
        build = subprocess.run(
            [hugo_bin, "--gc", "--minify"],
            cwd=str(site["path"]),
            capture_output=True, text=True, timeout=120,
        )
        # returncode != 0 → fail, warnings → warn
```

### audit_format.py의 HUGO_SITES (이미 존재)
```python
HUGO_SITES = {
    "rotcha": {"path": Path("/Users/twinssn/Projects/rotcha-blog"), "output_prefix": "posts/"},
    "issue.techpawz": {"path": Path("/Users/twinssn/Projects/issue-techpawz-hugo"), "output_prefix": ""},
    "techpawz": {"path": Path("/Users/twinssn/Projects/techpawz-hugo"), "output_prefix": ""},
}
```

### Hugo 빌드 시 필수 환경변수
```bash
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify
```

## 제약 조건

- 기존 10개 함수의 시그니처 변경 금지 (additive only)
- `--dry-run` 플래그가 Hugo 빌드/라이브 검증을 스킵하도록 유지
- `--chain-id` / `--all` CLI 인터페이스 유지
- test_audit_format.py의 기존 39개 테스트 깨뜨리지 않음
