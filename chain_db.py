"""
mc — 체인 DB 관리 모듈 (Phase 2)

SQLite 스키마 및 CRUD. Phase 2 추가: draft_md, slug, chain_type 컬럼.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

from mc_paths import load_config

cfg = None  # lazy load


def _get_cfg():
    global cfg
    if cfg is None:
        cfg = load_config()
    return cfg


def _db_path() -> str:
    return _get_cfg()["db_path"]


def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def get_conn() -> sqlite3.Connection:
    """Return a new SQLite connection (row_factory = sqlite3.Row)."""
    path = _db_path()
    _ensure_dir(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Schema ──

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    seed        TEXT    NOT NULL,
    depth_count INTEGER NOT NULL DEFAULT 3,
    chain_type  TEXT    NOT NULL DEFAULT 'depth',
    status      TEXT    NOT NULL DEFAULT 'derived',
    -- derived | generating | drafted | completed | failed
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS chain_posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chain_id INTEGER NOT NULL REFERENCES chains(id) ON DELETE CASCADE,
  depth INTEGER NOT NULL, -- 0, 1, 2
  step INTEGER DEFAULT 0,
  chain_type TEXT DEFAULT 'depth',
  title TEXT NOT NULL,
  target_keyword TEXT,
  key_points TEXT, -- JSON array string
  angle TEXT,
  category_guess TEXT,
  bridge_logic TEXT,
  image_prompt TEXT,
  image_url TEXT,
  draft_md TEXT,
  slug TEXT,
  hugo_file_path TEXT, -- published hugo file
  published_url TEXT, -- Phase 3: 최종 발행 URL
  published_at TEXT, -- Phase 3: 발행 일시
  card_injected INTEGER DEFAULT 0, -- Phase 3: 카드 주입 완료 여부
  card_injected_at TEXT, -- Phase 3: 카드 주입 일시
  publish_method TEXT, -- Phase 3: 'hugo' | 'blogger' | 'manual' | 'manual_pending'
  published_md TEXT, -- R2 URL 교체 본문 (card injection용, draft_md 원본 보존)
  status TEXT NOT NULL DEFAULT 'derived',
  -- derived | image_generated | drafted | published | failed
  error_log TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_chain_posts_chain_id ON chain_posts(chain_id);
CREATE INDEX IF NOT EXISTS idx_chain_posts_depth     ON chain_posts(depth);

-- Phase 5: publish_log (4-layer dedup layer 2)
CREATE TABLE IF NOT EXISTS publish_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    blog_id         TEXT NOT NULL,
    slug            TEXT NOT NULL,
    published_url   TEXT,
    publish_method  TEXT,
    published_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(blog_id, slug)
);
"""

# ── Phase 1 → Phase 2 마이그레이션 ──

MIGRATIONS_SQL = [
# Phase 1→2
"ALTER TABLE chains ADD COLUMN chain_type TEXT NOT NULL DEFAULT 'depth'",
"ALTER TABLE chain_posts ADD COLUMN step INTEGER DEFAULT 0",
"ALTER TABLE chain_posts ADD COLUMN chain_type TEXT DEFAULT 'depth'",
"ALTER TABLE chain_posts ADD COLUMN angle TEXT",
"ALTER TABLE chain_posts ADD COLUMN category_guess TEXT",
"ALTER TABLE chain_posts ADD COLUMN bridge_logic TEXT",
"ALTER TABLE chain_posts ADD COLUMN draft_md TEXT",
"ALTER TABLE chain_posts ADD COLUMN slug TEXT",
# Phase 2→3
"ALTER TABLE chain_posts ADD COLUMN published_url TEXT",
"ALTER TABLE chain_posts ADD COLUMN published_at TEXT",
"ALTER TABLE chain_posts ADD COLUMN card_injected INTEGER DEFAULT 0",
"ALTER TABLE chain_posts ADD COLUMN card_injected_at TEXT",
"ALTER TABLE chain_posts ADD COLUMN publish_method TEXT",
# Phase 10: ImageMeta consolidation (legacy columns removed in v1 migration)
    "ALTER TABLE chain_posts ADD COLUMN image_meta TEXT",
        # Phase 21: Smoke test columns
    "ALTER TABLE chain_posts ADD COLUMN smoke_test_checked_at TEXT",
    "ALTER TABLE chain_posts ADD COLUMN smoke_test_result TEXT",
    "ALTER TABLE chain_posts ADD COLUMN smoke_test_detail TEXT",
        # Phase 22: Quality warnings column
    "ALTER TABLE chain_posts ADD COLUMN quality_warnings TEXT",
]


