"""
image 패키지 — 체인 포스트용 이미지 생성

Pollinations.ai flux 모델 기반 무료 이미지 생성.
rate limit: ~1 req / 15초
"""

from .pollinations_client import generate_image, IMAGE_DIR
from .prompt_builder import build_full_prompt, get_image_style_for_blog, get_aspect_ratio
from .injector import inject_images_into_draft
from .thumbnail import generate_thumbnail, add_text_overlay
