"""Tests for image/prompt_builder.py — Pollinations 프롬프트 생성."""

import pytest


class TestPollinationsNegative:
    """POLLINATIONS_NEGATIVE 금지 키워드 테스트."""

    def test_negative_includes_people_keywords(self):
        """금지 키워드에 사람 관련 키워드가 포함되어야 함."""
        from image.prompt_builder import POLLINATIONS_NEGATIVE

        people_keywords = ["people", "person", "woman", "man", "human", "portrait", "face"]
        for kw in people_keywords:
            assert kw in POLLINATIONS_NEGATIVE, f"Missing people keyword: {kw}"

    def test_negative_includes_quality_keywords(self):
        """금지 키워드에 품질 관련 키워드가 포함되어야 함."""
        from image.prompt_builder import POLLINATIONS_NEGATIVE

        quality_keywords = ["blurry", "low quality", "distorted face", "deformed"]
        for kw in quality_keywords:
            assert kw in POLLINATIONS_NEGATIVE, f"Missing quality keyword: {kw}"

    def test_build_contextual_prompt_uses_negative(self):
        """build_contextual_prompt가 금지 키워드를 프롬프트에 포함해야 함."""
        from image.prompt_builder import build_contextual_prompt

        prompt = build_contextual_prompt(
            image_keyword="pension-overview",
            title="포천계곡펜션 추천",
            blog_key="rotcha",
        )
        assert "negative:" in prompt.lower()
        assert "people" in prompt
        assert "person" in prompt

    def test_negative_in_prompt_string(self):
        """금지 키워드 문자열에 'people'이 있어야 합니다."""
        from image.prompt_builder import POLLINATIONS_NEGATIVE

        # Verify the negative prompt contains the new people keywords
        assert "people, person, woman, man" in POLLINATIONS_NEGATIVE