def _run_migrations():
    """Phase 1 DB에 Phase 2 컬럼이 없으면 추가."""
    conn = get_conn()
    cursor = conn.execute("PRAGMA table_info(chains)")
    chains_cols = {row["name"] for row in cursor.fetchall()}
    cursor = conn.execute("PRAGMA table_info(chain_posts)")
    posts_cols = {row["name"] for row in cursor.fetchall()}

    for sql in MIGRATIONS_SQL:
        # 컬럼명 추출: "ALTER TABLE xxx ADD COLUMN col_name TYPE ..."
        col_name = sql.split("ADD COLUMN ")[1].split(" ")[0]
        table_name = "chains" if "chains" in sql.split("ALTER TABLE ")[1].split(" ")[0] else "chain_posts"
        cols = chains_cols if table_name == "chains" else posts_cols
        if col_name not in cols:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # 이미 존재하는 경우 무시
    conn.commit()
    conn.close()


def init_db():
    """Create tables if they don't exist + run migrations."""
    conn = get_conn()
    conn.executescript(SCHEMA_SQL)
    conn.executescript(KEYWORD_QUEUE_SCHEMA_SQL)
    conn.commit()
    conn.close()
    _run_migrations()
    _run_migrate_drop_legacy_image_columns()


def _run_migrate_drop_legacy_image_columns():
    """Wrapper that checks user_version and runs drop migration if needed."""
    conn = get_conn()
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version >= 1:
        conn.close()
        return

    # Check if legacy columns exist before attempting migration
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(chain_posts)")}
    conn.close()

    has_legacy = {"image_keyword", "chart_type", "thumbnail_path"} & cols
    if has_legacy:
        migrate_image_columns()
        migrate_drop_legacy_image_columns()
    else:
        # New database — just bump version
        conn = get_conn()
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        conn.close()


