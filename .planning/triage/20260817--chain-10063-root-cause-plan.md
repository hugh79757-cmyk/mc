---
date: 2026-08-17
type: incident-analysis
status: plan-ready
chain_id: 10063
---
# Chain 10063 발행 실패 원인 분석 및 수정 플랜

## 조사 결론

첨부 로그의 직접 실패는 Hugo가 `테라-토마토-맥주-20260817-s1/s2/s3/index.md`를 읽다가 frontmatter를 파싱하지 못한 것이다. 그러나 실행 키워드는 `남양주 물의 정원`이었다. 따라서 단순한 남양주 콘텐츠 품질 문제가 아니라, **새 체인의 산출물과 이전 Terra Tomato 파일·DB 상태가 발행 대상에 섞인 상태 오염**이 먼저 의심된다.

로그는 세 단계 모두 `[PUBLISH-FAIL]`을 출력했지만 이후 `publish complete`, `Chain #10063 completed`, `no published_url — skipping`을 출력했다. 이는 실패 집계와 smoke-test가 성공을 잘못 보고하는 별도 결함을 확정한다.

## 코드 근거

`chain_publisher.py:477-499`는 단계별 예외를 포착하고 post 상태를 `failed`로 바꾸지만, `:501-502`에서 URL이 하나도 없는 경우에도 chain 상태를 무조건 `published`로 바꾸고 완료를 출력한다. `:554-575`의 카드 주입은 Step 1·2의 next URL이 없으면 건너뛰지만, 마지막 Step 3 외부 링크 카드는 앞 단계 발행 성공 여부와 무관하게 주입한다. `:657-729`의 smoke test는 `published_url`이 없는 포스트를 실패로 기록하지 않고 건너뛴다. `run_chain()`은 `:892-898`에서 이 모든 결과를 확인하지 않고 카드 주입과 smoke test를 이어 간 뒤 `:922-923`에서 완료를 출력한다.

`cli/mc.py:168-186`은 `run_chain()`이 chain ID만 반환하면 성공으로 기록한다. `:264-287`의 resume도 URL이 남아 있지 않은 경우 경고만 출력하고 0을 반환한다. `:385-415`의 auto 모드는 동일하게 truthy chain ID만 보고 큐를 성공 처리한다.

`chain_publisher_core.py:684-741`은 frontmatter를 YAML 파서가 아니라 줄 단위 정규식으로 분리·재조립한다. `:842-854`는 전체 Hugo 빌드를 실행하며, 사이트 안의 이전 깨진 파일 하나가 현재 포스트의 배포를 막을 수 있다. `:856-867`의 검증 실패는 빈 반환값으로 축약된다. 또한 `:521-524`는 `slug`만으로 `chain_posts`의 이미지 메타를 조회하므로 공유 DB 또는 slug 충돌 시 다른 체인의 이미지가 연결될 위험이 있다.

`chain_drafter.py`는 현재 seed keyword로 slug를 결정하는 구조이므로, 새 slug가 derive 단계에서 직접 Terra Tomato로 바뀌었다고 단정하기보다는 publish 대상 조회·공유 DB·stale 파일 정리 경로를 우선 조사해야 한다. `chain_publisher_core._write_stage_log()`는 stdout/stderr를 별도 로그 파일에 기록하므로 로그 자체가 Markdown에 직접 쓰였다는 증거는 없다. 셸 명령 조각은 raw AI output, frontmatter 조립 입력, 또는 이전 오염 파일 중 하나에서 유입됐는지 원본과 최종 파일을 대조해야 한다.

## 외부 문서 교차검증

Hugo 공식 문서에 따르면 frontmatter는 JSON·TOML·YAML 중 하나의 직렬화 형식이어야 하며 구분자에 따라 형식을 판정한다.[1] 따라서 `;`, 셸 명령, 임의 텍스트가 frontmatter 경계 안에 들어가면 빌드 전에 파싱 차단해야 한다. Hugo 공식 page bundle 문서는 `content/<slug>/index.md`를 leaf bundle로 설명한다.[2] Hugo 공식 content organization 문서는 파일 경로와 frontmatter의 `slug`가 결과 URL을 결정한다고 설명한다.[3] 그러므로 DB slug, 디렉터리 slug, frontmatter slug, 예상 canonical URL을 같은 체인 ID 기준으로 묶어 검증해야 한다.

## 수정 플랜

### Wave 0 — 안전한 상태 고정

체인 10063을 `failed` 또는 `blocked`로 명시하고 `--resume`을 실행하지 않는다. 생성된 `남양주` 포스트의 DB `chain_id`, `seed`, `step`, `slug`, `draft_md`, `published_md`, `published_url`, `status`, `error_log`를 조회하고, 세 Hugo 저장소에서 Terra 경로와 남양주 경로를 함께 목록화한다. Git 추적 파일은 삭제하지 말고, 오염 파일의 원본·현재 내용을 별도 진단 로그로 보존한다. 수정 전 MC와 사이트 저장소를 깨끗한 커밋 상태로 만든다.

### Wave 1 — 체인 격리 게이트

