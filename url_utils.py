"""
url_utils.py — 통합 URL 처리 유틸 (Phase 26)

여러 모듈에 흩어진 URL 처리 로직 (도메인 추출, punycode 디코딩, 트래킹
파라미터 제거, 정규화) 의 단일 진실 공급원(single source of truth).

- extract_domain: URL에서 도메인(호스트) 추출 (포트/경로/쿼리 제거, 소문자화)
- decode_idn: punycode(xn--) 도메인을 유니코드로 디코딩 (chain_card_injector 에서 이동)
- strip_tracking_params: utm_* 및 알려진 트래킹 파라미터 제거
- normalize_url: 정규화 (트래킹 제거 + fragment 제거 + scheme/host 소문자화)
- ensure_scheme: 스킴 누락 시 https:// 보완

보안 (Phase 26 threat register):
  - T-26-04: 모든 입력은 예외-안전 처리 (오류 시 빈 문자열/원본 반환 — 오류 메시지 누출 없음)
  - T-26-05: 정규식/파서 기반 처리에 재귀 없음, 입력 크기 상한 적용 (ReDoS 완화)
"""

from urllib.parse import urlsplit, urlunsplit

# T-26-05: 입력 크기 상한 — 비정상적으로 긴 URL 거부 (ReDoS/메모리 완화).
MAX_URL_LENGTH = 8192  # 실제 사용되는 URL은 수백 자 내외

# 트래킹 파라미터 (소문자 키) — utm_* 프리픽스는 별도 처리.
# 널리 알려진 트래킹 파라미터만 포함 (source/ref 등 일반 파라미터는 보존).
TRACKING_PARAMS = frozenset({
    "fbclid", "gclid", "dclid", "gbraid", "wbraid", "msclkid",
    "mc_cid", "mc_eid", "_hsenc", "_hsmi", "igshid", "si",
    "ttclid", "twclid", "li_fat_id", "fb_action_ids", "fb_action_types",
    "spm", "from", "yclid", "srsltid",
})


def _guard_url(url: str):
    """T-26-05: 입력 검증 — 크기 상한 + 타입."""
    if url is None:
        return False
    if not isinstance(url, str):
        raise TypeError("url은 문자열이어야 합니다")
    return len(url) <= MAX_URL_LENGTH


def extract_domain(url: str) -> str:
    """URL에서 도메인(호스트) 추출.

    - 스킴 누락 시 https:// 를 가정해 파싱 (urlsplit 호환성) — 단, 스킴 없는
      입력은 도메인 형식(공백 없음 + dot 포함)을 검증해 쓰레기 입력을 배제
    - 포트, 경로, 쿼리, fragment 제거
    - 소문자 반환
    - 파싱 불가/오류 시 "" 반환 (T-26-04: 예외-안전)
    """
    if not url or not _guard_url(url):
        return ""
    try:
        had_scheme = "://" in url
        if not had_scheme:
            url = "https://" + url
        host = urlsplit(url).hostname
        if not host:
            return ""
        host = host.lower()
        if not had_scheme:
            # 스킴 없는 입력: 도메인 형식 검증 (공백/제어문자 불허, dot 필요)
            if any(c.isspace() or ord(c) < 32 for c in host):
                return ""
            if "." not in host:
                return ""
        return host
    except Exception:
        return ""


def decode_idn(domain: str) -> str:
    """punycode(xn--) 도메인을 유니코드로 디코딩. 실패 시 원본 반환."""
    if domain is None:
        return ""
    if not domain:
        return domain
    try:
        parts = domain.rsplit(".", 1)
        # xn-- 접두사가 있는 라벨만 디코딩
        decoded_parts = []
        for part in parts[0].split(".") if len(parts) > 1 else [parts[0]]:
            if not part:
                continue
            if part.startswith("xn--"):
                decoded_parts.append(part.encode("ascii").decode("idna"))
            else:
                decoded_parts.append(part)
        result = ".".join(decoded_parts)
        if len(parts) > 1:
            result += "." + parts[1]
        return result
    except Exception:
        return domain


def strip_tracking_params(url: str) -> str:
    """트래킹 파라미터 제거 (utm_* 및 TRACKING_PARAMS).

    원본 인코딩을 보존하며 (parse/re-encode 하지 않음) 트래킹 키만 걸러낸다.
    트래킹 파라미터만 있는 쿼리는 전체 제거.
    """
    if url is None:
        return ""
    if not url or not _guard_url(url):
        return url
    if "?" not in url:
        return url
    base, _, query = url.partition("?")
    frag = ""
    if "#" in query:
        query, _, frag = query.partition("#")
    if not query:
        return url

    kept = []
    for pair in query.split("&"):
        key = pair.split("=", 1)[0].lower()
        if key in TRACKING_PARAMS or key.startswith("utm_"):
            continue
        kept.append(pair)

    result = base + ("?" + "&".join(kept) if kept else "")
    if frag:
        result += "#" + frag
    return result


def normalize_url(url: str) -> str:
    """URL 정규화.

    1. 트래킹 파라미터 제거 (strip_tracking_params)
    2. fragment 제거
    3. scheme/host 소문자화 (path/query 는 대소문자 구분이므로 보존)
    """
    if url is None:
        return ""
    if not url or not _guard_url(url):
        return url
    url = strip_tracking_params(url)
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower() if parts.netloc else ""
    return urlunsplit((scheme, netloc, parts.path, parts.query, ""))


def ensure_scheme(url: str, scheme: str = "https") -> str:
    """스킴 누락 시 기본 스킴을 앞에 붙임. 이미 있으면 그대로."""
    if url is None:
        return ""
    if not url:
        return url
    return url if "://" in url else f"{scheme}://{url}"
