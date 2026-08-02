# RESEARCH.md — M2 정보가 3-블로그 체인 복제 타당성 조사 (Phase 37 사전)

**작성:** 2026-08-02 — 읽기 전용 조사 (수정/복제/발행 없음)
**목적:** 기존 mc를 복제해 informationhot.kr / kuta.informationhot.kr / 5.informationhot.kr
3-블로그 체인을 독립 레포로 운영하는 방안의 타당성과 필수 분리 지점 확정.

---

## 1. 복제 시 필수 분리 지점 (충돌 방지)

| 구분 | 현재 상태 (실측 근거) | 분리 방법 | 미분리 위험 |
|------|----------------------|-----------|-------------|
| **DB 경로** | `config/chain_config.yaml:204` `db_path: /Users/twinssn/Projects/5000/data/mc_chains.db` 절대경로. `mc_paths.py:36-40` `init_db_path()` → `chain_db.py:37 sqlite3.connect`. **5000 레포와 공유 중** (파일 실존 3.5MB, 8/2 13:34 수정) | 복제 레포 `chain_config.yaml` `db_path` → 복제 레포 내 경로. `init_db()`가 CREATE TABLE IF NOT EXISTS로 신규 스키마 자동 생성 | chain_id AUTOINCREMENT 재사용 + 같은 slug 크로스 발행. publish_log UNIQUE(blog_id,slug)가 부분 방어하나 카드/이미지 상태 오염. **최우선** |
| **shared 의존성** | `mc_paths.py:27` `PATH_5000="/Users/twinssn/Projects/5000"` 하드코딩 + sys.path 주입. `chain_publisher.py:38 / chain_drafter.py:38 / chain_deriver.py:18` `from shared.ai_writer import generate`. ai_writer.py는 `shared.env_loader`(5000/.env + ~/.env.common) + `5000/config/models.yaml`(CONFIG_DIR) 의존. pyproject.toml `include=["shared*"]` | **vendoring (대표 확정)**: ai_writer.py + env_loader.py + __init__.py + config/models.yaml 복사, mc_paths.py PATH_5000 제거 | 5000 변경 시 복제 레포 영향. vendoring 시 models.yaml 누락하면 import 시점 FileNotFoundError |
| **R2 경로** | `image/r2_uploader.py:29-38` `HUGO_R2_DOMAINS` site_path 부분문자열 매칭. 정보가 계열 중 **kuta 키만 존재** (images/kuta + img-kuta.informationhot.kr). informationhot/5.informationhot 키 **없음** → `chain_publisher_core.py:512` get_r2_config → (None,None) → 656행 `if r2_prefix and r2_domain:` 스킵 → 이미지 업로드 안 됨 | HUGO_R2_DOMAINS에 informationhot/5.informationhot 엔트리 추가. prefix/도메인 네이밍은 셋업 중 결정 (미확정) | info/5 카드·썸네일 broken image |
| **산출물 경로** | `mc_paths.py:19-20` OUTPUT_DIR/DRAFTS_DIR는 PROJECT_ROOT 하위. output/drafts/<chain_id>/step<N>/, output/images/ (chain_drafter.py:380/636, chain_publisher_core.py:637-652). .gitignore `output/` | 복제 시 자동 분리 | 없음 |
| **git** | origin 단일 `git@github.com:hugh79757-cmyk/mc.git`. 현재 브랜치 `feat/keyword-category-template` (main 공존, 작업 트리 클린). `feat/replace-informationhot-to-issue-techpawz`에서 정보가→issue.techpawz 교체 이력 (99979d5) | 복제 후 새 GitHub 레포 + origin 교체. `.env`는 git 미추적 → 복제 레포 `.env` 재생성 필수 (R2/KREA 키) | 두 레포 같은 origin push 충돌 |

## 2. informationhot 3개 인프라 실측

