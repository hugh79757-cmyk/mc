"""
link_finder.py — 링크 추출 모듈 (Phase 26, Wave 2)

HTML / 마크다운 / 일반 텍스트에서 http(s) 외부 링크를 추출하는
LinkFinder 클래스. chain_card_injector 의 링크 추출 로직을 대체할
단일 진실 공급원(single source of truth) 모듈.

추출 형식 (결과 dict 의 kind 값):
  - "html"     — <a href="URL">앵커 텍스트</a>
  - "markdown" — [앵커 텍스트](URL)
  - "bare"     — 본문에 그대로 노출된 순수 URL

각 결과 dict:
  - url       : 정규화된 URL (url_utils.normalize_url — 트래킹 파라미터 제거,
                fragment 제거, scheme/host 소문자화)
  - raw_url   : 원본 텍스트에서 추출한 정규화 전 URL
                (HTML 앵커 href 는 엔티티 언이스케이프 후)
  - text      : 앵커 텍스트 (html/markdown) 또는 주변 문맥 스니펫 (bare)
  - position  : 원본 텍스트 내 URL 시작 문자 오프셋
  - end       : 원본 텍스트 내 URL 끝 문자 오프셋 (exclusive)
  - kind      : "html" | "markdown" | "bare"

보안 (Phase 26 threat register):
  - T-26-10 (Information Disclosure): 입력 크기 상한 — 기본 1MB 문자 초과 시
    ValueError 발생 (메모리 보호).
  - T-26-11 (Denial of Service): ReDoS 완화 — 중첩/지수 역추적이 불가능한
    단순 정규식만 사용한다 (단일 문자 클래스 부정 + 리터럴 + non-greedy).
    constants.URL_PATTERN 은 선형(linear) 문자 클래스 부정 패턴이며, HTML/MD
    패턴 역시 중첩 양자화(nested quantifier)가 없다. 입력 크기 상한이 추가
    안전판 역할을 한다.

알려진 제한 (T-26-11 안전 우선 트레이드오프):
  - 마크다운 URL 안의 괄호: [t](https://en.wikipedia.org/wiki/Foo_(bar)) 는
    첫 ')' 에서 잘린다 (균형 괄호 매칭은 역추적 복잡도 증가로 미지원).
  - 상대 URL(/path), 앵커(#frag), 스킴 없는 URL(www.example.com) 은 추출
    대상이 아니다. HTML href 의 프로토콜 상대 URL(//host) 은 https 로 해석.
  - IDN/punycode 도메인은 정규화로 그대로 보존된다 (디코딩하지 않음 —
    url_utils.decode_idn 은 별도 호출 경로).
  - 코드 펜스(``` / ~~~) 내부의 URL은 코드로 간주해 추출하지 않는다.
"""

from __future__ import annotations

import html
import re
from typing import Any

from constants import URL_PATTERN
from url_utils import normalize_url

# T-26-10: 입력 크기 상한 (문자 수). 1MB 문자 ≈ UTF-8 한글 기준 약 3MB.
DEFAULT_MAX_INPUT_CHARS = 1_048_576

# T-26-11: 모든 패턴은 중첩 양자화(nested quantifier) 없음 → 지수 역추적 불가.

# bare URL 검색: constants.URL_PATTERN 의 패턴 문자열을 재사용하되 대소문자
# 무시로 컴파일 (HTTP:// 와 같은 대문자 스킴도 추출 — normalize_url 이 소문자화).
# 문자 클래스 부정 + 리터럴만 사용하므로 여전히 선형 시간이다 (T-26-11).
_URL_RE = re.compile(URL_PATTERN.pattern, re.IGNORECASE)

# HTML 앵커 전체: <a ...>내용</a> — 속성(1)과 내용(2) 분리 캡처.
# (?=[\s>/]) 로 `<a` 뒤가 공백/태그끝/self-close 인 경우만 매칭 (<abbr 등 오탐 방지).
_ANCHOR_RE = re.compile(r"<a(?=[\s>/])([^>]*)>(.*?)</a>", re.IGNORECASE | re.DOTALL)
# href 속성 값 추출: 따옴표 / 무따옴표 모두 지원.
# (?<![\w-]) 로 data-href 등 하이픈 접두 속성 오탐 방지.
_HREF_RE = re.compile(r"(?<![\w-])href\s*=\s*([\"']?)([^\"'>\s]+)\1", re.IGNORECASE)
# 마크다운 인라인 링크: [텍스트](URL)
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
# 일반 HTML 태그 (bare URL 중복 추출 방지용 — <img src>, <script src> 등 제외)
_TAG_RE = re.compile(r"<[^>]+>")
# 코드 펜스 (``` / ~~~) — 내부 URL은 코드로 간주 (html/markdown/bare 모두 제외)
_FENCE_RE = re.compile(
    r"^(?:`{3,}|~{3,})[^\n]*\n.*?^(?:`{3,}|~{3,})\s*$",
    re.MULTILINE | re.DOTALL,
)
# bare URL 끝에 붙은 문장 부호 (마침표/쉼표/세미콜론 등)
_TRAILING_PUNCT = ".,;:!?)]}>'\""


def _collapse_ws(s: str) -> str:
    """연속 공백/개행을 단일 공백으로 압축 후 양끝 trim."""
    return re.sub(r"\s+", " ", s).strip()


