"""Title–body consistency checker for mc blog posts.

Extracts key noun-phrase promises from a title, then verifies that each
promise is backed by a concrete section in the markdown body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Korean particles/conjunctions to strip when extracting promise topics
_STRIP_PARTICLES = re.compile(
    r"(을|를|이|가|은|는|의|에|에서|로|으로|와|과|하고)\b"
)

# Delimiters that separate promise topics in a title
_DELIMITERS = re.compile(r"\s*(?:및|과|,|\+)\s*")


@dataclass
class TitleBodyResult:
    """Result of title–body consistency validation."""

    score: float = 1.0
    met_promises: list[str] = field(default_factory=list)
    unmet_promises: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1. Title promise extraction
# ---------------------------------------------------------------------------

def extract_title_promises(title: str) -> list[str]:
    """Extract key noun-phrase topics from a title.

    Steps:
      1. Split on delimiters (및, 과, ',', '+').
      2. Strip Korean particles from each fragment.
      3. Collapse whitespace and drop empty strings.
    """
    raw_parts = _DELIMITERS.split(title)
    promises: list[str] = []
    for part in raw_parts:
        cleaned = _STRIP_PARTICLES.sub("", part).strip()
        if cleaned:
            promises.append(cleaned)
    return promises


# ---------------------------------------------------------------------------
# 2. Section coverage check
# ---------------------------------------------------------------------------

_H2_RE = re.compile(r"^## (.+)$", re.MULTILINE)
_H3_RE = re.compile(r"^### (.+)$", re.MULTILINE)
_DIGIT_RE = re.compile(r"\d")
_HANGUL_PROPER = re.compile(
    r"[가-힣]{2,}(?:\s[가-힣]+)*"  # 2+ char Korean words (potential named entities)
)
_ADDRESS_RE = re.compile(
    r"(?:시|군|구|동|읍|면|리|로|길|번지|\d{1,5}-\d{1,5})"
)


def _has_concrete_info(text: str) -> bool:
    """Return True if *text* contains at least one concrete-info signal."""
    if _DIGIT_RE.search(text):
        return True
    if _ADDRESS_RE.search(text):
        return True
    # At least 3 consecutive Korean characters (likely a named entity)
    if _HANGUL_PROPER.search(text):
        return True
    return False


def _split_sections(body_md: str) -> list[tuple[str, str]]:
    """Split markdown body into (heading, content) tuples for H2/H3.

    Heading-only lines (no body below) get an empty string as content.
    Text before the first heading is tagged with an empty heading.
    """
    lines = body_md.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    current_lines: list[str] = []

    heading_re = re.compile(r"^(#{2,3})\s+(.+)$")

    for line in lines:
        m = heading_re.match(line)
        if m:
            # flush previous section
            sections.append((current_heading, current_lines))
            current_heading = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # flush last section
    sections.append((current_heading, current_lines))

    return [(h, "\n".join(lines)) for h, lines in sections]


def check_section_coverage(
    body_md: str,
    promises: list[str],
) -> dict:
    """Check whether each promise topic has a covering section with concrete info.

    Returns a dict with keys:
      - met: list of (promise, heading) tuples
      - unmet: list of (promise, reason) tuples
    """
    sections = _split_sections(body_md)

    met: list[tuple[str, str]] = []
    unmet: list[tuple[str, str]] = []

    for promise in promises:
        promise_lower = promise.lower()
        found = False
        for heading, content in sections:
            heading_lower = heading.lower().strip()
            if not heading_lower:
                continue  # skip pre-heading / empty sections
            # Also strip particles from heading for comparison
            heading_stripped = _STRIP_PARTICLES.sub("", heading_lower).strip()
            # Check if heading covers the promise topic
            if (
                promise_lower in heading_lower
                or heading_lower in promise_lower
                or promise_lower in heading_stripped
                or heading_stripped in promise_lower
            ):
                # Check concrete info in this section
                if _has_concrete_info(content):
                    met.append((promise, heading))
                    found = True
                    break
                else:
                    # Heading matches but content is generic
                    unmet.append(
                        (promise, f"section '{heading}' has no concrete info")
                    )
                    found = True
                    break
        if not found:
            unmet.append((promise, "no matching section"))

    return {"met": met, "unmet": unmet}


# ---------------------------------------------------------------------------
# 3. Validate title-body consistency
# ---------------------------------------------------------------------------

def validate_title_body(title: str, body_md: str) -> TitleBodyResult:
    """Full title–body consistency validation.

    Returns TitleBodyResult with score, met/unmet promises, and details.
    """
    promises = extract_title_promises(title)

    if not promises:
        return TitleBodyResult(
            score=1.0,
            met_promises=[],
            unmet_promises=[],
            details={"reason": "no promises extracted from title"},
        )

    coverage = check_section_coverage(body_md, promises)

    met = [p for p, _ in coverage["met"]]
    unmet = [p for p, _ in coverage["unmet"]]

    # Score: 1.0 if all met, decreasing linearly
    if len(promises) == 0:
        score = 1.0
    else:
        score = len(met) / len(promises)

    details = {
        "total_promises": len(promises),
        "coverage": [
            {"promise": p, "status": "met", "heading": h}
            for p, h in coverage["met"]
        ]
        + [
            {"promise": p, "status": "unmet", "reason": r}
            for p, r in coverage["unmet"]
        ],
    }

    return TitleBodyResult(
        score=score,
        met_promises=met,
        unmet_promises=unmet,
        details=details,
    )
