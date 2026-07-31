"""
test_leak_defense_constants.py — leak_defense 상수 연동 테스트
(Phase 26, Plan 01-03/01-04)

leak_defense 의 LEAK_PATTERNS / LEAK_REGEX 공개 값이 yaml 기반 동작과
일관되게 유지되는지, 그리고 constants.py 의 re-export 와 동일한지 검증한다.
"""


class TestLeakDefenseConstants:
    def test_imports_work(self):
        # 계획의 `from leak_defense import ...` 는 실제 경로 mc/leak_defense.py 로 해석
        from mc.leak_defense import LEAK_PATTERNS, LEAK_REGEX  # noqa: F401

    def test_leak_patterns_non_empty(self):
        from mc.leak_defense import LEAK_PATTERNS

        assert isinstance(LEAK_PATTERNS, list)
        assert len(LEAK_PATTERNS) > 0

    def test_leak_regex_matches_patterns(self):
        """LEAK_REGEX 는 LEAK_PATTERNS 의 컴파일 버전."""
        from mc.leak_defense import LEAK_PATTERNS, LEAK_REGEX

        assert len(LEAK_REGEX) == len(LEAK_PATTERNS)
        for pat, rx in zip(LEAK_PATTERNS, LEAK_REGEX):
            assert rx.pattern == pat

    def test_constants_reexport_matches(self):
        """Plan verify: LEAK_PATTERNS == CONST_LEAK_PATTERNS."""
        from constants import LEAK_PATTERNS as CONST_LEAK_PATTERNS
        from mc.leak_defense import LEAK_PATTERNS

        assert LEAK_PATTERNS == CONST_LEAK_PATTERNS
        assert LEAK_PATTERNS is CONST_LEAK_PATTERNS

    def test_yaml_driven_behavior_intact(self):
        """reload_config() 이후에도 strip_leaks / LEAK_PATTERNS 가 일관된 동작."""
        from mc.leak_defense import LEAK_PATTERNS, reload_config, strip_leaks

        before = list(LEAK_PATTERNS)
        reload_config()
        after = list(LEAK_PATTERNS)
        assert before == after  # yaml 변경 없으면 동일해야 함
        # 릭 스트립 동작 유지 (yaml prompt_leak 패턴: ^#\s*Role — frontmatter 이후만 검사)
        text, report = strip_leaks(
            "---\n"
            'title: "Test"\n'
            "draft: true\n"
            "---\n"
            "\n"
            "## 서론\n"
            "\n"
            "내용.\n"
            "\n"
            "# Role (역할)\n"
            "\n"
            "이것은 프롬프트 유출입니다.\n"
            "\n"
            "## 결론\n"
            "\n"
            "결론 내용.",
            context="draft",
        )
        assert "# Role (역할)" not in text
        assert "이것은 프롬프트 유출입니다" not in text
        assert "## 서론" in text
        assert "## 결론" in text
