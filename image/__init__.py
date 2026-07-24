"""
image 패키지 — 체인 포스트용 이미지 생성

Unsplash/Pexels 실사 사진 기반.
- 콘텐츠 이미지 (본문용, 텍스트 오버레이 없음)
- 썸네일 (og:image용, 텍스트 오버레이 있음)

Pollinations.ai / Krea AI는 사용하지 않음.
"""

from .thumbnail import generate_thumbnail, add_text_overlay
from .thumbnail import generate_content_image as generate_image
from .prompt_builder import build_full_prompt, build_contextual_prompt, get_image_style_for_blog, get_aspect_ratio
from .injector import inject_images_into_draft