def migrate_image_columns():
    from chain_models import ImageMeta as ImageMetaDB

    conn = get_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, image_keyword, image_url, thumbnail_path, thumbnail_source,
                  content_image_path, content_image_source,
                  chart_type, chart_data, image_reason, image_meta
           FROM chain_posts"""
    ).fetchall()

    migrated = 0
    skipped = 0
    for row in rows:
        if row["image_meta"]:
            skipped += 1
            continue

        meta = ImageMetaDB(
            image_keyword=row["image_keyword"],
            image_url=row["image_url"],
            thumbnail_path=row["thumbnail_path"],
            thumbnail_source=row["thumbnail_source"],
            content_image_path=row["content_image_path"],
            content_image_source=row["content_image_source"],
            chart_type=row["chart_type"],
            chart_data=json.loads(row["chart_data"]) if row["chart_data"] else None,
            image_reason=row["image_reason"],
        )

        if row["chart_type"]:
            meta.image_type = "chart"
        elif row["image_keyword"]:
            meta.image_type = "photo"
        else:
            meta.image_type = "none"

        conn.execute(
            "UPDATE chain_posts SET image_meta=? WHERE id=?",
            (meta.model_dump_json(), row["id"]),
        )
        migrated += 1

    conn.commit()
    conn.close()
    print(f"  [migrate] image_meta 마이그레이션 완료: {migrated}개 생성, {skipped}개 스킵 (이미 존재)")
    return migrated


_LEGACY_IMAGE_COLUMNS = [
    "image_keyword",
    "chart_type",
    "chart_data",
    "image_reason",
    "thumbnail_path",
    "thumbnail_source",
    "content_image_path",
    "content_image_source",
]


def migrate_drop_legacy_image_columns():
    """Backfill NULL image_meta from legacy columns, then DROP legacy image columns.

    Prerequisite: all image_meta IS NULL records must be backfillable from
    legacy columns. Caller should check first with:
        SELECT COUNT(*) FROM chain_posts
        WHERE (image_meta IS NULL OR image_meta = '')
          AND (image_keyword IS NOT NULL OR ...);
    If > 0, backfill with {} (no image data).
    """
    conn = get_conn()
    cursor = conn.execute("PRAGMA user_version")
    current_version = cursor.fetchone()[0]
    _TARGET_VERSION = 1

    if current_version >= _TARGET_VERSION:
        conn.close()
        return

    # Step 1: Backfill NULL image_meta
    conn.row_factory = sqlite3.Row
    missing = conn.execute(
        "SELECT id, image_keyword, chart_type, chart_data, image_reason, "
        "thumbnail_path, thumbnail_source, content_image_path, "
        "content_image_source FROM chain_posts "
        "WHERE image_meta IS NULL OR image_meta = ''"
    ).fetchall()

    from chain_models import ImageMeta as ImageMetaDB

    for row in missing:
        populated = any(row[c] for c in _LEGACY_IMAGE_COLUMNS)
        if populated:
            meta = ImageMetaDB(
                image_keyword=row["image_keyword"],
                thumbnail_path=row["thumbnail_path"],
                thumbnail_source=row["thumbnail_source"],
                content_image_path=row["content_image_path"],
                content_image_source=row["content_image_source"],
                chart_type=row["chart_type"],
                chart_data=json.loads(row["chart_data"]) if row["chart_data"] else None,
                image_reason=row["image_reason"],
            )
            if row["chart_type"]:
                meta.image_type = "chart"
            elif row["image_keyword"]:
                meta.image_type = "photo"
            else:
                meta.image_type = "none"
        else:
            meta = ImageMetaDB()
        conn.execute(
            "UPDATE chain_posts SET image_meta=? WHERE id=?",
            (meta.model_dump_json(), row["id"]),
        )

    conn.commit()

    # Step 2: DROP legacy columns
    for col in _LEGACY_IMAGE_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE chain_posts DROP COLUMN {col}")
        except sqlite3.OperationalError as e:
            print(f"  [migrate] DROP COLUMN {col} 스킵: {e}")

    conn.execute(f"PRAGMA user_version = {_TARGET_VERSION}")
    conn.commit()
    conn.close()
    print(f"  [migrate] 레거시 {len(_LEGACY_IMAGE_COLUMNS)}개 컬럼 DROP 완료 (version {_TARGET_VERSION})")


# ── Chain CRUD ──

def create_chain(seed: str, depth_count: int = 3, chain_type: str = "depth") -> int:
    """Insert a new chain row, return chain_id."""
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO chains (seed, depth_count, chain_type, status, created_at, updated_at) VALUES (?, ?, ?, 'derived', ?, ?)",
        (seed, depth_count, chain_type, now, now),
    )
    conn.commit()
    chain_id = cur.lastrowid
    conn.close()
    return chain_id


def get_chain(chain_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM chains WHERE id = ?", (chain_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_chains() -> list[dict]:
    """Return all chains ordered by id descending."""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM chains ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_chain_status(chain_id: int, status: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chains SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, chain_id),
    )
    conn.commit()
    conn.close()


def update_chain_type(chain_id: int, chain_type: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chains SET chain_type = ?, updated_at = ? WHERE id = ?",
        (chain_type, now, chain_id),
    )
    conn.commit()
    conn.close()


# ── ChainPost CRUD ──

def create_chain_post(chain_id: int, depth: int, title: str,
                      target_keyword: str = None,
                      key_points: list = None,
                      image_prompt: str = None,
                      step: int = None,
                      chain_type: str = None,
                      angle: str = None,
                      category_guess: str = None,
                      bridge_logic: str = None) -> int:
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        """INSERT INTO chain_posts
           (chain_id, depth, step, chain_type, title, target_keyword, key_points,
            angle, category_guess, bridge_logic, image_prompt,
            status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'derived', ?, ?)""",
        (chain_id, depth, step or depth + 1, chain_type or "depth", title,
         target_keyword,
         json.dumps(key_points, ensure_ascii=False) if key_points else None,
         angle, category_guess, bridge_logic, image_prompt,
         now, now),
    )
    conn.commit()
    post_id = cur.lastrowid
    conn.close()
    return post_id


def get_chain_posts(chain_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chain_posts WHERE chain_id = ? ORDER BY depth", (chain_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("key_points"):
            try:
                d["key_points"] = json.loads(d["key_points"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result


def get_post(post_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM chain_posts WHERE id = ?", (post_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        if d.get("key_points"):
            try:
                d["key_points"] = json.loads(d["key_points"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d
    return None


def update_post_status(post_id: int, status: str, error_log: str = None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    if error_log:
        conn.execute(
            "UPDATE chain_posts SET status = ?, error_log = ?, updated_at = ? WHERE id = ?",
            (status, error_log, now, post_id),
        )
    else:
        conn.execute(
            "UPDATE chain_posts SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, post_id),
        )
    conn.commit()
    conn.close()


def update_post_image(post_id: int, image_url: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET image_url = ?, status = 'image_generated', updated_at = ? WHERE id = ?",
        (image_url, now, post_id),
    )
    conn.commit()
    conn.close()


def update_post_image_prompt(post_id: int, image_prompt: str):
    """실제 Pollinations 전달 프롬프트를 DB image_prompt에 저장."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET image_prompt = ?, updated_at = ? WHERE id = ?",
        (image_prompt, now, post_id),
    )
    conn.commit()
    conn.close()


