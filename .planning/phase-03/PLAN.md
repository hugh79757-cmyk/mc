# Phase 3 Plan: 역순 발행 + 카드 주입 + 스케줄러

**Phase:** 3
**Mode:** sequential (3 waves)
**Estimated tasks:** 8

## Wave 1: DB + Config 확장 (Tasks 3-1 ~ 3-2)

### Task 3-1: chain_db.py 스키마 확장

**파일:** `chain_db.py` (수정)
**의존성:** 없음

**변경사항:**
- chain_posts 테이블에 추가 컬럼:
  - `published_url TEXT`
  - `published_at TIMESTAMP`
  - `card_injected BOOLEAN DEFAULT 0`
  - `card_injected_at TIMESTAMP`
  - `publish_method TEXT`  -- 'hugo' | 'blogger' | 'manual' | 'manual_pending'
- MIGRATIONS_SQL에 Phase 3 컬럼 추가

**추가 메서드:**
- `update_published_url(post_id, url, method)` — published_url + publish_method 저장
- `update_card_injected(post_id)` — card_injected = 1, card_injected_at = now
- `get_chain_posts(chain_id, order_by='step', direction='asc')` — 정순/역순
- `get_pending_card_injections(chain_id)` — published_url IS NOT NULL AND card_injected = 0

### Task 3-2: config/chain_config.yaml 발행 설정 추가

**파일:** `config/chain_config.yaml` (수정)
**의존성:** 없음

**변경사항:**
- 각 site 블록에 `publisher_type`, `card_cta` 추가
- 새 site 등록: `2_techpawz` (blogger), `65_informationhot` (blogger)
- `chain_blog_mapping` 추가: direction별 기본 step-to-blog 매핑
- `publish_mode` 섹션 추가
- 기존 sites → blogs 통합 또는 분리 (기존 rotcha/infohot/techpawz 와 blogger 사이트 모두 포함)

## Wave 2: 발행 + 카드 모듈 (Tasks 3-3 ~ 3-5)

### Task 3-3: shared/publishers/blogger_client.py 신규

**파일:** `shared/publishers/blogger_client.py` (신규, 5000 프로젝트)
**의존성:** google-api-python-client, google-auth-oauthlib, google-auth

**구현:**
- `BloggerClient` 클래스
- `_get_service()` — OAuth2 인증 흐름 (token.pickle 재사용)
- `publish_post(blog_id, title, html_content, labels, is_draft)` → URL
- `update_post(blog_id, post_id, html_content)`
- `get_post_by_url(blog_id, url)` → post_id
- SCOPES = ['https://www.googleapis.com/auth/blogger']
- 첫 실행 브라우저 인증, 이후 token.pickle 캐싱
- credentials는 config/blogger_credentials.json

### Task 3-4: chain_publisher_core.py 신규

**파일:** `chain_publisher_core.py` (신규, mc)
**의존성:** Task 3-1, 3-2, 3-3

**클래스:** `PublisherCore`
- `publish_post(blog_key, draft_md, slug, title, labels)` → (url, method)
  - hugo: 5000 `_write_hugo_post` 재사용 + git push
  - blogger: `BloggerClient.publish_post()` + MD→HTML 변환
  - manual: HTML 파일 저장 + pbcopy + URL 입력 대기
- `update_post_content(blog_key, post_id_or_path, new_content)`
  - hugo: 마크다운 파일 재작성 + git push
  - blogger: BloggerClient.update_post()
- `_publish_hugo()`, `_publish_blogger()`, `_publish_manual()` 분기
- `_md_to_html(md)` — markdown 라이브러리
- `_git_push(repo_path)` — subprocess git add/commit/push

**Blogger blog_id 맵:**
- `2_techpawz`: "5484205249958557854"
- `65_informationhot`: 사용자 입력 대기 (BLOGGER_BLOG_ID_HERE)

### Task 3-5: chain_card_injector.py 신규

**파일:** `chain_card_injector.py` (신규, mc)
**의존성:** Task 3-2 (card_cta 설정)

