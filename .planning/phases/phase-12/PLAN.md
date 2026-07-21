# PLAN.md — Phase 12: mc R2 업로더 분리

**Goal:** mc가 mde2 없이 R2 이미지 업로드를 직접 수행하도록 분리

**Verification:** `python chain_publisher.py --chain-id N --publish` 시 썸네일이 R2에 정상 업로드되고, mde2 변경 없이 동작

---

## Task 1: mde2 원복

**What:** `mde2/app/services/r2_uploader.py`에서 추가된 13줄을 원복

**How:**
```bash
git -C /Users/twinssn/Projects/mde2 checkout HEAD -- app/services/r2_uploader.py
```

**Verify:** `git -C /Users/twinssn/Projects/mde2 diff HEAD` → r2_uploader.py 변경 없음

**Commit:** `git -C /Users/twinssn/Projects/mde2 commit -m "revert: r2_uploader thumb_* 패턴 추가분 원복 (mc로 분리)"`

---

## Task 2: mc/image/r2_uploader.py 생성

**What:** mde2의 `upload_all_images()` 로직을 기반으로 mc 전용 R2 업로더 생성

**File:** `/Users/twinssn/projects2/mc/image/r2_uploader.py`

**Key changes from mde2:**
1. `thumbnail.webp` + `thumb_*` 패턴 모두 지원
2. `HUGO_R2_DOMAINS` 상수를 mc/config에서 로드
3. 환경변수는 `.env.common`에서 로드 (mc 패턴)

**Core functions:**
- `get_r2_client()` — boto3 S3 클라이언트 생성
- `get_r2_config(site_path)` → `(r2_prefix, r2_domain)`
- `upload_all_images(post_dir, slug, r2_prefix, r2_domain)` → `{filename: url}`
- `HUGO_R2_DOMAINS` dict (mde2와 동일한 매핑)

**Verify:** `python -c "from image.r2_uploader import upload_all_images; print('OK')"`

---

## Task 3: chain_publisher_core.py import 변경

**What:** mde2 의존성 제거, mc 자체 모듈 사용

**Before:**
```python
# chain_publisher_core.py:23
from app.services.r2_uploader import get_r2_config, upload_all_images, HUGO_R2_DOMAINS
```

**After:**
```python
# chain_publisher_core.py:23
from image.r2_uploader import get_r2_config, upload_all_images, HUGO_R2_DOMAINS
```

**Additional:** `ensure_mde2_on_path()` 호출 제거 (라인 21)

**Verify:** `python -c "from chain_publisher_core import *; print('OK')"`

---

## Task 4: E2E 검증

**What:** 실제 썸네일이 R2에 업로드되는지 확인

**How:**
```bash
cd /Users/twinssn/projects2/mc
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from image.r2_uploader import get_r2_client, upload_all_images, get_r2_config
from pathlib import Path
import tempfile, shutil

# 테스트 썸네일로 R2 업로드 테스트
test_thumb = Path("output/images/thumb_pexels_9262765.webp")
if test_thumb.exists():
    r2_prefix, r2_domain = get_r2_config("techpawz-hugo")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        assets = tmpdir / "assets"
        assets.mkdir()
        shutil.copy2(test_thumb, assets / test_thumb.name)
        url_map = upload_all_images(tmpdir, "test-thumb", r2_prefix, r2_domain)
        print("url_map:", url_map)
        
        # R2 존재 확인
        client = get_r2_client()
        for fname, url in url_map.items():
            key = f"{r2_prefix}/test-thumb/{fname}"
            try:
                client.head_object(Bucket="md-editor", Key=key)
                print(f"✅ R2 OK: {key}")
            except Exception as e:
                print(f"❌ R2 FAIL: {key} — {e}")
else:
    print("테스트 파일 없음, 스킵")
EOF
```

**Verify:** `✅ R2 OK` 출력, URL 접근 가능

---

## Task 5: mde2 경로 참조 정리

**What:** `mc/mc_paths.py`에서 `ensure_mde2_on_path()` 호출 코드 검토

**Files to check:**
- `mc/mc_paths.py` — `ensure_mde2_on_path()` 함수 보존 (다른 모듈에서 사용 가능)
- `mc/chain_publisher_core.py` — `ensure_mde2_on_path()` 호출 제거 확인
- `mc/chain_publisher_core.py` — 라인 21 `ensure_mde2_on_path()` 주석 처리 또는 삭제

**Verify:** `grep -n "ensure_mde2" mc/chain_publisher_core.py` → 결과 없음

---

## Dependencies

- Task 1 (mde2 원복) → Task 2 (mc 업로더 생성) → Task 3 (import 변경) → Task 4 (검증)
- Task 5는 Task 3과 병렬 가능

## Risk

- mde2 원복 후 mde2 자체 동작에 영향 없음 (원래 동작으로 복귀)
- mc의 새 업로더가 mde2와 동일한 R2 버킷에 업로드하는지 확인 필요

## Estimated Effort

- Task 1: 5분 (git 명령어 1줄)
- Task 2: 30분 (mde2 로직 복사 + 수정)
- Task 3: 5분 (import 변경)
- Task 4: 15분 (E2E 테스트)
- Task 5: 5분 (grep 확인)
- **Total: ~1시간**