from chain_models import ImageMeta as ImageMetaDB

def update_image_meta(post_id: int, image_meta):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(image_meta, dict):
        meta = ImageMetaDB(**image_meta)
    else:
        meta = image_meta
    meta_json = meta.model_dump_json()
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET image_meta=?, updated_at=? WHERE id=?",
        (meta_json, now, post_id),
    )
    conn.commit()
    conn.close()


def get_image_meta(post_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT image_meta FROM chain_posts WHERE id=?", (post_id,)).fetchone()
    conn.close()
    if row and row["image_meta"]:
        try:
            return json.loads(row["image_meta"])
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def update_post_draft(post_id: int, draft_md: str, slug: str):
    """Save draft content and slug, set status = 'drafted'."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET draft_md = ?, slug = ?, status = 'drafted', updated_at = ? WHERE id = ?",
        (draft_md, slug, now, post_id),
    )
    conn.commit()
    conn.close()


def update_quality_warnings(post_id: int, warnings: list):
    """품질 경고 리스트를 JSON으로 저장."""
    import json
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET quality_warnings = ?, updated_at = ? WHERE id = ?",
        (json.dumps(warnings), now, post_id),
    )
    conn.commit()
    conn.close()


def update_post_published_md(post_id: int, published_md: str):
    """Save R2-replaced content for card injection to use (preserves draft_md original)."""
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET published_md = ? WHERE id = ?",
        (published_md, post_id),
    )
    conn.commit()
    conn.close()


def update_post_published(post_id: int, hugo_file_path: str):
  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  conn = get_conn()
  conn.execute(
    "UPDATE chain_posts SET hugo_file_path = ?, status = 'published', updated_at = ? WHERE id = ?",
    (hugo_file_path, now, post_id),
  )
  conn.commit()
  conn.close()

# ── Phase 7: Thumbnail / Content Image helpers ────────────────────

def _merge_image_meta(post_id: int, updates: dict) -> bool:
    """Read current image_meta JSON, merge updates, write back."""
    conn = get_conn()
    row = conn.execute("SELECT image_meta FROM chain_posts WHERE id=?", (post_id,)).fetchone()
    if not row:
        conn.close()
        return False
    meta = json.loads(row["image_meta"]) if row["image_meta"] else {}
    meta.update(updates)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE chain_posts SET image_meta=?, updated_at=? WHERE id=?",
        (json.dumps(meta, ensure_ascii=False), now, post_id),
    )
    conn.commit()
    conn.close()
    return True

def update_thumbnail(post_id: int, path: str, source: str):
    """Save thumbnail path + source to image_meta JSON. Idempotent (skips if already set)."""
    conn = get_conn()
    row = conn.execute("SELECT image_meta FROM chain_posts WHERE id=?", (post_id,)).fetchone()
    if not row:
        conn.close()
        return
    meta = json.loads(row["image_meta"]) if row["image_meta"] else {}
    if meta.get("thumbnail_path"):
        conn.close()
        return
    meta["thumbnail_path"] = path
    meta["thumbnail_source"] = source
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE chain_posts SET image_meta=?, updated_at=? WHERE id=?",
        (json.dumps(meta, ensure_ascii=False), now, post_id),
    )
    conn.commit()
    conn.close()

def update_content_image(post_id: int, path: str, source: str):
    """Save content image path + source to image_meta JSON."""
    _merge_image_meta(post_id, {"content_image_path": path, "content_image_source": source})

def update_chart(post_id: int, chart_type: str, chart_data: str):
    """Save chart_type + chart_data to image_meta JSON."""
    _merge_image_meta(post_id, {"chart_type": chart_type, "chart_data": chart_data})

# ── Phase 3: 발행 URL 관리 ──

def update_published_url(post_id: int, url: str, method: str):
    """발행 완료 후 URL + 방식 저장. status='published' 전환."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET published_url = ?, publish_method = ?, "
        "published_at = ?, status = 'published', error_log = '', updated_at = ? WHERE id = ?",
        (url, method, now, now, post_id),
    )
    conn.commit()
    conn.close()


