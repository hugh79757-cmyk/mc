"""year_guard — 연도 오류 방지 유틸리티 모듈 (Phase 32).

3겹 방어의 공통 유틸. 소스 데이터 보정(1차), LLM 프롬프트(2차), 출력단
사후 검증(3차) 모두 이 모듈의 validate_and_fix_years()를 사용한다.

핵심 원칙:
- 사실 날짜(축제 개최일, 이벤트 기간 등)는 절대 변경하지 않음
- 과거 연도 + '최신/기준/현재' 조합만 현재 연도로 자동 치환
- standalone 과거 연도는 플래그만 반환 (치환 안 함)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional


# ── 정규식 패턴 ──────────────────────────────────────────────────────

# 패턴 1: 과거 연도 + '최신/기준/현재' → 현재 연도로 치환
# 예: "2025 최신 정보" → "2026 최신 정보", "2024년 기준" → "2026년 기준"
PATTERN_YEAR_WITH_CONTEXT = re.compile(
    r'(20\d{2})년?\s*(최신|기준|현재)'
)

# 패턴 2: '최신/기준/현재' + 과거 연도 → 현재 연도로 치환
# 예: "최신 2025년 정보" → "최신 2026년 정보"
PATTERN_CONTEXT_WITH_YEAR = re.compile(
    r'(최신|기준|현재)\s*(20\d{2})년?'
)

# 패턴 3: standalone 과거 연도 (최신/기준/현재 없음) → 플래그만 (치환 안 함)
# 예: "2025년 축제" → 사실 정보이므로 보호
PATTERN_STANDALONE_YEAR = re.compile(r'(20\d{2})\s*년?')


# ── 사실 날짜 보호 패턴 ──────────────────────────────────────────────

# 이벤트/기간 키워드 — standalone 매칭에서 사실 날짜 여부 판정용
FACTUAL_KEYWORDS = (
    '축제|개최|행사|기간|일정|운영|개장|폐장'  # 이벤트
    '|부터|까지|이후|전까지|중'                   # 기간 표현
)

# 전체 패턴 — 매칭 주변에서 사실 날짜 여부 판정용 (년 포함)
FACTUAL_DATE_PATTERNS = [
    r'20\d{2}년?\s*(축제|개최|행사|기간|일정|운영|개장|폐장)',   # 이벤트 날짜
    r'20\d{2}년?\s*(부터|까지|이후|전까지|중)',                   # 기간 표현
    r'20\d{2}년?\s*\d{1,2}월',                                   # 구체적 월
    r'20\d{2}년?\s*\d{1,2}월\s*\d{1,2}일',                      # 구체적 일
]


def _is_factual_date(text: str, match_start: int, match_end: int) -> bool:
    """매칭된 연도가 사실 날짜 컨텍스트에 있는지 확인.

    매칭 뒤쪽 컨텍스트(±15자)에서 사실 날짜 패턴이 매칭되면 True.
    앞쪽 컨텍스트는 확인하지 않는다 — 다른 문장의 사실 날짜에 의해
    오검출되는 것을 방지한다.
    """
    ctx_end = min(len(text), match_end + 15)
    context = text[match_end:ctx_end]

    for pattern in FACTUAL_DATE_PATTERNS:
        if re.search(pattern, context):
            return True
    return False


def _is_factual_standalone(text: str, match_start: int, match_end: int) -> bool:
    """standalone 매칭에서 뒤쪽이 사실 날짜 키워드로 이어지는지 확인.

    standalone 패턴("2025년") 매칭 후 뒤쪽에 축제/기간 등 키워드가
    오면 사실 날짜로 보호한다.
    """
    ctx_end = min(len(text), match_end + 15)
    context = text[match_end:ctx_end]

    if re.search(FACTUAL_KEYWORDS, context):
        return True
    return False


def build_allowed_years(source_years: Optional[set[int]] = None) -> set[int]:
    """허용 연도 목록 생성.

    Args:
        source_years: 소스 데이터에서 추출한 연도 목록 (TourAPI/DB 등).
                      None이면 빈 세트.

    Returns:
        {현재 연도} ∪ source_years
    """
    current = datetime.now().year
    allowed = {current}
    if source_years:
        allowed.update(source_years)
    return allowed


def validate_and_fix_years(
    text: str,
    allowed_years: Optional[set[int]] = None,
    current_year: Optional[int] = None,
    fix_mode: bool = True,
) -> tuple[str, list[str]]:
    """텍스트에서 연도를 검증하고 필요 시 치환.

    Args:
        text: 검증할 마크다운 텍스트
        allowed_years: 허용 연도 목록. None이면 {현재 연도}만 허용
        current_year: 기준 연도. None이면 datetime.now().year
        fix_mode: True면 '과거연도+최신/기준/현재' 패턴을 현재 연도로
                  자동 치환. False면 플래그만 반환 (치환 없음).

    Returns:
        (처리된 텍스트, 경고 메시지 리스트)
    """
    if current_year is None:
        current_year = datetime.now().year

    if allowed_years is None:
        allowed_years = {current_year}

    warnings: list[str] = []
    result = text

    # ── 1차: 패턴 1 — "2025 최신" / "2024년 기준" / "2023 현재" ──────
    # 매칭을 먼저 모두 수집한 후 역순으로 치환 (인덱스 보존)
    matches1 = list(PATTERN_YEAR_WITH_CONTEXT.finditer(result))
    for m in reversed(matches1):
        year = int(m.group(1))
        context_word = m.group(2)
        if _is_factual_date(result, m.start(), m.end()):
            continue
        if year != current_year:
            if fix_mode:
                full_match = m.group(0)
                replaced = full_match.replace(str(year), str(current_year), 1)
                result = result[:m.start()] + replaced + result[m.end():]
                warnings.append(f"치환: {year} {context_word} → {current_year} {context_word}")
            else:
                warnings.append(f"경고: {year} {context_word} — 과거 연도+최신 조합")

    # ── 2차: 패턴 2 — "최신 2025년" / "기준 2024년" ──────────────────
    matches2 = list(PATTERN_CONTEXT_WITH_YEAR.finditer(result))
    for m in reversed(matches2):
        year = int(m.group(2))
        context_word = m.group(1)
        if _is_factual_date(result, m.start(), m.end()):
            continue
        if year != current_year:
            if fix_mode:
                full_match = m.group(0)
                replaced = full_match.replace(str(year), str(current_year), 1)
                result = result[:m.start()] + replaced + result[m.end():]
                warnings.append(f"치환: {context_word} {year}년 → {context_word} {current_year}년")
            else:
                warnings.append(f"경고: {context_word} {year}년 — 과거 연도+최신 조합")

    # ── 3차: 패턴 3 — standalone 과거 연도 (플래그만) ────────────────
    for m in PATTERN_STANDALONE_YEAR.finditer(result):
        year = int(m.group(1))
        if year != current_year and year not in allowed_years:
            if _is_factual_standalone(result, m.start(), m.end()):
                continue
            warnings.append(f"주의: {year}년 — 허용 목록에 없는 과거 연도 (standalone)")

    return result, warnings
