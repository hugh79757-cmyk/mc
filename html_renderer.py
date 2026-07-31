"""
html_renderer.py — 카드 HTML 렌더링 단일 진실 공급원 (Phase 26 W2)

card_generator.CardGenerator 가 만든 카드 스펙(dict) → 최종 HTML 문자열 렌더링.

템플릿은 기존 chain_card_injector.CardInjector 가 생성하던 HTML 과
바이트 단위로 동일하다. 02-03 퍼사드 리팩터링에서 이 렌더러가
build_card_html / build_official_card_html / build_external_link_card 의
출력을 그대로 대체한다 (스냅샷 동등성 요구).

T-26-13: 템플릿은 모듈 로드 시 고정된 상수 문자열이며 사용자 입력에 의해
템플릿 자체가 확장/변경되지 않는다. 렌더링 복잡도는 O(스펙 크기) 로
제한되며, 외부 링크 카드의 secondary 는 생성기에서 이미 2개로 슬라이싱된다.
"""

from __future__ import annotations

from typing import Any


class HtmlRenderer:
    """카드 스펙 dict → HTML 문자열 렌더러.

    상태를 갖지 않는 순수 렌더러. spec["type"] 으로 디스패치한다.
    """

    # ── 디스패치 ─────────────────────────────────────────────

    def render(self, spec: dict) -> str:
        """카드 스펙을 HTML 문자열로 렌더링.

        Args:
            spec: CardGenerator 가 생성한 카드 스펙 dict.

        Returns:
            렌더링된 HTML. type == "none" 이면 빈 문자열.
        """
        card_type = spec.get("type")
        if card_type == "none":
            return ""
        if card_type in ("next", "internal"):
            return self._render_chain_card(spec)
        if card_type == "official":
            return self._render_official_card(spec)
        if card_type == "external":
            return self._render_external_card(spec)
        raise ValueError(f"unknown card spec type: {card_type!r}")

    # ── next/internal: {{< chain-card >}} shortcode ───────────

    @staticmethod
    def _render_chain_card(spec: dict) -> str:
        """chain-card shortcode. 기존 build_card_html 과 동일 구조."""
        return (
            f'{{{{< chain-card '
            f'title="{spec["title"]}" '
            f'url="{spec["url"]}" '
            f'cta="{spec["cta"]}" >}}}}'
        )

    # ── official: {{< chain-official-card >}} shortcode ───────

    @staticmethod
    def _render_official_card(spec: dict) -> str:
        """chain-official-card shortcode. 기존 build_official_card_html 과 동일 구조."""
        return (
            f'{{{{< chain-official-card '
            f'title="{spec["title"]}" '
            f'url="{spec["url"]}" '
            f'label="{spec["label"]}" >}}}}'
        )

    # ── external: raw HTML 복합 (primary/secondary/fallback) ──

    def _render_external_card(self, spec: dict) -> str:
        """외부 링크 카드 복합 렌더링. 기존 build_external_link_card 와 동일 구조.

        분기 규칙 (기존 구현과 동일):
          1. primary 가 있으면 primary 블록
          2. secondary 가 있으면 secondary 블록 (스펙 생성 시 2개로 슬라이싱됨)
          3. 둘 다 없으면 fallback 블록
        각 블록은 "\\n\\n" 로 결합된다.
        """
        parts: list[str] = []

        primary = spec.get("primary")
        if primary:
            parts.append(self._render_external_primary(primary))

        secondary = spec.get("secondary") or []
        if secondary:
            parts.append(self._render_external_secondary(secondary))

        if not parts:
            fallback = spec.get("fallback")
            if fallback:
                parts.append(self._render_external_fallback(fallback))

        return "\n\n".join(parts)

    @staticmethod
    def _render_external_primary(primary: dict) -> str:
        """1순위 공식 사이트 카드 (적색 배경). 기존 build_external_link_card 와 동일."""
        url = primary["url"]
        label = primary["label"]
        title = primary["title"]
        return (
            f'<div style="margin:1.5em 0;padding:1em;'
            f'border-radius:8px;background:#DC2626;text-align:center">'
            f'<p style="font-size:0.85em;color:rgba(255,255,255,0.85);margin:0 0 0.3em 0">관련 공식 사이트</p>'
            f'<p style="font-size:1.05em;font-weight:bold;color:#fff;margin:0 0 0.5em 0">{label}</p>'
            f'<a href="{url}" target="_blank" rel="noopener" '
            f'style="display:inline-block;padding:0.5em 1.5em;background:rgba(255,255,255,0.2);color:#fff;'
            f'border-radius:4px;text-decoration:none;font-weight:600;font-size:0.9em">'
            f'{title} 바로가기 →</a>'
            f'</div>'
        )

    @staticmethod
    def _render_external_secondary(secondary: list[dict]) -> str:
        """2순위 플랫폼 링크 카드 (파란 배경 링크들). 기존과 동일."""
        links_html = []
        for s in secondary:
            links_html.append(
                f'<a href="{s["url"]}" target="_blank" rel="noopener" '
                f'style="display:inline-block;margin:0.2em;padding:0.4em 1em;'
                f'background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0.85em">'
                f'{s.get("label", "더 보기")} →</a>'
            )
        return (
            f'<div style="margin:1em 0;text-align:center">'
            + " ".join(links_html)
            + "</div>"
        )

    @staticmethod
    def _render_external_fallback(fallback: dict) -> str:
        """fallback 카드 (회색 배경). 기존 build_external_link_card 와 동일."""
        url = fallback["url"]
        label = fallback["label"]
        return (
            f'<div style="margin:1.5em 0;padding:1em;border:1px solid #e5e7eb;'
            f'border-radius:8px;background:#fafafa;text-align:center">'
            f'<p style="font-size:0.85em;color:#666;margin:0 0 0.3em 0">더 많은 정보</p>'
            f'<a href="{url}" target="_blank" rel="noopener" '
            f'style="display:inline-block;padding:0.5em 1.5em;background:#333;color:#fff;'
            f'border-radius:4px;text-decoration:none;font-size:0.9em">'
            f'{label} →</a>'
            f'</div>'
        )
