"""
injector.py — 생성된 이미지를 draft 마크다운에 삽입

Hugo shortcode {{< figure >}} 사용.
각 step별 cover image + 본문 중간에 적절한 위치에 삽입.
운영자가 편집 가능하도록 <!-- todo:image --> 포인터도 제공.
"""

import re
from pathlib import Path

from .pollinations_client import IMAGE_DIR


def _find_image_file(slug: str) -> Path | None:
    """slug에 해당하는 첫 번째 이미지 파일을 IMAGE_DIR에서 찾음."""
    if not IMAGE_DIR.exists():
        return None
    candidates = sorted(IMAGE_DIR.glob(f"{slug}_*.jpg"))
    return candidates[0] if candidates else None


def _hugo_figure(src_path: str, alt: str = "", caption: str = "") -> str:
    """
    Hugo figure shortcode 생성.
    src: Hugo 기준 상대 경로 (예: /images/step-1-xxx_1024x1024.jpg)
    """
    lines = [
        "{{< figure",
        f'  src="{src_path}"',
        f'  alt="{alt}"',
        f'  caption="{caption}"',
        ">}}",
    ]
    return "\n".join(lines)


def _image_relative_path(absolute_path: Path) -> str:
    """
    절대 경로 → Hugo static/images/ 기준 상대 경로.
    Pollinations IMAGE_DIR = mc/output/images/
    Hugo static 기준: /images/...
    """
    return f"/images/{absolute_path.name}"


def inject_images_into_draft(
    draft_md: str,
    slug: str,
    blog_key: str,
    step: int,
    title: str,
) -> str:
    """
    draft 마크다운에 이미지 삽입.

    1. 첫 h2 앞에 cover image 삽입 (Hugo figure)
    2. <!--todo:image--> 마커를 실제 figure shortcode로 치환
    3. 마커가 없으면 첫 h2 다음에 삽입

    운영자가 마커를 원하는 위치에 심으면 injector가 자동 치환.
    """
    image_path = _find_image_file(slug)

    if not image_path:
        print(f"  [injector] ⚠️ slug '{slug}' 이미지 없음, <!--todo:image--> 유지")
        return draft_md

    rel_path = _image_relative_path(image_path)
    figure = _hugo_figure(rel_path, alt=title, caption=title)

    # 마커 치환
    if "<!--todo:image-->" in draft_md:
        injected = draft_md.replace("<!--todo:image-->", figure)
        print(f"  [injector] ✅ 이미지 삽입 (마커 치환): {rel_path}")
        return injected

    # 첫 h2 앞에 삽입
    h2_pattern = re.compile(r"^## ", re.MULTILINE)
    h2_match = h2_pattern.search(draft_md)
    if h2_match:
        pos = h2_match.start()
        injected = draft_md[:pos].rstrip() + "\n\n" + figure + "\n\n" + draft_md[pos:]
        print(f"  [injector] ✅ 이미지 삽입 (첫 h2 전): {rel_path}")
        return injected

    # 끝에 추가
    print(f"  [injector] ✅ 이미지 추가 (문서 끝): {rel_path}")
    return draft_md.rstrip() + "\n\n" + figure + "\n"


# ── CLI test ──
if __name__ == "__main__":
    sample = (
        "# 제목\n\n"
        "<!--todo:image-->\n\n"
        "## 소개\n\n본문 내용"
    )
    result = inject_images_into_draft(sample, "test", "rotcha", 1, "테스트")
    print(result)
