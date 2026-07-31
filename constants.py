"""
constants.py — 공통 상수 모듈 (Phase 26)

여러 파일에 분산된 상수 (도메인 화이트리스트/블랙리스트, 정규식 패턴) 를
한 곳으로 모은다. 단일 진실 공급원(single source of truth).

소유권 규칙:
  - 릭 방어 패턴(LEAK_PATTERNS/LEAK_REGEX) 의 단일 진실 공급원은
    config/leak_defense.yaml 이며 mc.leak_defense 가 로드한다.
    reload_config() 동작 보존을 위해 이곳은 re-export 만 한다 (복제 금지).
"""

import re

# ── 공신력 도메인 화이트리스트 (chain_card_injector 에서 이동) ─────────

AUTHORITY_GOVERNMENT = (".go.kr", ".or.kr", ".gov.kr")
AUTHORITY_PLATFORMS = {
    "place.naver.com": "네이버 플레이스",
    "map.naver.com": "네이버 지도",
    "map.kakao.com": "카카오맵",
    "instagram.com": "인스타그램",
    "facebook.com": "페이스북",
}
SKIP_DOMAINS = (
    "naver.com", "blog.naver.com", "brunch.co.kr", "tistory.com",
    "velog.io", "medium.com", "news.naver.com", "dispatch.co.kr",
    "youtube.com", "wikipedia.org",
)
SKIP_PATHS = (
    "/board/", "/faq", "/customer", "/bbs/", "/menu/",
    "/cruiseinfo/", "/useinfo/", "/terms/", "/?type=",
)

# 통합 공신력 도메인 집합: 정부/기관 접미사 + 인정 플랫폼 도메인.
# (카드 주입 외 모듈이 공신력 판별 목적으로 사용하는 내보내기용 상수)
AUTHORITY_DOMAINS = AUTHORITY_GOVERNMENT + tuple(AUTHORITY_PLATFORMS.keys())

# ── URL / 이메일 감지 정규식 ───────────────────────────────────────────

# URL 감지: http(s):// 로 시작하는 연속 문자.
# 마크다운 링크 [text](url) 와 문장 부호를 고려해 닫는 괄호/따옴표/<>/{} 제외.
URL_PATTERN = re.compile(r"https?://[^\s<>\"'()\[\]{}]+")

# 이메일 감지: 표준 이메일 형식
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# ── HTML 태그 감지 (chain_publisher_core 에서 이동) ──────────────────────
# _extract_clean_body() 와 _verify_before_deploy() 에서 공용으로 사용.
HTML_TAG_RE = re.compile(r'<(?:div|span|meta|script|ins|link|p|a|table|blockquote|figure|del)[\s>/]')

# ── R2 이미지 도메인 (chain_publisher_core 에서 이동) ────────────────────
R2_IMAGE_DOMAINS = ("r2.dev", "img.")

# ── 릭 방어 패턴 — yaml 기반 re-export (복제 금지) ───────────────────────
# 단일 진실 공급원: config/leak_defense.yaml (mc/leak_defense.py 가 로드,
# reload_config() 로 재로드 가능). 여기서는 동일 객체를 노출할 뿐이다.
from mc.leak_defense import (  # noqa: E402 — 상수 모듈 하단에서 의도적 import
    LEAK_PATTERNS as LEAK_PATTERNS,
    LEAK_REGEX as LEAK_REGEX,
)
