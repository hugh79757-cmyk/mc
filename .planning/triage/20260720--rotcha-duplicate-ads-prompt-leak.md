---
date: 2026-07-20
type: fix
status: fixed
---

# rotcha.kr 광고 2개 + 프롬프트 릭 수정

## What
- `single.html`에 `adsense/in-article.html` partial이 두 번 삽입되어 타이틀 상단에 광고가 2개 연속으로 렌더링되던 중복
- `chain_drafter.py`에서 GPT가 system prompt 일부를 그대로 반환하면 `result["content"]`에 섞여 DB/sanitization 없이 저장되는 prompt leak

## Why
- `layouts/_default/single.html:17` 에 `{{ partial "adsense/in-article.html" . }}` 가 단독 삽입되어 있었고
- 동일 partial이 `layouts/partials/content-with-ads.html:9` 에도 `{{ partial "adsense/anchor-above-title.html" $ }}` 형태로 삽입되어 있었다
- `chain_drafter.py`의 `draft_single_post()`는 `result["content"]`를 바로 `draft_md`로 사용하므로, GPT가 prompt 템플릿을 그대로 반복한 경우 본문 앞에 노출됨

## Files changed
- `/Users/twinssn/Projects/rotcha-blog/layouts/_default/single.html` — 중복 partial 삭제 (라인 16-18)
- `/Users/twinssn/projects2/mc/chain_drafter.py` — `_strip_prompt_leak()` 추가 + `draft_md = _strip_prompt_leak(draft_md)` 호출 추가

## How
- single.html 에서 `{{ partial "adsense/in-article.html" . }}` 블록을 완전히 제거하고 `{{/* Header */}}` 바로 위로 `content-with-ads.html`(anchor)만 남김
- chain_drafter.py 마지막에 `_PROMPT_LEAK_RE` 정규식 + `_strip_prompt_leak()` 함수 정의 후 chart JSON 파싱 직후에 호출하여 알려진 prompt 헤더 줄을 모두 제거

## Verification
- Hugo build 후 `layouts/_default/single.html`에 `in-article.html` partial이 1회만 호출되는지 확인
- 새로 발행되는 draft에서 `# Role (역할)` `# SEO 기본 원칙` `# Frontmatter Rules` 등 prompt 헤더가 본문 앞에 없음 확인
