"""MarkdownProcessor — 발행 전 마크다운 1차 정제 파이프라인 단일 진실 공급원.

Phase 26 W4 (03-04) 에 신설. 기존에 각 모듈에 분산되어 있던 정제 로직의
공통 실행 경로를 하나의 클래스로 제공한다:

- 펜스 자동 수정      : ``chain_card_injector.CardInjector.fix_unclosed_fences`` 위임
- 릭 방어            : ``mc.leak_defense.strip_leaks`` 위임 (패턴 단일 진실 공급원은
  ``constants.LEAK_PATTERNS`` / ``constants.LEAK_REGEX`` — mc/leak_defense.py 문서 참조)
- 연도 검증          : ``mc.year_guard.validate_and_fix_years`` 위임 (Phase 32)
- 심볼 클리닝        : ``chain_publisher_core._clean_markdown_symbols`` 와 동일 알고리즘
- 표 자동 보정        : ``fix_tables`` — header 다음 separator 누락 시 삽입,
  header 단독 잘린 빈 표는 제거 (quick 20260801, Hugo goldmark ``<table>`` 렌더링 보장)

모든 정제는 **기존 함수/모듈을 수정하지 않고** (additive) 이 클래스로 위임한다.
기존 호출부는 그대로 동작하며, ``process()`` 는 위 5단계를
fix_fences → strip_leaks → year_guard → clean_symbols 순서로 적용한 결과를 반환한다.
(``clean_symbols`` 진입 시 ``fix_tables`` 전처리가 먼저 적용된다.)
"""

import re
from typing import List

from mc.leak_defense import strip_leaks as _strip_leaks  # noqa: F401 — 릭 방어 위임 (단일 진실 공급원)
from mc.year_guard import validate_and_fix_years as _validate_and_fix_years  # noqa: F401 — 연도 검증 위임 (Phase 32)


