"""
prompt_builder.py — 블로그별 이미지 프롬프트 조립

Pollinations 프롬프트 규칙:
  1. 인물 금지 (hard): body parts 포함 (wrist/finger/hands/arm/limb)
  2. 풍경 강제: "LANDSCAPE ONLY" 긍정문을 프롬프트 맨 앞에 배치
  3. 스타일 강제: 주제별 1개 선택 (파스텔/유화/크로키/수채화)
  4. 주제 시각화: 사물도 풍경 배경 안에 배치 (예: "스마트워치 on 도시 야경")

Image Keywords: 각 chain_post의 image_keyword를 기반으로
블로그별 시각 스타일 + 채널 성격에 맞는 영문 Pollinations 프롬프트 생성.
"""

import yaml

from mc_paths import CHAIN_CONFIG_PATH

POLLINATIONS_STYLE_MAP = {
    "rotcha": "soft pastel illustration, gentle color palette, artistic",
    "issue.techpawz": "clean infographic style, modern flat design, isometric, pastel palette, professional",
    "techpawz": "sketch style, pencil drawing, monochrome, hand-drawn, artistic",
}

# 주제별 스타일 (라운드로빈 대신 image_keyword로 매칭)
TOPIC_STYLES = {
    # 풍경 주제
    "landscape": "oil painting style, textured brushstrokes, warm tones",
    "nature": "watercolor painting, soft wash, translucent colors",
    "travel": "watercolor painting, soft wash, translucent colors",
    "hotel": "oil painting style, textured brushstrokes, warm tones",
    "pension": "oil painting style, textured brushstrokes, warm tones",
    "cafe": "soft pastel illustration, gentle color palette, artistic",
    # 추상/사물 주제
    "tech": "sketch style, pencil drawing, monochrome, hand-drawn",
    "ai": "sketch style, pencil drawing, monochrome, hand-drawn",
    "market": "clean infographic style, modern flat design",
    "finance": "clean infographic style, modern flat design",
    "shopping": "soft pastel illustration, gentle color palette, artistic",
    "fashion": "soft pastel illustration, gentle color palette, artistic",
    "game": "sketch style, pencil drawing, monochrome, hand-drawn",
    "food": "watercolor painting, soft wash, translucent colors",
}

# 인물 금지 키워드 (항상 포함) — body parts까지 명시
NO_PEOPLE_BLOCK = (
    "no people, no humans, no characters, no faces, no portraits, "
    "no figures, no hands, no eyes, no person, no crowd, no portrait, "
    "no wrist, no finger, no arm, no limb, no body part"
)

# Pollinations 프롬프트 맨 앞에 배치하는 강제 문장 (긍정 명령)
FORCED_LANDSCAPE_PREAMBLE = (
    "NO PEOPLE. NO HANDS. NO BODY PARTS. LANDSCAPE OR SCENERY ONLY."
)

POLLINATIONS_ASPECT_RATIOS = {
    "rotcha": (1024, 1024),      # 1:1
    "issue.techpawz": (1024, 1024),  # 1:1
    "techpawz": (1024, 1024),    # 1:1
}

POLLINATIONS_NEGATIVE = (
    "text, watermark, signature, logo, text on image, blurry, low quality, distorted face, "
    "nsfw, explicit, violent, scary, ugly, deformed, "
    "people, person, woman, man, character, human, portrait, face, crowd, figure"
)


def _infer_topic_type(image_keyword: str) -> str:
    """image_keyword에서 주제 유형 추론 (풍경/추상/사물)."""
    kw_lower = image_keyword.lower()
    landscape_words = [
        "valley", "mountain", "river", "sea", "ocean", "beach", "forest",
        "pension", "hotel", "resort", "cafe", "restaurant", "village",
        "city", "building", "architecture", "garden", "park",
        "paju", "pocheon", "ucheon", "haeundae", "ukjido",
        "travel", "trip", "tour", "healing", "relaxation",
    ]
    abstract_words = [
        "ai", "market", "tech", "data", "algorithm", "digital",
        "future", "trend", "analysis", "strategy", "platform",
        "prompt", "code", "test", "software", "system",
        "finance", "investment", "crypto", "blockchain",
    ]
    for w in landscape_words:
        if w in kw_lower:
            return "landscape"
    for w in abstract_words:
        if w in kw_lower:
            return "abstract"
    return "object"


def _select_style(image_keyword: str, blog_key: str) -> str:
    """image_keyword + blog_key로 스타일 선택."""
    topic_type = _infer_topic_type(image_keyword)
    # 1순위: 주제별 스타일 매칭
    for key, style in TOPIC_STYLES.items():
        if key in image_keyword.lower():
            return style
    # 2순위: 블로그 기본 스타일
    return POLLINATIONS_STYLE_MAP.get(blog_key, "high quality, detailed, professional")


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

    Pollinations 프롬프트 규칙:
      1. LANDSCAPE ONLY 긍정문을 맨 앞에 배치
      2. 인물 금지 (body parts 포함)
      3. 스타일 강제 (주제별 매칭)

    Args:
        image_keyword: Short keyword for image identity.
        title: Article title for contextualization.
        blog_key: Blog identifier (rotcha/issue.techpawz/techpawz).
        post_angle: Article angle/perspective.
        seed_keyword: Original seed keyword.
        step: Chain step number.
        chain_type: Chain direction type.

    Returns:
        Full English prompt string for Pollinations.
    """
    style = _select_style(image_keyword, blog_key)
    sites = _load_blog_config()
    site_cfg = sites.get(blog_key, {})
    extra_prompt = site_cfg.get("prompt", "")

    # 주제 시각화: image_keyword를 기반으로 구체적 장면 묘사
    topic_type = _infer_topic_type(image_keyword)
    if topic_type == "landscape":
        scene = f"scenic landscape featuring {image_keyword}, natural beauty, peaceful atmosphere"
    elif topic_type == "abstract":
        scene = f"abstract concept art of {image_keyword}, geometric shapes, symbolic representation, serene background"
    else:
        scene = f"scenic landscape background with {image_keyword}, still life object in natural setting, outdoor environment, peaceful scenery"

    parts = [
        FORCED_LANDSCAPE_PREAMBLE,
        scene,
        style,
        extra_prompt,
        NO_PEOPLE_BLOCK,
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
    LANDSCAPE ONLY + 인물금지 + 스타일강제 + 풍경배경.
    """
    style = _select_style(image_keyword, blog_key)

    sites = _load_blog_config()
    site_cfg = sites.get(blog_key, {})
    extra_prompt = site_cfg.get("prompt", "")

    topic_type = _infer_topic_type(image_keyword)
    if topic_type == "landscape":
        scene = f"scenic landscape featuring {image_keyword}"
    elif topic_type == "abstract":
        scene = f"abstract concept art of {image_keyword}, serene background"
    else:
        scene = f"scenic landscape background with {image_keyword}, outdoor natural setting"

    parts = [
        FORCED_LANDSCAPE_PREAMBLE,
        scene,
        style,
        extra_prompt,
        NO_PEOPLE_BLOCK,
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
