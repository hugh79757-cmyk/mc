# Triage Index

- 2026-08-17 | release-quality | terra-tomato-quality-release | Terra Tomato Beer 세 블로그 9점 품질 릴리스, Hugo 3/3 빌드·Cloudflare Pages 직접 배포·라이브 검증 완료
- 2026-08-04 | fix | mc-run-missing-boto3-deps | mc run 의존성 누락 수정 (boto3/python-slugify/python-frontmatter/python-dotenv), requirements.txt+pyproject.toml 업데이트
- 2026-08-04 | config | zhipu-zai-key-mismatch | Zhipu AI API 키 env var 불일치 수정 (ZAI_API_KEY→ZHIPU_API_KEY), tier 16 GLM 4.5 Flash 스킵 버그 해결
- 2026-07-30 | refactor | fm-structural-fix-and-card-cta | Phase 24 FM 분리 (AI→코드 조립) + 외부 링크 카드 CTA 동적화. _ensure_frontmatter 91→23라인, 378 tests ✅
- 2026-07-22 | fix | r2-thumb-upload-fix-phase12 | R2 썸네일 업로드 버그 수정 + mc 업로더 분리 (Phase 12 실행)
- 2026-07-21 | fix | fm-bug-fix-and-guard | FM 버림(no-FM 404) 버그 수정, 6페이지 재발행, 재발 방지 가드(_NON_INTENDED_CHAINS) 구현
- 2026-07-20 | fix | r2-techpawz-thumbnail-fixes | img.rotcha.kr/img.informationhot.kr → hotissue-images, img.techpawz.com → techpawz-images 복원, 썸네일·발행 sanitization 복합 수정
- 2026-07-20 | fix | rotcha-duplicate-ads-prompt-leak | 타이틀 상단 광고 2개 연속 렌더링 원인(template 중복 partial) 수정, GPT prompt leak 방지 필터 추가