class MarkdownProcessor:
    """마크다운 정제 파이프라인. 스레드 안전한 인스턴스 1개 공유 권장."""

    # ── 단계 0: 깨진/잘린 마크다운 표 자동 보정 ─────────────────────────
    _TABLE_ROW_RE = re.compile(r'^\s*\|')
    _TABLE_SEP_RE = re.compile(r'^\s*\|[\s\-:|]+\|\s*$')
    _BARE_PIPE_RE = re.compile(r'^\s*\|\s*$')

    def fix_tables(self, body: str) -> str:
        """깨진/잘린 마크다운 표 자동 보정 (재발 방지, quick 20260801).

        AI 초안이 표 header 행 다음에 separator 행(``| --- | --- |``)을
        누락하면 Hugo goldmark 는 ``<table>`` 이 아닌 ``<p>`` 로 렌더링한다.
        본 메서드는 발행 전에 다음 두 패턴을 보정한다:

        1. header 다음에 데이터 행이 바로 오는 경우 → separator 행 삽입
           (예: ``| A | B |`` 바로 아래 ``| 1 | 2 |`` → 사이에 ``| --- | --- |``)
        2. header 다음에 빈 파이프(``|``)만 오는 잘린 빈 표 → 해당 표 제거
           (데이터가 생성되지 않은 header 단독 표는 렌더링 시 깨지므로 제거)

        표는 "연속된 | 행들의 run" 단위로 판정한다. run 의 두 번째 줄이
        separator 가 아니면 깨진 표로 보고 header 다음에 separator 를
        한 번만 삽입한다 (모든 데이터 행 뒤에 삽입하지 않음).

        코드 펜스(```) 내부는 보호되어 수정되지 않는다. 기존 정제 로직과
        독립적인 전처리 단계로, ``clean_symbols`` 진입 시 자동 적용된다.
        """
        lines = body.split('\n')
        result: List[str] = []
        in_code_block = False
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            stripped = line.strip()

            # PROTECTED: code blocks
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                result.append(line)
                i += 1
                continue
            if in_code_block:
                result.append(line)
                i += 1
                continue

            # non-table line — keep as-is
            if not self._TABLE_ROW_RE.match(stripped):
                result.append(line)
                i += 1
                continue

            # gather the whole run of consecutive table-ish lines
            run = []
            j = i
            while j < n:
                s = lines[j].strip()
                if s.startswith('```') or not self._TABLE_ROW_RE.match(s):
                    break
                run.append((j, lines[j]))
                j += 1

            if len(run) == 0:
                result.append(line)
                i += 1
                continue

            if len(run) == 1:
                single_cls = self._classify_table_line(run[0][1].strip())
                if single_cls == 'bare':
                    # stray bare pipe — drop it (렌더링 깨짐 유발)
                    i = j
                    continue
                # single table line: keep as-is (can't determine intent)
                result.append(run[0][1])
                i = j
                continue

            second_cls = self._classify_table_line(run[1][1].strip())
            first_cls = self._classify_table_line(run[0][1].strip())

            if second_cls == 'sep':
                # valid table (header + separator [+ data rows]) — keep run as-is
                for _idx, _l in run:
                    result.append(_l)
                i = j
                continue

            if first_cls == 'row' and second_cls == 'bare':
                # truncated empty table: header + bare pipe → drop the run
                i = j
                continue

            if first_cls == 'row' and second_cls == 'row':
                # header followed by data row WITHOUT separator → insert separator
                result.append(run[0][1])
                cells = max(run[0][1].strip().count('|') - 1, 1)
                result.append('| ' + ' | '.join(['---'] * cells) + ' |')
                for _idx, _l in run[1:]:
                    result.append(_l)
                i = j
                continue

            # unknown pattern — keep run as-is
            for _idx, _l in run:
                result.append(_l)
            i = j

        return '\n'.join(result)

    @staticmethod
    def _classify_table_line(stripped: str) -> str:
        """표 관련 라인 분류: 'sep' | 'bare' | 'row' | None."""
        if MarkdownProcessor._TABLE_SEP_RE.match(stripped):
            return 'sep'
        if MarkdownProcessor._BARE_PIPE_RE.match(stripped):
            return 'bare'
        if MarkdownProcessor._TABLE_ROW_RE.match(stripped):
            return 'row'
        return None

    # ── 단계 1: 미닫힌 코드 펜스 자동 수정 ──────────────────────────────
    def fix_fences(self, text: str) -> str:
        """``chain_card_injector.CardInjector.fix_unclosed_fences`` 에 위임.

        chain_card_injector 가 무거운 모듈(link_finder/card_generator 등)을
        import 하므로 첫 호출 시점에 lazy import 한다.
        """
        from chain_card_injector import CardInjector  # lazy — 순환/부팅 비용 회피

        return CardInjector.fix_unclosed_fences(text)

    # ── 단계 2: 프롬프트/CTA 릭 방어 ────────────────────────────────────
    def strip_leaks(self, text: str, context: str = "draft") -> str:
        """``mc.leak_defense.strip_leaks`` 에 위임, 클린 텍스트만 반환.

        리턴 튜플 (cleaned, stats) 중 cleaned 만 반환한다. 통계가 필요하면
        ``mc.leak_defense.strip_leaks`` 를 직접 호출한다.
        """
        cleaned, _stats = _strip_leaks(text, context=context)
        return cleaned

    # ── 단계 3: 마크다운 심볼 클리닝 ────────────────────────────────────
    def clean_symbols(self, body: str) -> str:
        """chain_publisher_core._clean_markdown_symbols 와 동일 알고리즘.

        PROTECTED — never modified:
        - <!--todo:image--> / <!--todo:chart--> markers
        - Code blocks (``` fences)
        - Inline code (backtick)
        - Table separator lines (---|---|--- or |---|---|)
        - Table data lines (lines starting with |)
        - Math blocks ($$) and inline math ($)

        Rules:
        1. Escape loose pipes (|) outside protected contexts — replace with \\|.
        2. CJK 볼드/이탤릭 간격 보정은 AI 프롬프트가 강제하므로 수행하지 않음.
        3. Remove orphaned markdown delimiters (unmatched ** pairs).

        전처리: ``fix_tables`` 를 먼저 적용해 깨진/잘린 표를 보정한다.
        """
        body = self.fix_tables(body)
        lines = body.split('\n')
        result: List[str] = []
        in_code_block = False
        in_math_block = False

        for line in lines:
            stripped = line.strip()

            # PROTECTED: code blocks
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                result.append(line)
                continue
            if in_code_block:
                result.append(line)
                continue

            # PROTECTED: math blocks
            if stripped.startswith('$$'):
                in_math_block = not in_math_block
                result.append(line)
                continue
            if in_math_block:
                result.append(line)
                continue

            # PROTECTED: image/comment markers
            if '<!--todo:' in stripped:
                result.append(line)
                continue

            # PROTECTED: table separator lines (---|---|--- or |---|---|)
            # Must check BEFORE pipe-escape rule since these may lack leading |
            if re.match(r'^[-|:\s]+$', stripped) and ('|' in stripped) and ('-' in stripped):
                result.append(line)
                continue

            # PROTECTED: table data rows (starts with |)
            if stripped.startswith('|'):
                result.append(line)
                continue

            # PROTECTED: inline math ($...$)
            stripped_no_math = re.sub(r'\$[^\$]+\$', '', stripped)
            if not stripped_no_math.strip():
                result.append(line)
                continue

            # Rule 1: Escape loose pipes in non-table context
            line = line.replace('|', '\\|')

            # Rule 2: NO CJK bold/italic spacing — AI prompt already enforces
            # '볼드체 앞뒤에 반드시 공백' and CommonMark requires no spaces
            # inside ** or * delimiters. Adding spaces inside breaks rendering.
            pass

            # Rule 3: Handle unmatched bold/italic delimiters
            bold_count = line.count('**')
            if bold_count % 2 != 0:
                last_idx = line.rfind('**')
                if last_idx >= 0:
                    line = line[:last_idx] + line[last_idx + 2:]

            result.append(line)

        return '\n'.join(result)

    # ── 파이프라인: fix_fences → strip_leaks → year_guard → clean_symbols ──
    def process(self, markdown_text: str, leak_context: str = "draft") -> str:
        """발행 전 1차 정제 파이프라인 전체 실행.

        Args:
            markdown_text: 정제할 마크다운 본문 (frontmatter 는 이미 분리된 상태 권장).
            leak_context: strip_leaks 의 context ("draft" 기본).

        Returns:
            펜스 수정 + 릭 제거 + 연도 검증 + 심볼 클리닝이 적용된 텍스트.
            (clean_symbols 내부에서 fix_tables 표 보정이 먼저 적용됨)
        """
        text = self.fix_fences(markdown_text)
        text = self.strip_leaks(text, context=leak_context)
        # Phase 32: 연도 검증 — 과거연도+최신 조합 자동 치환
        text, _year_warnings = _validate_and_fix_years(text, fix_mode=True)
        return self.clean_symbols(text)


# 모듈 공유 인스턴스 — 호출부에서 매번 생성하지 않고 재사용
processor = MarkdownProcessor()