def update_card_injected(post_id: int):
    """카드 주입 완료 플래그 저장."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET card_injected = 1, card_injected_at = ?, updated_at = ? WHERE id = ?",
        (now, now, post_id),
    )
    conn.commit()
    conn.close()


def update_smoke_test_result(post_id: int, result: str, detail: dict = None) -> None:
    """Smoke test 결과 기록. result: 'pass' | 'fail'."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
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


def get_chain_posts_ordered(chain_id: int, direction: str = "asc") -> list[dict]:
    """step 기준 정순(asc) 또는 역순(desc) 조회."""
    order = "ASC" if direction.lower() == "asc" else "DESC"
    conn = get_conn()
    rows = conn.execute(
        f"SELECT * FROM chain_posts WHERE chain_id = ? ORDER BY step {order}", (chain_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("key_points"):
            try:
                d["key_points"] = json.loads(d["key_points"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result


def get_pending_card_injections(chain_id: int) -> list[dict]:
    """발행 완료되었으나 카드가 아직 주입되지 않은 posts."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chain_posts WHERE chain_id = ? AND published_url IS NOT NULL "
        "AND (card_injected IS NULL OR card_injected = 0) "
        "ORDER BY step ASC",
        (chain_id,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("key_points"):
            try:
                d["key_points"] = json.loads(d["key_points"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result


# ── Phase 5: publish_log (4-layer dedup layer 2) ──

def log_publish(blog_id: str, slug: str, published_url: str = None, publish_method: str = None):
    """발행 성공 기록 → 중복 발행 방지."""
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO publish_log (blog_id, slug, published_url, publish_method) "
        "VALUES (?, ?, ?, ?)",
        (blog_id, slug, published_url, publish_method),
    )
    conn.commit()
    conn.close()


def check_duplicate(blog_id: str, slug: str) -> bool:
    """이미 발행된 slug 인지 확인."""
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM publish_log WHERE blog_id = ? AND slug = ?", (blog_id, slug),
    ).fetchone()
    conn.close()
    return row is not None


def get_publish_log(blog_id: str = None, limit: int = 50) -> list[dict]:
    """발행 이력 조회 (blog_id 필터 선택)."""
    conn = get_conn()
    if blog_id:
        rows = conn.execute(
            "SELECT * FROM publish_log WHERE blog_id = ? ORDER BY published_at DESC LIMIT ?",
            (blog_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM publish_log ORDER BY published_at DESC LIMIT ?", (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Phase 6: Loop Funnel ──

LOOP_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS loop_chains (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id     INTEGER NOT NULL REFERENCES chains(id) ON DELETE CASCADE,
    hub_slug     TEXT    NOT NULL,
    hub_url      TEXT,
    spokes_count INTEGER DEFAULT 3,
    status       TEXT    NOT NULL DEFAULT 'hub_pending',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

LOOP_MIGRATIONS_SQL = [
    "ALTER TABLE chain_posts ADD COLUMN loop_role TEXT",
]


def init_loop_tables():
    """Create loop_chains table + run loop migrations."""
    conn = get_conn()
    conn.executescript(LOOP_SCHEMA_SQL)
    conn.commit()

    cursor = conn.execute("PRAGMA table_info(chain_posts)")
    posts_cols = {row["name"] for row in cursor.fetchall()}

    for sql in LOOP_MIGRATIONS_SQL:
        col_name = sql.split("ADD COLUMN ")[1].split(" ")[0]
        if col_name not in posts_cols:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass
    conn.commit()
    conn.close()


def insert_loop_chain(chain_id: int, hub_slug: str, spokes_count: int = 3) -> int:
    """Register a new loop chain. Returns loop_chain_id."""
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO loop_chains (chain_id, hub_slug, spokes_count, status) VALUES (?, ?, ?, 'hub_pending')",
        (chain_id, hub_slug, spokes_count),
    )
    conn.commit()
    lid = cur.lastrowid
    conn.close()
    return lid


def get_loop_chain(chain_id: int) -> Optional[dict]:
    """Get loop chain record for a chain_id."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM loop_chains WHERE chain_id = ? ORDER BY id DESC LIMIT 1",
        (chain_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_loop_chain_status(loop_chain_id: int, hub_url: str = None, status: str = None):
    """Update hub URL and/or status for a loop chain."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    parts = ["updated_at = ?"]
    vals = [now]
    if hub_url is not None:
        parts.append("hub_url = ?")
        vals.append(hub_url)
    if status is not None:
        parts.append("status = ?")
        vals.append(status)
    vals.append(loop_chain_id)
    conn.execute(
        f"UPDATE loop_chains SET {', '.join(parts)} WHERE id = ?", vals
    )
    conn.commit()
    conn.close()


def set_loop_role(post_id: int, role: str):
    """Set loop_role for a chain post: 'hub', 'spoke', or None to clear."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET loop_role = ?, updated_at = ? WHERE id = ?",
        (role, now, post_id),
    )
    conn.commit()
    conn.close()


def get_chain_posts_by_loop_role(chain_id: int, role: str) -> list[dict]:
    """Get chain posts filtered by loop_role."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chain_posts WHERE chain_id = ? AND loop_role = ? ORDER BY step",
        (chain_id, role),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Phase 7: Search Context ──

SEARCH_MIGRATIONS_SQL = [
    "ALTER TABLE chain_posts ADD COLUMN context_md TEXT",
    "ALTER TABLE chain_posts ADD COLUMN search_sources TEXT",
]


# Phase 34: raw_ai_output 컬럼 추가 (raw_output 관측 강화)

RAW_AI_OUTPUT_MIGRATION_SQL = [
    "ALTER TABLE chain_posts ADD COLUMN raw_ai_output TEXT",
]


# ── Phase 23: Keyword Queue ──

KEYWORD_QUEUE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS keyword_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    category TEXT,
    priority INTEGER DEFAULT 3,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    processed_at TEXT,
    chain_id INTEGER,
    error_msg TEXT
);

CREATE INDEX IF NOT EXISTS idx_keyword_queue_status ON keyword_queue(status);
CREATE INDEX IF NOT EXISTS idx_keyword_queue_priority ON keyword_queue(priority ASC, created_at ASC);
"""


def init_keyword_queue_table():
    """Create keyword_queue table if not exists."""
    conn = get_conn()
    conn.executescript(KEYWORD_QUEUE_SCHEMA_SQL)
    conn.commit()
    conn.close()


def add_keyword_queue(keyword: str, category: str = None, priority: int = 3) -> Dict:
    """Add keyword to queue. Returns dict with success status."""
    from datetime import datetime
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute(
            "INSERT INTO keyword_queue (keyword, category, priority, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (keyword, category, priority, now)
        )
        conn.commit()
        return {"success": True, "keyword": keyword, "status": "added"}
    except sqlite3.IntegrityError:
        # Check existing status
        row = conn.execute("SELECT status, category FROM keyword_queue WHERE keyword = ?", (keyword,)).fetchone()
        return {"success": False, "keyword": keyword, "status": "duplicate", "existing_status": row["status"] if row else None}
    finally:
        conn.close()


def get_next_keyword() -> Optional[Dict]:
    """Get next pending keyword by priority (high priority = low number = first)."""
    from datetime import datetime
    conn = get_conn()
    row = conn.execute(
        "SELECT id, keyword, category, priority FROM keyword_queue WHERE status = 'pending' ORDER BY priority ASC, created_at LIMIT 1"
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE keyword_queue SET status = 'processing', processed_at = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row["id"])
        )
        conn.commit()
        conn.close()
        return dict(row)
    conn.close()
    return None


def mark_keyword_done(keyword: str, chain_id: int):
    """Mark keyword as done with chain_id."""
    from datetime import datetime
    conn = get_conn()
    conn.execute(
        "UPDATE keyword_queue SET status = 'done', processed_at = ?, chain_id = ? WHERE keyword = ?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), chain_id, keyword)
    )
    conn.commit()
    conn.close()


def mark_keyword_failed(keyword: str, error_msg: str):
    """Mark keyword as failed with error message."""
    from datetime import datetime
    conn = get_conn()
    conn.execute(
        "UPDATE keyword_queue SET status = 'failed', processed_at = ?, error_msg = ? WHERE keyword = ?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), error_msg, keyword)
    )
    conn.commit()
    conn.close()


def list_keyword_queue(status: str = None) -> list[dict]:
    """List keyword queue entries."""
    conn = get_conn()
    if status:
        rows = conn.execute("SELECT * FROM keyword_queue WHERE status = ? ORDER BY priority ASC, created_at", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM keyword_queue ORDER BY priority ASC, created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remove_keyword_queue(queue_id: int) -> bool:
    """Remove keyword from queue (only pending)."""
    conn = get_conn()
    cur = conn.execute("DELETE FROM keyword_queue WHERE id = ? AND status = 'pending'", (queue_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def get_chains_since(date_str: str) -> list[dict]:
    """Get chains created since given date."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chains WHERE created_at >= ? ORDER BY created_at DESC",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def init_search_columns():
    """Add context_md and search_sources columns to chain_posts if missing."""
    conn = get_conn()
    cursor = conn.execute("PRAGMA table_info(chain_posts)")
    cols = {row["name"] for row in cursor.fetchall()}
    for sql in SEARCH_MIGRATIONS_SQL:
        col_name = sql.split("ADD COLUMN ")[1].split(" ")[0]
        if col_name not in cols:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass
    conn.commit()
    conn.close()


def update_post_context(post_id: int, context_md: str, search_sources: str = None):
    """Update context_md and search_sources for a chain post."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET context_md = ?, search_sources = ?, updated_at = ? WHERE id = ?",
        (context_md, search_sources, now, post_id),
    )
    conn.commit()
    conn.close()


# Phase 34: raw_ai_output 컬럼 마이그레이션 실행

def init_raw_ai_output_column():
    """Add raw_ai_output column to chain_posts if missing."""
    conn = get_conn()
    cursor = conn.execute("PRAGMA table_info(chain_posts)")
    cols = {row["name"] for row in cursor.fetchall()}
    for sql in RAW_AI_OUTPUT_MIGRATION_SQL:
        col_name = sql.split("ADD COLUMN ")[1].split(" ")[0]
        if col_name not in cols:
            try:
                conn.execute(sql)
                print(f"  [migrate] {col_name} 컬럼 추가 완료")
            except sqlite3.OperationalError:
                pass
    conn.commit()
    conn.close()


def update_post_raw_output(post_id: int, raw_md: str):
    """Save raw AI output (before any processing) to chain_posts.raw_ai_output."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET raw_ai_output = ?, updated_at = ? WHERE id = ?",
        (raw_md, now, post_id),
    )
    conn.commit()
    conn.close()


# ── Initialization Guard ──

if __name__ == "__main__":
    init_db()
    print(f"[mc] DB initialized at {_db_path()}")


# ── Phase 23: Keyword Queue Functions ──

def add_keyword_queue(keyword: str, category: str = None, priority: int = 3) -> dict:
    """Add keyword to queue. Returns dict with success status.
    Allows duplicate keywords (no UNIQUE constraint).
    If same keyword exists in 'done' status, warns but still adds."""
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Check for existing done keyword
    row = conn.execute("SELECT status FROM keyword_queue WHERE keyword = ? AND status = 'done'", (keyword,)).fetchone()
    if row:
        conn.close()
        return {"success": False, "keyword": keyword, "status": "duplicate", "existing_status": "done", "warning": f"Keyword '{keyword}' already completed (done)"}

    # Insert new keyword (allows duplicates for pending/processing/failed)
    cur = conn.execute(
        "INSERT INTO keyword_queue (keyword, category, priority, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
        (keyword, category, priority, now)
    )
    conn.commit()
    conn.close()
    return {"success": True, "id": cur.lastrowid, "keyword": keyword, "status": "added"}


def get_next_keyword() -> dict | None:
    """Get next pending keyword by priority (asc) and created_at (asc). Update to processing."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id, keyword, category, priority FROM keyword_queue WHERE status = 'pending' ORDER BY priority ASC, created_at ASC LIMIT 1"
    ).fetchone()
    if row:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE keyword_queue SET status = 'processing', processed_at = ? WHERE id = ?",
            (now, row["id"])
        )
        conn.commit()
        conn.close()
        return dict(row)
    conn.close()
    return None


def mark_keyword_done(keyword: str, chain_id: int):
    """Mark keyword as done with chain_id."""
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE keyword_queue SET status = 'done', processed_at = ?, chain_id = ? WHERE keyword = ?",
        (now, chain_id, keyword)
    )
    conn.commit()
    conn.close()


def mark_keyword_failed(keyword: str, error_msg: str):
    """Mark keyword as failed with error message."""
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE keyword_queue SET status = 'failed', processed_at = ?, error_msg = ? WHERE keyword = ?",
        (now, error_msg, keyword)
    )
    conn.commit()
    conn.close()


def list_keyword_queue(status: str = None) -> list[dict]:
    """List keywords in queue, optionally filtered by status."""
    conn = get_conn()
    if status:
        rows = conn.execute("SELECT * FROM keyword_queue WHERE status = ? ORDER BY priority ASC, created_at ASC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM keyword_queue ORDER BY priority ASC, created_at ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_chains_since(date_str: str) -> list[dict]:
    """Get chains created since date."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chains WHERE created_at >= ? ORDER BY created_at DESC",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
