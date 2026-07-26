---
phase: 21
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - chain_publisher.py
  - image/thumbnail.py
  - chain_db.py
  - test_chain_publisher_core.py
  - test_cli_mc.py
autonomous: true
requirements: [R21-01, R21-02, R21-03, R21-04, R21-05]
must_haves:
  truths:
    - "Content image이 thumbnail으로 재사용되어 별도 Unsplash/Pexels API 호출이 사라짐"
    - "R2 업로드가 포스트당 1회로 감소 (thumbnail은 content image 파일에 text overlay만 추가)"
    - "time.sleep(15)가 제거되어 post 간 강제 대기가 없음"
    - "3개 포스트 이미지 생성이 ThreadPoolExecutor로 병렬 처리됨"
    - "CLI publish_mode가 이미 'auto'로 기본 설정되어 전체 파이프라인이 동작함"
    - "발행 후 smoke_test()가 자동 실행되어 3개 URL의 HTTP 200을 검증함"
    - "smoke_test 결과가 chain_posts.smoke_test_checked_at 컬럼에 기록됨"
    - "pytest 246/246 이상 유지 (새 smoke test 포함)"
  artifacts:
    - path: chain_publisher.py
      provides: "generate_chain_images() 최적화 + smoke_test()"
      min_lines: 1000
    - path: image/thumbnail.py
      provides: "add_text_overlay() 함수 (변경 없음, 재사용)"
    - path: chain_db.py
      provides: "smoke_test_checked_at 컬럼 migration"
    - path: test_chain_publisher_core.py
      provides: "smoke_test 단위 테스트"
  key_links:
    - from: "generate_chain_images()"
      to: "add_text_overlay()"
      via: "content image path 재사용 → 텍스트 오버레이 → thumbnail 저장"
      pattern: "add_text_overlay"
    - from: "generate_chain_images()"
      to: "concurrent.futures.ThreadPoolExecutor"
      via: "병렬 처리"
      pattern: "ThreadPoolExecutor"
    - from: "inject_cards_chain()"
      to: "smoke_test()"
      via: "_deploy_blogs_after_inject() 완료 후 호출"
      pattern: "smoke_test"
---

<objective>
Phase 21 — `mc "키워드"` 한 줄로, 플래그 없이, 60초 이내에 3개 사이트 발행 완료 + URL 자동 검증

**Purpose:** 이미지 파이프라인 병목 해결로 182s → 60s 미만 단축, 발행 후 자동 smoke test로 신뢰성 확보
**Output:** 최적화된 chain_publisher.py + smoke_test() + DB 스키마 + 단위 테스트
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phase-21/CONTEXT.md
@.planning/phase-21/RESEARCH.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From image/thumbnail.py:
```python
def add_text_overlay(
    image_path: Path,
    title: str,
    subtitle: Optional[str] = None,
    target_size: tuple[int, int] = (1024, 1024),
) -> Path:
    """Content image에 텍스트 오버레이 추가. 이미 열려 있는 로컬 파일 경로를 받음."""

def generate_content_image(
    prompt: str,
    slug: str = "post",
    width: int = 1024,
    height: int = 1024,
    model: str = "unsplash",
    seed: int = None,
    retries: int = 3,
) -> "Result":
    """Unsplash/Pexels 실사 사진을 다운로드. 텍스트 오버레이 없음."""
    # Returns Result.success(Path) or Result.failure(...)

def generate_thumbnail(
    title: str,
    keyword: str,
    slug: str = "",
    subtitle: Optional[str] = None,
) -> Optional[tuple[Path, str]]:
    """(변경 없음) — 대체로 사용되지 않음. 새 코드는 add_text_overlay() 직접 호출."""
```

From chain_publisher.py current generate_chain_images():
```python
def generate_chain_images(chain_id: int) -> None:
    chain = db.get_chain(chain_id)
    posts = db.get_chain_posts(chain_id)
    db.update_chain_status(chain_id, "generating")

    for i, post in enumerate(posts):
        # content image 생성 + R2 업로드 (line 222-252)
        image_result = img_gen(full_prompt, slug=_slug)
        if image_result and image_result.ok:
            image_path = image_result.value  # Path object
            # R2 upload content image (line 237-244)
            # Thumbnail 생성 + R2 upload (line 254-296)
            # img_inject (line 298-303)
        if i < len(posts) - 1:
            time.sleep(15)  # ← 제거 대상
```

