"""
prompt_builder.py — 블로그별 이미지 프롬프트 조립

Image Keywords: 각 chain_post의 image_keyword를 기반으로
블로그 시각 스타일 + 채널 성격에 맞는 영문 Pollinations 프롬프트 생성.
"""

import yaml

from mc_paths import CHAIN_CONFIG_PATH

POLLINATIONS_STYLE_MAP = {
    "rotcha": "k-pop inspired, vibrant colors, cute and energetic, Korean webtoon style, soft lighting",
    "informationhot": "clean infographic style, modern flat design, isometric, pastel palette, professional",
    "techpawz": "tech devices and gadgets, futuristic retro-wave, neon accents, dark mode aesthetic, 3D render",
}

POLLINATIONS_ASPECT_RATIOS = {
    "rotcha": (1024, 1024),      # 1:1
    "informationhot": (1024, 1024),  # 1:1
    "techpawz": (1024, 1024),    # 1:1
}

POLLINATIONS_NEGATIVE = (
    "text, watermark, signature, logo, text on image, blurry, low quality, distorted face, "
    "nsfw, explicit, violent, scary, ugly, deformed"
)


def get_image_style_for_blog(blog_key: str) -> str:
    """Blog key에 대응하는 Pollinations 스타일 프롬프트."""
    return POLLINATIONS_STYLE_MAP.get(blog_key, "high quality, detailed, professional")


def get_aspect_ratio(blog_key: str) -> tuple[int, int]:
    """Blog key에 대응하는 이미지 해상도."""
    return POLLINATIONS_ASPECT_RATIOS.get(blog_key, (1200, 675))


def _load_blog_config() -> dict:
    with open(CHAIN_CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("sites", {})


def build_contextual_prompt(
    image_keyword: str,
    title: str,
    blog_key: str,
    post_angle: str = "",
    seed_keyword: str = "",
    step: int = 1,
    chain_type: str = "depth",
) -> str:
    """
    Build a contextual Pollinations prompt using title + angle.
    Replaces the generic '主題: {image_keyword}' prefix with article context.

    Args:
        image_keyword: Short keyword for image identity.
        title: Article title for contextualization.
        blog_key: Blog identifier (rotcha/informationhot/techpawz).
        post_angle: Article angle/perspective.
        seed_keyword: Original seed keyword.
        step: Chain step number.
        chain_type: Chain direction type.

    Returns:
        Full English prompt string for Pollinations.
    """
    style = get_image_style_for_blog(blog_key)
    sites = _load_blog_config()
    site_cfg = sites.get(blog_key, {})
    extra_prompt = site_cfg.get("prompt", "")

    # Contextual subject line (replaces bare '主題: {keyword}')
    subject_line = f"Article about '{title}' focusing on {image_keyword}"
    if post_angle:
        subject_line += f" from the perspective of {post_angle}"

    parts = [
        subject_line,
        style,
        extra_prompt,
        f"step {step} of {chain_type} chain blog series, Korean cultural context",
        "masterpiece, best quality, 8k, trending on ArtStation",
        f"negative: {POLLINATIONS_NEGATIVE}",
    ]

    return ". ".join(p for p in parts if p)


def build_full_prompt(
    image_keyword: str,
    blog_key: str,
    chain_type: str = "depth",
    step: int = 1,
) -> str:
    """
    image_keyword + blog_key → 완전한 영문 프롬프트.
    """
    style = get_image_style_for_blog(blog_key)

    # 블로그별 추가 프롬프트 규칙 (chain_config.yaml)
    sites = _load_blog_config()
    site_cfg = sites.get(blog_key, {})
    extra_prompt = site_cfg.get("prompt", "")

    parts = [
        f"主題: {image_keyword}",
        style,
        extra_prompt,
        f"step {step} of {chain_type} chain blog series, Korean cultural context",
        "masterpiece, best quality, 8k, trending on ArtStation",
        f"negative: {POLLINATIONS_NEGATIVE}",
    ]

    return ". ".join(p for p in parts if p)


# ── CLI test ──
if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "춘천 여행"
    blog = sys.argv[2] if len(sys.argv) > 2 else "rotcha"
    prompt = build_full_prompt(kw, blog)
    print(prompt)