| 항목 | informationhot-hugo | kuta-hugo | 5.informationhot-hugo |
|------|-----|-----|-----|
| Hugo 디렉토리 | 존재 (`~/Projects/informationhot-hugo`) | 존재 (`~/Projects/kuta-hugo`) | 존재 (`~/Projects/5.informationhot-hugo`) |
| baseURL | hugo.toml 존재 (내용 실측 미완) | `config/_default/hugo.toml`: `https://kuta.informationhot.kr/` ✅ | **`https://example.org/` 플레이스홀더 ❌** |
| theme | Blowfish (+PaperMod submodule) | blowfish, themesDir=shared-themes ✅ | params.toml colorScheme만, theme 키 누락 의심 |
| CF Pages | `informationhot-hugo` + informationhot.kr ✅ | `kuta-hugo` + kuta.informationhot.kr ✅ | `5-informationhot` + 5.informationhot.kr ✅ |
| HTTPS | **200** (`Information HOT`) ✅ | **200** (`KUTALOG`) ✅ | **200** (`TEAM65`) ✅ |
| shortcode 3종 | **전부 없음** (linkcard.html만) ❌ | **전부 없음** (adsense/related-card.html만) ❌ | **shortcodes 디렉토리 없음** ❌ |
| AdSense | ca-pub-6677996696534146 일치 ✅ | ca-pub-6677996696534146 일치 ✅ | ca-pub-6677996696534146 일치 ✅ |
| R2 매핑 키 | **없음** ❌ | `kuta` 키 존재 ✅ | **없음** ❌ |
| 콘텐츠 글 수 | 536 | 2036 | 34 |
| static/ads.txt | 존재 | 없음 | 없음 |
| 배포 설정 | .github/indexnow.yml만 | 없음 | 없음 |

**판정:** 기본 인프라(도메인/CF Pages/AdSense) 준비됨. shortcode 3종 전부 미비 +
5.informationhot baseURL 플레이스홀더 + R2 키 부재(2곳)는 선행 셋업 필요.

## 3. chain_config 교체 지점 + 카드 색상

**교체 지점 (config/chain_config.yaml):**
1. `sites` (1-63행): 정보가 3개 Hugo 사이트 정의 추가 (hugo_root/cf_pages_project/permalink/content_dir/card_cta)
2. `chain_blogs` (95-98행): `{0: rotcha, 1: issue.techpawz, 2: techpawz}` → `{0: informationhot, 1: kuta, 2: 5_informationhot}`
3. `chain_blog_mapping.default` (99-113행): depth/swallow/lateral 리스트 교체 (chain_publisher.py:395-404 `_get_blog_for_step()` 소비)
4. `db_path` (204행): 복제 레포 내 경로
5. `65_informationhot` blogger 정의 (54-63행): blog_id="BLOGGER_BLOG_ID_HERE" 자리표시자 + config/blogger_credentials.json **파일 부재** → 실사용 불가 상태. 키 이름이 달라 충돌 없음. 처리 결정 필요.

**카드 색상 (대표 결정: 체인 카드만 파랑):**
- 체인 카드 색상은 사이트별 shortcode 템플릿 하드코딩 (rotcha/techpawz chain-card.html = #DC2626 빨강, chain-official-card = #16a34a 초록, dual-cta = bg-red-600)
- 정보가 사이트에 chain-card.html을 **파랑(#2563eb)** 으로 신규 생성하면 성립 ✅ (shortcode가 사이트 소유)
- **external 카드 예외**: html_renderer.py:108-117 primary #DC2626(빨강) / 119-134 secondary #2563eb(파랑) 사이트 무관 하드코딩 → 전면 파랑 통일 시 html_renderer.py 수정 필요 (이번엔 미포함)
- config/cta_templates.yaml `style: "red-bg"`는 메타 정보 — mc/cta.py:83-87은 shortcode 호출만 생성, 실제 색상은 사이트 shortcode가 결정

## 4. 종합 판정

- **복제 방식 타당** — 필수 분리 지점 모두 config/경로 레벨에서 해결 가능
- **선행 셋업 필수 (미비 5건)**: DB 분리 / .env 재생성 / shared vendoring / shortcode 3종 + 5.informationhot baseURL / R2 매핑 키
- **놓치면 위험**: DB 미분리 → 크로스 발행 (가장 큼). R2 키 미추가 → info/5 이미지 미업로드. shortcode 미설치 → 카드가 raw text 노출

## 5. 미확정 항목 (M2 이월)

1. R2 prefix/도메인 네이밍 (img-5.informationhot.kr 등 실제 R2 커스텀 도메인 바인딩 존재 여부 — Cloudflare 콘솔 확인)
2. informationhot-hugo 정확한 baseURL/theme 내용 (hugo.toml 미실측)
3. 5000 레포와의 발행 충돌 정합 (5000이 informationhot-hugo를 blog_id로 등록, dashboard/api.py:79 — 발행 파이프라인 여부 확인)
4. 정보가 사이트 기존 콘텐츠 slug 정합 (536/2036/34건 — MC 발행 slug 충돌 정책)
5. 65_informationhot blogger 정의 제거/유지

## 잔존 위험

- 조사는 읽기 전용이라 실데이터 검증(DB 조회, 발행 시뮬레이션) 미수행
- 카드 파랑은 external 카드에서 불완전 (html_renderer 하드코딩) — 전면 통일은 별도 결정 필요
