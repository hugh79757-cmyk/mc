---
date: 2026-08-17
type: release-quality
status: resolved
---
# Terra Tomato Beer 9-point Quality Release

## What
테라 토마토 맥주 체인 포스트의 세 블로그 역할을 분리하고 사실 기반·독자 중심 본문과 제목을 적용했다. rotcha는 제품 개요와 첫 선택 기준, issue.techpawz는 일반 라거와의 비교, techpawz는 가격·재고 확인과 구매 체크리스트를 담당한다.

## Root Causes and Fixes
rotcha 라이브가 개선 전 배포본을 제공해 로컬 완성 산출물을 Wrangler로 직접 재배포했다. issue.techpawz는 `chain-card` shortcode 누락으로 빌드가 실패해 `layouts/shortcodes/chain-card.html`을 복구했다. techpawz는 어둡고 흑백인 숲 썸네일을 밝은 토마토 탄산 음료 이미지 `/images/terra-sparkling-tomato-s3.png`로 교체했다. 사용자 절대 테마 경로 문제는 저장소 설정 변경 없이 빌드 시 임시 경로를 주입해 해결했다.

## Changes and Verification
485mL, 토마토 맛 4.6도, 화이트와인 베이스 과실 탄산주와 일반 라거의 차이를 표·체크리스트로 정리했다. 확인되지 않은 가격을 최저가로 단정하지 않고 판매처별 가격·행사·재고 확인 절차로 전환했다. rotcha→issue.techpawz→techpawz 카드 CTA를 보존하고 마지막 CTA는 하이트진로 공식 사이트로 연결했다. Hugo 빌드는 rotcha 19,180 files, issue 4,461 files, techpawz 썸네일 반영 후 9,938 files이며 세 Cloudflare Pages 프로젝트 배포와 라이브 검증을 완료했다.

## Commits
| Repository | Commit |
|---|---:|
| rotcha-blog | e10b0cb |
| issue-techpawz-hugo | 2d9b7a0 |
| techpawz-hugo | 8bbd196b |
| mc | this triage record |

## Final assessment
콘텐츠·제목·CTA·썸네일 품질이 9/10 목표를 충족했다.
