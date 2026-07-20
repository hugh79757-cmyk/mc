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
  """slug에 해당하는 첫 번째 이미지 파일을 여러 경로에서 찾음."""
  base = Path("output/images")
  if not base.exists():
    return None
  search_patterns = [
    f"thumb_{slug}.webp",         # Phase 7: thumbnail.py (WebP)
    f"{slug}_*.webp",             # pollinations_client.py (WebP)
    f"content_{slug}.webp",       # Phase 7+ content image
    f"chart_{slug}.webp",         # Phase 8: pillow_chart (WebP)
    f"thumb_{slug}.jpg",          # 하위호환: 기존 .jpg
    f"{slug}_*.jpg",              # 하위호환: 기존 .jpg
    f"chart_{slug}.jpg",          # 하위호환: 기존 .jpg
  ]
  for pattern in search_patterns:
    candidates = sorted(base.glob(pattern))
    if candidates:
      return candidates[0]
  return None


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

    # 마커 치환 (자동 삽입 분기 제거 — drafter가 마커 삽입 여부를 결정)
    if "<!--todo:image-->" in draft_md:
        injected = draft_md.replace("<!--todo:image-->", figure)
        print(f"  [injector] ✅ 이미지 삽입 (마커 치환): {rel_path}")
        return injected

    # Phase 8: <!--todo:chart--> 마커 치환
    if "<!--todo:chart-->" in draft_md:
        injected = draft_md.replace("<!--todo:chart-->", figure)
        print(f"  [injector] ✅ 차트 삽입 (마커 치환): {rel_path}")
        return injected

    # 마커 없으면 패스 (image_type=none인 경우 정상)
    print(f"  [injector] ⏭️ 마커 없음, 삽입 건너뜀")
    return draft_md


# ── CLI test ──
if __name__ == "__main__":
    sample = (
        "# 제목\n\n"
        "<!--todo:image-->\n\n"
        "## 소개\n\n본문 내용"
    )
    result = inject_images_into_draft(sample, "test", "rotcha", 1, "테스트")
    print(result)