발행 직전에 각 post에 대해 `post.chain_id == requested_chain_id`, `post.target_keyword == chain.seed`, `slug == build_slug(chain.seed, step)`, `slug`의 키워드 토큰이 현재 seed와 일치하는지 검증한다. `PublisherCore.publish_post()`에 `post_id`를 필수 전달하고 image metadata 조회를 `WHERE id = ? AND chain_id = ?`로 바꾼다. 대상 디렉터리의 기존 `index.md`가 다른 chain ID 또는 다른 seed의 marker를 가지고 있으면 overwrite하지 않고 `DeployValidationError`로 차단한다.

### Wave 2 — frontmatter 안전 조립

줄 단위 frontmatter 재조립을 YAML 파싱 기반으로 교체한다. 저장 직전 `yaml.safe_load`로 전체 frontmatter를 파싱하고, 필수 필드 `title`, `description`, `draft`, `slug`, `date`의 타입과 값을 검증한다. frontmatter opener/closer가 정확히 한 쌍인지, opener 뒤에 셸 명령·로그 접두사·JSON fence·제어문자가 없는지 검사한다. 실패하면 Markdown 파일을 운영 경로에 쓰지 않고 raw output과 오류만 저장한다. `draft_md`와 최종 `index.md`를 모두 같은 validator로 검사한다.

### Wave 3 — 실패 집계와 부작용 차단

`publish_chain()`이 `step_results`를 반환하도록 바꾸고, 세 단계 모두 `url`, 파일 검증, 배포 검증이 성공한 경우에만 chain status를 `published`로 바꾼다. 하나라도 실패하면 chain status를 `failed` 또는 재시도 가능한 경우 `partial_failed`로 저장하고 예외/결과를 상위로 전달한다. 실패한 chain에는 카드 주입, 카드 후 재배포, 성공 알림을 실행하지 않는다. Step 3 외부 CTA도 세 포스트의 선행 발행이 성공한 경우에만 주입한다.

### Wave 4 — smoke test와 CLI/queue 계약 수정

`smoke_test()`는 `published_url` 없는 포스트를 `skipped`가 아니라 `fail`로 기록하고, 세 포스트 결과가 모두 pass일 때만 chain 완료를 반환한다. 각 URL에 대해 HTTP 200, title, expected slug, `og:image` 200, CTA card, AdSense marker를 검사한다. `_run_full`, `_resume_chain`, `_cmd_auto`는 chain ID 반환 여부가 아니라 최종 `chain.status`와 포스트별 결과를 사용한다. 부분 실패는 exit code 1과 `mark_failed`로 전달하고 성공 알림을 금지한다.

### Wave 5 — 테스트와 안전한 재실행

다음 회귀 테스트를 먼저 추가한다.

| 테스트 | 기대 결과 |
|---|---|
| 하나의 post publish 실패 | chain은 `failed/partial_failed`, 완료 문구·성공 알림 없음 |
| 세 post 모두 publish 실패 | 카드 주입·후속 deploy·smoke 성공 처리 없음 |
| published_url 없는 smoke test | 결과에 fail 기록, exit code 1 |
| `chain_id`/seed/slug 불일치 | Hugo 쓰기 전 즉시 차단 |
| 다른 chain의 동일 slug 이미지 조회 | 현재 post ID·chain ID만 조회 |
| 오염 frontmatter | 파일 저장·Hugo 실행 모두 차단 |
| stale Terra 파일이 있는 사이트 | 남양주 발행은 충돌을 명시적으로 보고하고 자동 overwrite 금지 |
| 정상 3단계 발행 | 카드 주입 후 세 URL smoke test pass일 때만 completed |
| resume 부분 실패 | 경고만 하고 0을 반환하지 않으며 실패 코드 반환 |
| auto queue 부분 실패 | `mark_done`이 아니라 `mark_failed` |

수정 후에는 먼저 `derive-only`와 draft/schema 검증만 실행한다. 그 다음 테스트용 격리 site root에서 남양주 물의 정원 체인을 publish하고 세 URL·slug·frontmatter를 검증한다. 마지막으로 운영 발행은 새 chain ID로 승격하며, 각 단계 결과를 확인한 뒤 다음 단계로 넘어간다. 실패하면 같은 chain ID의 실패 단계만 재개하고, 새 키워드에 이전 chain ID의 `--resume`을 사용하지 않는다.

## 우선순위

가장 먼저 고칠 것은 false-success다. 실패를 성공으로 기록하는 동안에는 어떤 콘텐츠 수정도 운영 신뢰성을 회복하지 못한다. 그 다음 chain isolation과 frontmatter validator를 적용하고, 마지막으로 stale 파일 처리 정책과 전체 사이트 빌드 격리 전략을 정한다. 전체 Hugo 빌드를 유지하되, 대상 파일의 사전 검증과 사이트 baseline build를 분리해 “기존 stale 파일 때문에 신규 발행이 실패”하는 경우를 원인별로 보고한다.

## References

[1]: https://gohugo.io/content-management/front-matter/ "Hugo Front matter"
[2]: https://gohugo.io/content-management/page-bundles/ "Hugo Page bundles"
[3]: https://gohugo.io/content-management/organization/ "Hugo Content organization"