def _overlaps_any(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    """start..end 구간이 spans 중 하나와 겹치면 True."""
    return any(s < end and start < e for s, e in spans)


class LinkFinder:
    """텍스트에서 외부 링크를 추출하는 클래스.

    HTML 앵커 → 마크다운 링크 → bare URL 순으로 추출하며, 더 구체적인
    형식(html/markdown)에 포함된 URL이 bare 로 중복 추출되지 않도록 한다.
    결과는 텍스트 내 위치(position) 순으로 정렬되고, 기본적으로 정규화된
    URL 기준 중복 제거(dedupe=True) 후 반환된다.

    Attributes:
        max_input_chars: T-26-10 입력 길이 상한 (초과 시 ValueError).
        dedupe: True 이면 정규화 URL 기준 첫 발생(가장 이른 position)만 반환.
    """

    def __init__(
        self,
        max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
        dedupe: bool = True,
    ):
        self.max_input_chars = max_input_chars
        self.dedupe = dedupe

    # ── public ────────────────────────────────────────────────────────────

    def find_links(self, text: str) -> list[dict[str, Any]]:
        """텍스트에서 링크 목록을 추출한다.

        Args:
            text: HTML/마크다운/일반 텍스트 (str).

        Returns:
            position 순 정렬된 링크 dict 목록. 각 dict 는 url, raw_url,
            text, position, end, kind 키를 가진다.

        Raises:
            TypeError: text 가 문자열이 아닐 때.
            ValueError: text 길이가 max_input_chars 를 초과할 때 (T-26-10).
        """
        self._guard_input(text)
        found: list[dict[str, Any]] = []

        # 코드 펜스 내부는 코드 — 모든 종류의 링크 추출에서 제외
        fence_spans = [(m.start(), m.end()) for m in _FENCE_RE.finditer(text)]

        # 1) HTML 앵커
        anchor_spans: list[tuple[int, int]] = []
        for m in _ANCHOR_RE.finditer(text):
            if _overlaps_any(m.start(), m.end(), fence_spans):
                continue
            href_m = _HREF_RE.search(m.group(1))
            if href_m is None:
                continue
            raw_url = html.unescape(href_m.group(2)).strip()
            url = self._resolve_url(raw_url)
            if url is None:
                continue
            anchor_text = _collapse_ws(re.sub(r"<[^>]+>", "", m.group(2)))
            found.append({
                "url": url,
                "raw_url": raw_url,
                "text": anchor_text,
                "position": m.start(1) + href_m.start(2),
                "end": m.start(1) + href_m.end(2),
                "kind": "html",
            })
            anchor_spans.append((m.start(), m.end()))

        # 2) 마크다운 링크 (HTML 앵커/펜스 내부 중복 방지)
        md_spans: list[tuple[int, int]] = []
        for m in _MD_LINK_RE.finditer(text):
            if _overlaps_any(m.start(), m.end(), anchor_spans + fence_spans):
                continue
            raw_url = m.group(2).strip()
            url = self._resolve_url(raw_url)
            if url is None:
                continue
            found.append({
                "url": url,
                "raw_url": raw_url,
                "text": _collapse_ws(m.group(1)),
                "position": m.start(2),
                "end": m.end(2),
                "kind": "markdown",
            })
            md_spans.append((m.start(), m.end()))

        # 3) bare URL (태그/앵커/마크다운/펜스 내부 중복 방지)
        tag_spans = [(t.start(), t.end()) for t in _TAG_RE.finditer(text)]
        excluded = anchor_spans + md_spans + tag_spans + fence_spans
        for m in _URL_RE.finditer(text):
            if _overlaps_any(m.start(), m.end(), excluded):
                continue
            raw_url = m.group().rstrip(_TRAILING_PUNCT)
            if not raw_url:
                continue
            url = normalize_url(raw_url)
            if not url:
                continue
            found.append({
                "url": url,
                "raw_url": raw_url,
                "text": self._snippet(text, m.start(), m.start() + len(raw_url)),
                "position": m.start(),
                "end": m.start() + len(raw_url),
                "kind": "bare",
            })

        found.sort(key=lambda d: d["position"])
        if self.dedupe:
            found = self._dedupe(found)
        return found

    # ── internal ──────────────────────────────────────────────────────────

    def _guard_input(self, text: str) -> None:
        """T-26-10: 입력 타입/길이 검증."""
        if not isinstance(text, str):
            raise TypeError("text는 문자열이어야 합니다")
        if len(text) > self.max_input_chars:
            raise ValueError(
                f"입력 텍스트가 너무 깁니다: {len(text)} chars "
                f"(상한: {self.max_input_chars})"
            )

    def _resolve_url(self, raw_url: str) -> str | None:
        """원시 URL을 http(s) 절대 URL로 해석·정규화.

        - 프로토콜 상대(//host) → https:// 로 해석
        - http(s) 절대 URL만 통과 (대소문자 무시), 나머지(상대 경로/앵커/
          기타 스킴) 는 None
        """
        lowered = raw_url.lower()
        if lowered.startswith("//"):
            resolved = "https:" + raw_url
        elif lowered.startswith(("http://", "https://")):
            resolved = raw_url
        else:
            return None
        return normalize_url(resolved)

    def _snippet(self, text: str, start: int, end: int, radius: int = 24) -> str:
        """bare URL 주변 문맥 스니펫 (공백 압축, 경계 공백 보존).

        _collapse_ws 는 양끝 trim 때문에 URL 경계 공백이 사라지므로,
        내부 압축만 하는 re.sub 를 직접 사용한 뒤 전체를 trim 한다.
        """
        left = re.sub(r"\s+", " ", text[max(0, start - radius):start])
        right = re.sub(r"\s+", " ", text[end:end + radius])
        return f"{left}{text[start:end]}{right}".strip()

    def _dedupe(self, found: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """정규화 URL 기준 첫 발생만 유지 (position 순서 보존)."""
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for d in found:
            if d["url"] in seen:
                continue
            seen.add(d["url"])
            out.append(d)
        return out