**클래스:** `CardInjector`
- `inject_cards(post, next_post, chain_direction)` → 수정된 content
  - 5000의 `_build_funnel_card_html()` 재사용
  - 하단 카드: 마지막 H2 섹션 이후 (또는 `<!-- next_link -->` 플레이스홀더 치환)
  - 중간 카드: H2 ≥ 3개일 때 2번째 H2 직후
- `_get_cta(blog_key, direction)` — chain_config.yaml 읽기

**카드 스타일:** Hugo figure 기반 (기존 _build_funnel_card_html 확장 또는 래핑)

## Wave 3: CLI + 스케줄러 + 마무리 (Tasks 3-6 ~ 3-8)

### Task 3-6: scheduler/ 패키지 신규

**파일:** `scheduler/__init__.py`, `scheduler/cron_manager.py`, `scheduler/launchd_manager.py`, `scheduler/task_runner.py`
**의존성:** python-crontab (선택)

**구현:**
- `CronManager.add_task(command, cron_expr, description)` — crontab 추가
- `CronManager.remove_task(command)` — crontab 제거
- `CronManager.list_tasks()` — 등록된 mc 작업 목록
- `LaunchdManager.add_task(command, schedule_dict, label)` — ~/Library/LaunchAgents/ plist 생성 + load
- `LaunchdManager.remove_task(label)` — unload + plist 삭제
- `task_runner.py` — 스케줄에서 호출되는 래퍼 (체인 ID 기반 publish 실행)

### Task 3-7: chain_publisher.py CLI 확장

**파일:** `chain_publisher.py` (수정)
**의존성:** Tasks 3-1~3-6

**새 CLI 플래그:**
- `--publish`: 역순 자동 발행 (Step 3→2→1)
- `--publish-interactive`: 1개씩 승인 발행
- `--publish-manual`: 수동 발행 (HTML 출력 + URL 입력)
- `--inject`: 카드 주입만
- `--schedule`, `--cron`, `--launchd`, `--hour`, `--minute`: 스케줄러
- `--schedule-list`, `--schedule-remove`: 스케줄러 관리
- `--blog-step1/2/3 KEY`: 블로그 강제 지정

**발행 워크플로:**
1. `publish_chain(chain_id, mode)`: Step 3→2→1 역순
   - 각 step: PublisherCore.publish_post() → DB update_published_url()
2. `inject_cards_chain(chain_id)`: Step 1→2 정순
   - 각 post: CardInjector.inject_cards() → Blogger/Hugo update_post_content() → DB update_card_injected()

### Task 3-8: README.md 업데이트

**파일:** `README.md` (수정)
**의존성:** Task 3-7

**내용:**
- Phase 3 사용법 전체 명령어 예시
- Blogger OAuth2 설정 가이드 (credentials.json 발급)
- 스케줄러 사용법

## Implementation Order & Waves

```
Wave 1: DB + Config (Tasks 3-1, 3-2) — 병렬 가능
Wave 2: Core Modules (Tasks 3-3, 3-4, 3-5) — 3-4가 3-3 의존, 3-5는 독립
Wave 3: Integration (Tasks 3-6, 3-7, 3-8) — 3-7이 앞선 모든 task 의존
```

## Verification Checklist

- [ ] `python -c "import chain_db; chain_db.init_db(); print('migration ok')"` — Phase 3 컬럼 존재
- [ ] BloggerClient 인스턴스 생성 + 서비스 객체 정상 반환 (OAuth2 토큰 있을 때)
- [ ] `chain_publisher.py --chain-id 5 --publish-manual` → output/manual/step-*.html 생성
- [ ] `chain_publisher.py --chain-id 5 --publish` → 3개 글 Hugo 발행 + git push
- [ ] `chain_publisher.py --chain-id 5 --inject` → 2개 카드 주입 (Step 1→2, Step 2→3)
- [ ] `chain_publisher.py --chain-id 5 --schedule --launchd --hour 9 --minute 0` → plist 생성 + load
- [ ] `chain_publisher.py --schedule-list` → 등록된 작업 표시
- [ ] `chain_publisher.py --schedule-remove --chain-id 5` → plist unload
- [ ] DB 확인: published_url, card_injected 값 정상 저장
