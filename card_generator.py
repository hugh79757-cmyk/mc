"""
card_generator.py — 카드 스펙 생성 단일 진실 공급원 (Phase 26 W2)

링크 dict + 포스트 메타데이터 → 카드 스펙(dict) 변환을 담당한다.
스펙은 순수 데이터 dict 이며, html_renderer.HtmlRenderer 가 이를 받아
최종 HTML 문자열을 렌더링한다.

목표: 기존 chain_card_injector.CardInjector 의 카드 HTML 생성 의미론(semantics)을
그대로 재현하는 것. 02-03 퍼사드 리팩터링에서 출력이 바이트 단위로 동일해야
하므로(스냅샷 동등성), 여기서 생성하는 스펙의 기본값/슬라이싱/분기 규칙은
기존 build_card_html / build_official_card_html / build_external_link_card 의
구현과 1:1 대응한다.

카드 스펙 타입:
  - "none"      — 렌더링할 내용 없음 (빈 문자열 반환 대상)
  - "next"      — 다음 글 카드 ({{< chain-card >}} shortcode)
  - "internal"  — 내부 이동 카드 ({{< chain-card >}} shortcode, next 와 동일 구조)
  - "official"  — 공식 안내 카드 ({{< chain-official-card >}} shortcode)
  - "external"  — 외부 링크 카드 (primary/secondary/fallback 복합 raw HTML)
"""

from __future__ import annotations

from typing import Any, Optional


class CardGenerator:
    """링크 dict + 포스트 메타데이터 → 카드 스펙 dict 생성.

    상태를 갖지 않는 순수 생성기. T-26-12: 입력 값 타입을 검증하여
    잘못된 타입(비문자열)이 스펙에 흘러들어 HTML 을 오염시키는 것을 차단한다.
    """

    # ── 입력 검증 (T-26-12) ────────────────────────────────────

    @staticmethod
    def _validate_str(value: Any, field: str) -> str:
        """field 가 str 인지 검증. 아니면 ValueError (비문자열 HTML 오염 방지).

        기존 구현은 f-string 보간으로 임의 객체를 str() 로 강제 변환했으나,
        이는 'None'/'123' 같은 문자열이 아닌 값이 카드 HTML 에 그대로
        노출되는 원인이 된다. 카드에 들어가는 title/url/cta/label 은
        전부 문자열이어야 하므로 비문자열 입력은 명시적으로 거부한다.
        """
        if not isinstance(value, str):
            raise ValueError(
                f"card field '{field}' must be a string, got {type(value).__name__}: {value!r}"
            )
        return value

    # ── next/internal 카드 (chain-card shortcode) ──────────────

    def generate_next_card_spec(self, title: str, url: str, cta: str) -> dict:
        """다음 글 카드 스펙 생성 ({{< chain-card >}}).

        기존 CardInjector.build_card_html(title, url, cta) 와 1:1 대응.
        """
        return {
            "type": "next",
            "title": self._validate_str(title, "title"),
            "url": self._validate_str(url, "url"),
            "cta": self._validate_str(cta, "cta"),
        }

    def generate_internal_card_spec(self, title: str, url: str, cta: str) -> dict:
        """내부 이동 카드 스펙 생성.

        next 와 동일한 chain-card shortcode 구조. 의미적 구분만 다르고
        렌더링 결과는 동일하다 (02-03 퍼사드의 build_card_html 호환).
        """
        return {
            "type": "internal",
            "title": self._validate_str(title, "title"),
            "url": self._validate_str(url, "url"),
            "cta": self._validate_str(cta, "cta"),
        }

    def generate_chain_card_spec(self, card_type: str, title: str, url: str, cta: str) -> dict:
        """next/internal 공용 생성 (card_type: 'next' | 'internal')."""
        if card_type not in ("next", "internal"):
            raise ValueError(f"chain-card type must be 'next' or 'internal', got {card_type!r}")
        return {
            "type": card_type,
            "title": self._validate_str(title, "title"),
            "url": self._validate_str(url, "url"),
            "cta": self._validate_str(cta, "cta"),
        }

    # ── official 카드 (chain-official-card shortcode) ─────────

    def generate_official_card_spec(self, link: Optional[dict]) -> dict:
        """공식 안내 카드 스펙 생성 ({{< chain-official-card >}}).

        기존 CardInjector.build_official_card_html(link) 와 1:1 대응.
        link 가 falsy(빈 dict 포함)면 {"type": "none"} → 렌더 결과 빈 문자열.
        """
        if not link:
            return {"type": "none"}
        return {
            "type": "official",
            "title": self._validate_str(link.get("title", "공식 안내"), "title"),
            "url": self._validate_str(link.get("url", "https://www.gov.kr"), "url"),
            "label": self._validate_str(link.get("label", "공식 사이트"), "label"),
        }

    # ── external 카드 (primary/secondary/fallback 복합) ────────

    def generate_external_card_spec(self, links: dict, seed_keyword: str = "") -> dict:
        """외부 링크 카드 스펙 생성 (Depth 2, 공신력 우선순위).

        기존 CardInjector.build_external_link_card(links, seed_keyword) 와
        1:1 대응. 분기 규칙:
          - primary 가 truthy → primary 블록 렌더 (url 필수 — 없으면 기존과
            동일하게 KeyError 전파)
          - secondary 가 truthy → 최대 2개 슬라이싱해 secondary 블록 렌더
          - 위 둘 다 없으면 fallback 블록 렌더 (url/label 기본값 + seed_keyword)

        Args:
            links: {"primary": {...}, "secondary": [...], "fallback": {...}}
            seed_keyword: fallback 라벨 기본값에 쓰이는 원본 주제 키워드
        """
        primary = links.get("primary")
        secondary = links.get("secondary", [])
        fallback = links.get("fallback", {})

        spec: dict = {
            "type": "external",
            "seed_keyword": self._validate_str(seed_keyword, "seed_keyword"),
            "primary": None,
            "secondary": [],
            "fallback": None,
        }

        if primary:
            # url 필수: 기존 구현과 동일하게 KeyError 전파 (유효하지 않은 링크)
            spec["primary"] = {
                "url": self._validate_str(primary["url"], "primary.url"),
                "label": self._validate_str(primary.get("label", "공식 사이트"), "primary.label"),
                "title": self._validate_str(
                    primary.get("title", primary.get("label", "공식 사이트")), "primary.title"
                ),
            }

        if secondary:
            spec["secondary"] = [
                {
                    "url": self._validate_str(s["url"], "secondary.url"),
                    "label": self._validate_str(s.get("label", "더 보기"), "secondary.label"),
                }
                for s in secondary[:2]
            ]

        if not spec["primary"] and not spec["secondary"]:
            # fallback 블록은 primary/secondary 가 없을 때 항상 렌더됨
            if not fallback:
                fallback = {}
            spec["fallback"] = {
                "url": self._validate_str(fallback.get("url", "#"), "fallback.url"),
                "label": self._validate_str(
                    fallback.get("label", f"네이버에서 '{seed_keyword}' 검색"), "fallback.label"
                ),
            }

        return spec