From chain_publisher.py _deploy_blogs_after_inject():
```python
def _deploy_blogs_after_inject(blog_keys: set, config: dict) -> None:
    """카드 주입 후 Hugo build + Wrangler deploy. smoke_test()는 이 함수 종료 직후 호출."""
```

From chain_db.py existing patterns:
```python
# Migration pattern:
MIGRATIONS_SQL = [
    "ALTER TABLE chain_posts ADD COLUMN publish_method TEXT",
    "ALTER TABLE chain_posts ADD COLUMN image_meta TEXT",
]
```

From chain_db.py get_chain_posts():
```python
def get_chain_posts(chain_id: int) -> list[dict]:
    """Returns list of Row dicts with all columns."""
```

Existing test patterns (test_cli_mc.py):
```python
@patch("chain_publisher.run_chain")
def test_dry_run_calls_run_chain(self, mock_run_chain):
    mock_run_chain.return_value = 99
    # ... assertion on call args
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Thumbnail 재사용 + R2 업로드 병합 (A-1+A-2)</name>
  <files>
    chain_publisher.py
    image/thumbnail.py
    test_image_pipeline.py
    test_chain_publisher_core.py
  </files>
  <action>
    **변경 사항: generate_chain_images()에서 thumbnail 생성을 위한 별도 API 호출 제거**

    ### chain_publisher.py `generate_chain_images()` 수정 (line 254-296 영역)

    **Before:**
    ```python
    # Generate thumbnail (Unsplash/Pexels + Pillow text overlay) and upload to R2
    try:
        print(f"  [publisher] Generating thumbnail for post #{post_id}...")
        thumb_result = img_thumb(
            post["title"],
            post.get("image_keyword", post.get("target_keyword", "")),
            slug=_slug,
        )
        if thumb_result:
            thumb_path, thumb_source = thumb_result
            # ... R2 upload
    ```

    **After:**
    ```python
    # Generate thumbnail from content image (로컬 파일 재사용, API 호출 없음)
    try:
        print(f"  [publisher] Generating thumbnail from content image for post #{post_id}...")
        from image.thumbnail import add_text_overlay
        thumb_path = add_text_overlay(
            image_path,
            post["title"],
            subtitle=post.get("image_keyword", post.get("target_keyword", "")),
            target_size=(1024, 1024),
        )
        print(f"  [publisher] Thumbnail generated from content image: {thumb_path}")
        # R2 upload (기존 코드 유지 — thumb_key 경로, put_object)
        _thumb_source = "unsplash"  # content image과 동일한 소스 (thumbnail 자체 소스 불필요)
        thumb_source = _thumb_source
        from image.r2_uploader import get_r2_client, _resolve_bucket
        import os
        r2_client = get_r2_client()
        _r2_prefix = {
            "rotcha": "images/rotcha",
            "issue.techpawz": "images/issue-techpawz",
            "techpawz": "images/techpawz",
        }.get(blog_key, f"images/{blog_key}")
        _bucket = _resolve_bucket(_r2_prefix)
        thumb_key = f"{_r2_prefix}/{_slug}/{thumb_path.name}"
        with open(thumb_path, "rb") as f:
            r2_client.put_object(
                Bucket=_bucket,
                Key=thumb_key,
                Body=f.read(),
                ContentType="image/webp"
            )
        thumb_r2_url = f"{os.getenv('R2_PUBLIC_URL')}/{thumb_key}"
        db.update_post_image(post_id, thumb_r2_url)
        meta = json.loads(post.get("image_meta", "{}")) if post.get("image_meta") else {}
        meta["thumbnail_r2_url"] = thumb_r2_url
        meta["thumbnail_source"] = thumb_source
        meta["thumbnail_path"] = str(thumb_path)
        db.update_image_meta(post_id, meta)
        print(f"  [publisher] Thumbnail uploaded to R2: {thumb_r2_url}")
    except Exception as e:
        print(f"  [publisher] ⚠️ Thumbnail generation from content image failed: {e}")
        import traceback
        traceback.print_exc()
    ```

    **핵심 변경:**
    1. `img_thumb(post["title"], keyword, slug=_slug)` 호출을 `add_text_overlay(image_path, post["title"], subtitle=keyword, target_size=(1024, 1024))`로 대체
    2. `add_text_overlay()`에 필요한 import 추가: `from image.thumbnail import add_text_overlay`
    3. `img_thumb` import는 유지 — 다른 코드 경로에서 사용될 수 있음. 단, `generate_chain_images()` 내부에서만 제거.
    4. `thumb_source` = `"unsplash"` (content image 소스와 동일. thumbnail API 호출이 없으므로 content image의 source를 계승. 실제로는 `content_image_path` 파일명에서 추론해도 되나 복잡도 대비 이득 없음)
    5. `generate_thumbnail()`이 반환하던 `(Path, source)` tuple → `add_text_overlay()`가 반환하는 `Path`로 변경. `thumb_result` unpacking 수정.

    ### image/thumbnail.py — export 추가 확인
    `add_text_overlay()`는 이미 `image/__init__.py`에 export되어 있지 않음 (`from .thumbnail import generate_thumbnail, add_text_overlay` — line 11에서 확인됨). 따라서 별도 import 추가 불필요.
    
    chain_publisher.py 상단 import 영역에 추가해야 할 것:
    ```python
    from image.thumbnail import add_text_overlay  # thumbnail 재사용용 (A-1)
    ```
    (선택: generate_chain_images() 내부에서 lazy import해도 무방)

    ### add_text_overlay() 호출 시 slug 처리
    `add_text_overlay()`는 `image_path.stem`에서 slug를 추출해 저장 (line 334-336):
    ```python
    safe_slug = re.sub(r"[^a-zA-Z0-9가-힣_-]", "", str(image_path.stem))[:60]
    safe_slug = re.sub(r"^thumb_", "", safe_slug)
    out_path = IMAGE_DIR / f"thumb_{safe_slug}.webp"
    ```
    Content image path가 `{slug}_1024x1024.webp` 형태이므로, slug 추출이 정상 동작함.

    ### 테스트 영향
    - `test_image_pipeline.py`의 `test_generate_thumbnail_unsplash_success` 등 `generate_thumbnail()` 테스트는 변경 없음 (함수 자체는 유지)
    - `test_chain_publisher_core.py`의 generate_chain_images 관련 테스트가 mock 호출 검증 실패할 수 있음. 
    - `test_cli_mc.py`의 `test_default_full_pipeline` 등 `publish_mode="auto"` 검증 테스트는 영향 없음

    ### pytest 회귀 확인
    ```bash
    python -m pytest --timeout=60 -x -q 2>&1 | tail -20
    ```
    실패 시 `img_thumb` mock 호출이 포함된 테스트를 찾아 수정. `img_thumb` mock 대신 `add_text_overlay` mock으로 변경.

    ### 롤백 계획
    ```bash
    git checkout -- chain_publisher.py
    ```
  </action>
  <verify>
    <automated>python -m pytest --timeout=60 -x -q 2>&1 | tail -5</automated>
  </verify>
  <done>
    - generate_chain_images()에서 img_thumb() 호출 제거 → grep 결과 0건
    - add_text_overlay()가 content image path로 호출됨
    - R2 업로드는 포스트당 1회(content image + thumbnail)로 유지
    - pytest 246/246 통과 (회귀 없음)
    - git diff로 변경 사항 검증
  </done>
</task>

<task type="auto">
  <name>Task 2: Sleep 제거 + 병렬화 (A-3+A-4) + CLI 검증 (B)</name>
  <files>
    chain_publisher.py
  </files>
  <action>
    **변경 1: time.sleep(15) 제거**

    `generate_chain_images()` line 316-318 삭제:
    ```python
    # Before (line 316-318):
    if i < len(posts) - 1:
        print(f"  [publisher]     waiting {pol_cfg.get('rate_limit_seconds', 15)}s...")
        time.sleep(pol_cfg.get("rate_limit_seconds", 15))
    
    # After: 완전 제거
    ```

    **변경 2: ThreadPoolExecutor로 병렬화**

    `generate_chain_images()` 함수를 변경하여 `for i, post in enumerate(posts):` 루프를 `ThreadPoolExecutor(max_workers=3)`로 감싼다.

    **설계 결정:**
    - 각 포스트의 이미지 생성은 완전히 독립적 (서로 다른 slug, 다른 post_id, 다른 DB row)
    - DB 쓰기는 각 thread 내에서 `get_conn()`으로 **별도 connection** 사용 → thread-safe
    - 결과 순서는 중요하지 않음 (DB 업데이트는 post_id 기준, 순서 무관)
    - 예외 발생 시 해당 포스트만 실패 처리, 다른 포스트는 계속 진행

    **변경 패턴:**
    ```python
    def _process_post_image(post: dict, blog_key: str, pol_cfg: dict) -> int:
        """단일 포스트 이미지 생성 (ThreadPoolExecutor용). Returns post_id."""
        post_id = post["id"]
        _slug = post.get("slug") or f"post-{post_id}"
        
        # (기존 for 루프 내 코드를 이 함수로 추출)
        # image_meta.content_image_path 완결 판정, 디스크 백필 등
        ...
        
        # content image 생성
        if use_new_image:
            full_prompt = img_build(...)
            image_result = img_gen(full_prompt, slug=_slug)
            ...
        
        # thumbnail 생성 (add_text_overlay)
        ...
        
        # img_inject
        ...
        
        return post_id
    
    def generate_chain_images(chain_id: int) -> None:
        chain = db.get_chain(chain_id)
        if not chain:
            print(f"[publisher] Chain #{chain_id} not found")
            return
        
        config = load_config()
        pol_cfg = config.get("pollinations", {})
        posts = db.get_chain_posts(chain_id)
        db.update_chain_status(chain_id, "generating")
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        post_ids = []
        blog_keys = {}
        for post in posts:
            blog_key = get_chain_blog_key(post["depth"])
            blog_keys[post["id"]] = blog_key
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(_process_post_image, post, blog_keys[post["id"]], pol_cfg): post["id"]
                for post in posts
            }
            for future in as_completed(futures):
                post_id = futures[future]
                try:
                    result = future.result()
                    post_ids.append(result)
                except Exception as e:
                    print(f"  [publisher] ⚠️ Post #{post_id} image generation failed: {e}")
                    import traceback
                    traceback.print_exc()
        
        db.update_chain_status(chain_id, "image_generated")
        print(f"\n  [publisher] Chain #{chain_id} images done (parallel)")
    ```

    **중요 — 추출 시 고려사항:**
    1. `i` (루프 인덱스): `_process_post_image()` 내에서는 **사용하지 않음**. sleep 조건이 사라졌으므로 인덱스 불필요.
    2. `blog_key`: 각 post의 `post["depth"]`로 `get_chain_blog_key()` 계산 → `_process_post_image()` 인자로 전달
    3. `_meta_raw`, `_meta` 변수: `_process_post_image()` 내부에서 지역 변수로 처리
    4. `_write_image_log()`: 함수 외부에 정의되어 있어야 함. `generate_chain_images()` 스코프 내에서 사용 가능.
    5. `use_new_image`: 모듈 전역 변수 (line 172) — `_process_post_image()`에서 접근 가능
    6. `db.` 호출들: 각 thread가 자체 connection 사용 — thread-safe 확인 필요. `get_conn()`이 매번 새 connection을 열므로 문제 없음.

    **변경 3: 실시간 측정 로그 추가**

    CONTEXT.md 제약사항 3번 "추측 금지. 코드를 읽고, 시간을 측정하고, 로그를 남겨라"에 따라:
    ```python
    import time as _time_module
    _t0 = _time_module.time()
    # ... 이미지 생성 코드 ...
    _elapsed = _time_module.time() - _t0
    print(f"  [publisher] Post #{post_id} image pipeline: {_elapsed:.1f}s")
    ```

    **변경 4: CLI publish_mode 검증**

    Task B는 **코드 변경이 아닌 검증** 작업:
    - `cli/mc.py` line 140-142 이미 `publish_mode = "auto"`인 것을 확인
    - `run_chain()` line 762-765 이미 deploy까지 포함하는 것을 확인
    - 검증 스크립트:
      ```python
      # cli/mc.py _run_full()의 publish_mode 기본값 확인
      assert publish_mode == "auto"  # line 142
      ```
    - 검증 결과를 로그로 출력 (별도 코드 변경 없음, 확인만)

    ### pytest 회귀 확인
    ```bash
    python -m pytest --timeout=60 -x -q 2>&1 | tail -5
    ```
    모킹된 테스트에서 `generate_chain_images`의 내부 구조 변화로 인한 깨짐이 발생할 수 있음. 
    - `test_cli_mc.py`에서 `generate_chain_images`를 mock하는 테스트는 영향 없음 (mock이 함수 전체를 대체)
    - `test_chain_publisher_core.py`에서 실제 `generate_chain_images`를 호출하는 테스트는 수정 필요

    ### 롤백 계획
    ```bash
    git checkout -- chain_publisher.py
    ```
  </action>
  <verify>
    <automated>python -m pytest --timeout=60 -x -q 2>&1 | tail -5</automated>
  </verify>
  <done>
    - `time.sleep(15)` 제거 → grep "time.sleep" chain_publisher.py 결과 0건 (정당한 sleep 제외)
    - `ThreadPoolExecutor(max_workers=3)` 적용 → grep "ThreadPoolExecutor" chain_publisher.py 결과 1건
    - 각 Post 이미지 생성 시간이 로그에 기록됨
    - pytest 246/246 통과 (회귀 없음)
    - CLI publish_mode 기본값 "auto" 확인 완료
  </done>
</task>

<task type="auto">
  <name>Task 3: Smoke Test 함수 + DB 스키마 + 단위 테스트 (C)</name>
  <files>
    chain_db.py
    chain_publisher.py
    test_chain_publisher_core.py
    test_cli_mc.py
  </files>
  <action>
    ### C-1: DB 스키마 — chain_posts에 smoke_test_checked_at 컬럼 추가

    `chain_db.py`의 `MIGRATIONS_SQL` 리스트에 migration 추가:
    ```python
    # Phase 21: Smoke test
    "ALTER TABLE chain_posts ADD COLUMN smoke_test_checked_at TEXT",
    "ALTER TABLE chain_posts ADD COLUMN smoke_test_result TEXT",  # "pass" | "fail" | NULL
    "ALTER TABLE chain_posts ADD COLUMN smoke_test_detail TEXT",  # JSON: {url, status, title_found, og_image_ok}
    ```

    `chain_db.py`에 smoke_test update 함수 추가:
    ```python
    def update_smoke_test_result(post_id: int, result: str, detail: dict = None) -> None:
        """Smoke test 결과 기록. result: 'pass' | 'fail'."""
        conn = get_conn()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE chain_posts SET smoke_test_checked_at = ?, smoke_test_result = ?, smoke_test_detail = ?, updated_at = ? WHERE id = ?",
            (now, result, json.dumps(detail) if detail else None, now, post_id),
        )
        conn.commit()
        conn.close()

    def get_smoke_test_summary(chain_id: int) -> list[dict]:
        """체인의 smoke_test 결과 요약."""
        posts = get_chain_posts(chain_id)
        return [
            {
                "step": p.get("step"),
                "published_url": p.get("published_url"),
                "result": p.get("smoke_test_result"),
                "checked_at": p.get("smoke_test_checked_at"),
            }
            for p in posts
        ]
    ```

    ### C-2: smoke_test() 함수

    `chain_publisher.py`에 새 함수 추가 (또는 `chain_publisher_core.py` — 결정 필요):

    **설계 결정: chain_publisher.py에 추가.** 이유:
    1. `_deploy_blogs_after_inject()`가 `chain_publisher.py`에 있음
    2. `run_chain()`이 `chain_publisher.py`에 있고, 여기서 호출
    3. `chain_db` import가 이미 되어 있음

    ```python
    import requests as _requests  # 함수 내부 import 또는 상단 추가

    def smoke_test(chain_id: int) -> dict:
        """
        발행 완료된 체인의 각 포스트 URL에 대해 smoke test 수행.
        
        검증:
        - HTTP 200 응답
        - <title> 태그 존재
        - og:image 메타태그 존재 → 해당 URL HTTP 200
        
        실패해도 경고만 출력 (롤백 없음).
        
        Returns:
            dict: {post_id: {"url": str, "status_code": int, "title_found": bool, 
                             "og_image_ok": bool, "overall": "pass"|"fail"}}
        """
        import requests as req
        from bs4 import BeautifulSoup  # 또는 간단한 regex로 title/og:image 추출
        
        posts = db.get_chain_posts(chain_id)
        results = {}
        
        for post in posts:
            url = post.get("published_url")
            if not url:
                print(f"  [smoke] Post #{post['id']}: no published_url — skipping")
                continue
            
            detail = {"url": url, "status_code": None, "title_found": False, 
                      "og_image_url": None, "og_image_ok": False, "error": None}
            
            try:
                resp = req.get(url, timeout=10, allow_redirects=True)
                detail["status_code"] = resp.status_code
                
                if resp.status_code == 200:
                    # <title> 존재 확인
                    import re
                    title_match = re.search(r'<title[^>]*>(.*?)</title>', resp.text, re.IGNORECASE | re.DOTALL)
                    detail["title_found"] = bool(title_match and title_match.group(1).strip())
                    
                    # og:image URL 추출 및 검증
                    og_match = re.search(
                        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](.*?)["\']',
                        resp.text, re.IGNORECASE
                    )
                    if og_match:
                        og_url = og_match.group(1)
                        detail["og_image_url"] = og_url
                        try:
                            og_resp = req.get(og_url, timeout=10, stream=True)
                            detail["og_image_ok"] = og_resp.status_code == 200
                            og_resp.close()
                        except Exception as e:
                            detail["og_image_ok"] = False
                            detail["error"] = f"og:image fetch failed: {e}"
                
                overall = "pass" if (resp.status_code == 200 and 
                                     detail["title_found"] and 
                                     detail["og_image_ok"]) else "fail"
                
            except Exception as e:
                overall = "fail"
                detail["error"] = str(e)
            
            detail["overall"] = overall
            results[post["id"]] = detail
            
            # DB 기록
            db.update_smoke_test_result(post["id"], overall, detail)
            
            status_icon = "✅" if overall == "pass" else "⚠️"
            print(f"  [smoke] {status_icon} Post #{post['id']}: {url} → {resp.status_code if 'resp' in dir() else 'ERR'}, title={'Y' if detail['title_found'] else 'N'}, og:image={'Y' if detail['og_image_ok'] else 'N'}")
        
        return results
    ```

    ### C-3: smoke_test() 호출 위치 — _deploy_blogs_after_inject() 완료 직후

    `inject_cards_chain()`의 deploy 완료 후, 또는 `run_chain()`의 publish_mode="auto" 블록 완료 후.

    **호출 위치: `run_chain()` line 762-765 영역 수정:**

    ```python
    # Before (line 761-765):
    if publish_mode:
        publish_chain(chain_id, mode=publish_mode, ...)
        if publish_mode != "manual":
            inject_cards_chain(chain_id)
    
    # After:
    if publish_mode:
        publish_chain(chain_id, mode=publish_mode, ...)
        if publish_mode != "manual":
            inject_cards_chain(chain_id)
            # Phase 21: 발행 후 smoke test
            print(f"\n{'─'*60}\n[mc] Running smoke test for chain #{chain_id}\n{'─'*60}\n")
            smoke_test(chain_id)
    ```

    ### C-4: 단위 테스트

    `test_chain_publisher_core.py`에 `TestSmokeTest` 클래스 추가:

    ```python
    class TestSmokeTest(unittest.TestCase):
        """Phase 21: 발행 후 smoke_test() 단위 테스트."""

        @patch("chain_publisher.db.get_chain_posts")
        @patch("chain_publisher.db.update_smoke_test_result")
        @patch("chain_publisher.requests.get")
        def test_smoke_test_all_pass(
            self, mock_get, mock_update, mock_get_posts
        ):
            """3개 URL 모두 HTTP 200 + title + og:image 정상."""
            from chain_publisher import smoke_test
            
            mock_get_posts.return_value = [
                {"id": 1, "published_url": "https://rotcha.kr/post1", "step": 1},
                {"id": 2, "published_url": "https://issue.techpawz/post2", "step": 2},
                {"id": 3, "published_url": "https://techpawz/post3", "step": 3},
            ]
            
            # Mock HTTP response
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = """
            <html><head>
                <title>Test Post</title>
                <meta property="og:image" content="https://r2.example.com/img.webp">
            </head></html>
            """
            mock_get.return_value = mock_resp
            
            results = smoke_test(99)
            
            self.assertEqual(len(results), 3)
            for post_id, detail in results.items():
                self.assertEqual(detail["overall"], "pass")
                self.assertEqual(detail["status_code"], 200)
                self.assertTrue(detail["title_found"])
                self.assertTrue(detail["og_image_ok"])

        @patch("chain_publisher.db.get_chain_posts")
        @patch("chain_publisher.db.update_smoke_test_result")
        @patch("chain_publisher.requests.get")
        def test_smoke_test_http_500(
            self, mock_get, mock_update, mock_get_posts
        ):
            """HTTP 500 → overall fail, DB 기록."""
            from chain_publisher import smoke_test
            
            mock_get_posts.return_value = [
                {"id": 1, "published_url": "https://rotcha.kr/fail", "step": 1},
            ]
            
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.text = "<html><body>Error</body></html>"
            mock_get.return_value = mock_resp
            
            results = smoke_test(99)
            
            self.assertEqual(results[1]["overall"], "fail")
            self.assertEqual(results[1]["status_code"], 500)

        @patch("chain_publisher.db.get_chain_posts")
        @patch("chain_publisher.db.update_smoke_test_result")
        @patch("chain_publisher.requests.get")
        def test_smoke_test_connection_error(
            self, mock_get, mock_update, mock_get_posts
        ):
            """Connection error → overall fail, 예외 처리."""
            from chain_publisher import smoke_test
            
            mock_get_posts.return_value = [
                {"id": 1, "published_url": "https://rotcha.kr/timeout", "step": 1},
            ]
            mock_get.side_effect = Exception("Connection timeout")
            
            results = smoke_test(99)
            
            self.assertEqual(results[1]["overall"], "fail")
            self.assertIsNotNone(results[1]["error"])

        @patch("chain_publisher.db.get_chain_posts")
        @patch("chain_publisher.db.update_smoke_test_result")
        @patch("chain_publisher.requests.get")
        def test_smoke_test_missing_url(
            self, mock_get, mock_update, mock_get_posts
        ):
            """published_url 없음 → skip."""
            from chain_publisher import smoke_test
            
            mock_get_posts.return_value = [
                {"id": 1, "published_url": None, "step": 1},
            ]
            
            results = smoke_test(99)
            self.assertEqual(len(results), 1)
            self.assertIsNone(results[1]["status_code"])

        @patch("chain_publisher.db.get_chain_posts")
        @patch("chain_publisher.db.update_smoke_test_result")
        @patch("chain_publisher.requests.get")
        def test_smoke_test_og_image_404(
            self, mock_get, mock_update, mock_get_posts
        ):
            """og:image URL이 404 → overall fail."""
            from chain_publisher import smoke_test
            
            mock_get_posts.return_value = [
                {"id": 1, "published_url": "https://rotcha.kr/post1", "step": 1},
            ]
            
            # First call: page OK ; Second call: og:image 404
            mock_page = MagicMock()
            mock_page.status_code = 200
            mock_page.text = """
            <html><head>
                <title>Test</title>
                <meta property="og:image" content="https://r2.example.com/missing.webp">
            </head></html>
            """
            
            mock_og = MagicMock()
            mock_og.status_code = 404
            
            mock_get.side_effect = [mock_page, mock_og]
            
            results = smoke_test(99)
            self.assertEqual(results[1]["overall"], "fail")
            self.assertFalse(results[1]["og_image_ok"])
    ```

    ### requests 의존성 확인
    현재 `chain_publisher.py`는 `urllib.request`만 import하고 `requests`는 import하지 않음.
    - `requirements.txt`에 `requests`가 있는지 확인. 없으면 smoke_test() 내부에서 `urllib.request` 사용.
    - 또는 `chain_publisher.py` 상단에 `import requests` 추가 (requirements.txt에 requests가 있다고 가정 — 확인 필수)

    ```bash
    grep "requests" requirements.txt  # 확인
    ```
    만약 `requests`가 없으면 `urllib.request`로 구현:
    ```python
    import urllib.request as _urllib_req
    import urllib.error as _urllib_err
    
    def _http_get(url: str, timeout: int = 10) -> tuple:
        """urllib를 사용한 HTTP GET. (status_code, text, error) 반환."""
        try:
            with _urllib_req.urlopen(url, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8", errors="replace"), None
        except _urllib_err.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace"), None
        except Exception as e:
            return None, None, str(e)
    ```

    ### pytest 회귀 확인
    ```bash
    python -m pytest --timeout=60 -x -q 2>&1 | tail -5
    ```
    새로 추가한 smoke_test 테스트 5개 포함 251/251 통과 확인.

    ### 롤백 계획
    ```bash
    # DB migration 제거
    # chain_db.py의 MIGRATIONS_SQL에서 smoke_test 관련 ALTER 제거
    # chain_publisher.py에서 smoke_test 함수 제거 및 호출 제거
    # test 파일에서 TestSmokeTest 클래스 제거
    git checkout -- chain_db.py chain_publisher.py test_chain_publisher_core.py
    ```
  </action>
  <verify>
    <automated>python -m pytest --timeout=60 -x -q 2>&1 | tail -5</automated>
  </verify>
  <done>
    - smoke_test() 함수가 chain_publisher.py에 구현됨
    - chain_db.py에 smoke_test_checked_at, smoke_test_result, smoke_test_detail 컬럼 migration 추가
    - run_chain() 내 publish_mode="auto" 블록 종료 후 smoke_test() 호출
    - smoke_test 단위 테스트 5개 통과 (mock HTTP)
    - pytest 251/251+ 통과 (새 테스트 포함)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| chain_publisher.py ↔ Unsplash/Pexels API | 외부 API 호출 (이미지 검색/다운로드) |
| chain_publisher.py ↔ R2 (Cloudflare) | 이미지 업로드 |
| smoke_test() → 발행 URL | HTTP GET 검증 (읽기 전용) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-21-01 | Tampering | ThreadPoolExecutor 내 DB 쓰기 | mitigate | 각 thread가 `get_conn()`으로 별도 connection 사용. SQLite WAL 모드 + thread-safe 확인 |
| T-21-02 | Denial of Service | 병렬 Unsplash/Pexels API 호출 | accept | 3개 동시 호출 = rate limit 50/시간, 200/시간에 크게 미달. 필요시 max_workers=2로 축소 |
| T-21-03 | Spoofing | smoke_test() HTTP GET | accept | 읽기 전용, 롤백 없음, 경고만 출력 |
| T-21-SC | Tampering | pip install requests (smoke_test용) | mitigate | `requests`가 requirements.txt에 있는지 확인. 없으면 `urllib.request`로 대체 |
</threat_model>

<verification>
## 단계별 검증 프로토콜

### Task 1 검증
```bash
# ① Thumbnail 재사용 확인 (img_thumb 호출 제거)
grep -n "img_thumb\|generate_thumbnail" chain_publisher.py
# → generate_chain_images() 내부에 img_thumb 호출이 없어야 함

# ② add_text_overlay 호출 확인
grep -n "add_text_overlay" chain_publisher.py
# → generate_chain_images() 내부에 add_text_overlay(image_path, ...) 호출 있어야 함

# ③ R2 업로드 구조 확인 (thumb_key 업로드 유지)
grep -n "thumb_key\|put_object" chain_publisher.py

# ④ pytest
python -m pytest --timeout=60 -x -q
```

### Task 2 검증
```bash
# ① Sleep 제거 확인
grep -n "time.sleep" chain_publisher.py
# → generate_chain_images() 내부에 time.sleep 호출이 없어야 함

# ② 병렬화 확인
grep -n "ThreadPoolExecutor" chain_publisher.py

# ③ 성능 측정: 3개 포스트 이미지 생성 시간 측정
python -c "
from chain_publisher import generate_chain_images
import time
t0 = time.time()
generate_chain_images(<TEST_CHAIN_ID>)
print(f'Total: {time.time() - t0:.1f}s')
"

# ④ pytest
python -m pytest --timeout=60 -x -q
```

### Task 3 검증
```bash
# ① DB migration 확인
python -c "
import chain_db as db
db.init_db()
conn = db.get_conn()
cols = [r['name'] for r in conn.execute('PRAGMA table_info(chain_posts)').fetchall()]
print('smoke_test_checked_at' in cols)  # True
print('smoke_test_result' in cols)      # True
print('smoke_test_detail' in cols)      # True
conn.close()
"

# ② smoke_test 단위 테스트
python -m pytest test_chain_publisher_core.py::TestSmokeTest -v

# ③ 전체 pytest
python -m pytest --timeout=60 -x -q
```
</verification>

<success_criteria>
## Definition of Done

1. ✅ **Thumbnail 재사용:** `generate_chain_images()`가 `add_text_overlay(image_path, ...)`로 thumbnail 생성, 별도 `img_thumb()` API 호출 없음
2. ✅ **R2 업로드 병합:** Content image 업로드 후 thumbnail은 로컬에서 text overlay만 추가, 포스트당 1회 API 검색
3. ✅ **Sleep 제거:** `time.sleep(15)` 완전 제거 (grep 0건)
4. ✅ **병렬화:** `ThreadPoolExecutor(max_workers=3)` 적용, 3개 포스트 이미지 생성 동시 실행
5. ✅ **성능 목표:** 이미지 생성 81s → ~13s (RESEARCH.md 추정치 기준). 실측치 로그 기록.
6. ✅ **CLI 검증:** `publish_mode="auto"` 기본값 확인, 전체 파이프라인 deploy 포함 확인
7. ✅ **smoke_test():** `_deploy_blogs_after_inject()` 완료 직후 자동 실행
8. ✅ **DB 스키마:** `chain_posts`에 `smoke_test_checked_at`, `smoke_test_result`, `smoke_test_detail` 컬럼 추가
9. ✅ **단위 테스트:** smoke_test 5개 케이스 (all pass, HTTP 500, connection error, missing URL, og:image 404)
10. ✅ **pytest:** 251/251+ 통과 (회귀 없음)
11. ✅ **.continue-here.md** 업데이트: Phase 21 완료 내용 기록
</success_criteria>

<output>
`.planning/phases/phase-21/SUMMARY.md` when done
</output>
