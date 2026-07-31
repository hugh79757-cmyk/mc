"""Tests for config JSON-Schema validation (Phase 26 W4 — 03-03).

검증 대상:
- config/schema.yaml 이 prompts.yaml / chain_config.yaml 의 실구조를
  관대(permissive)하게 수용한다 (기존 유효 설정 거부 금지).
- 잘못된 타입/누락 필드/구조 오류가 명확한 메시지와 함께 거부된다.
- chain_publisher_core.load_and_validate_config 가 파일명+오류 목록을
  포함한 ConfigValidationError 를 발생시킨다.

주의: 실제 config 파일은 수정하지 않는다 — dict 직접 검증 + monkeypatch.
"""
import pytest

from mc_paths import load_config


def _real_prompts():
    """실제 config/prompts.yaml (읽기 전용, 수정 안 함)."""
    return load_config("prompts.yaml")


def _real_chain_config():
    """실제 config/chain_config.yaml (읽기 전용, 수정 안 함)."""
    return load_config("chain_config.yaml")


class TestSchemaFile:
    """schema.yaml 자체가 유효한 YAML + 두 서브스키마 보유."""

    def test_schema_yaml_loads(self):
        import yaml
        from mc_paths import CONFIG_DIR
        import os
        with open(os.path.join(CONFIG_DIR, "schema.yaml"), encoding="utf-8") as f:
            schema = yaml.safe_load(f)
        assert "prompts" in schema
        assert "chain_config" in schema
        assert schema["prompts"]["type"] == "object"
        assert "keyword_mapping" in schema["chain_config"]["properties"]

    def test_schema_min_lines(self):
        """must_haves: min_lines 30 이상."""
        from mc_paths import CONFIG_DIR
        import os
        with open(os.path.join(CONFIG_DIR, "schema.yaml"), encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) >= 30


class TestRealConfigsPass:
    """실제 설정 파일이 스키마를 통과한다 (관대함 검증)."""

    def test_real_prompts_passes(self):
        from chain_publisher_core import validate_config
        errors = validate_config(_real_prompts(), "prompts.yaml")
        assert errors == []

    def test_real_chain_config_passes(self):
        from chain_publisher_core import validate_config
        errors = validate_config(_real_chain_config(), "chain_config.yaml")
        assert errors == []

    def test_real_etc_category_empty_patterns_passes(self):
        """etc 카테고리의 빈 patterns 배열이 거부되지 않는다."""
        from chain_publisher_core import validate_config
        config = _real_prompts()
        assert config["keyword_categories"]["etc"]["patterns"] == []
        assert validate_config(config, "prompts.yaml") == []

    def test_unknown_extra_keys_allowed(self):
        """additionalProperties=true — 미래 키 확장 허용 (관대함)."""
        from chain_publisher_core import validate_config
        config = _real_prompts()
        config["future_new_key"] = {"any": "thing"}
        assert validate_config(config, "prompts.yaml") == []
        cfg2 = _real_chain_config()
        cfg2["future_section"] = [1, 2, 3]
        assert validate_config(cfg2, "chain_config.yaml") == []


class TestInvalidRejected:
    """잘못된 설정이 명확한 오류와 함께 거부된다."""

    def test_wrong_type_keyword_mapping_value(self):
        """keyword_mapping 값이 str 이 아니라 int → 거부."""
        from chain_publisher_core import validate_config
        config = _real_chain_config()
        config["keyword_mapping"]["travel"] = 42
        errors = validate_config(config, "chain_config.yaml")
        assert errors, "int 값이 거부되어야 함"
        assert any("keyword_mapping" in e for e in errors)

    def test_unknown_direction_value(self):
        """enum 밖의 방향 값 → 거부."""
        from chain_publisher_core import validate_config
        config = _real_chain_config()
        config["keyword_mapping"]["travel"] = "diagonal"
        errors = validate_config(config, "chain_config.yaml")
        assert errors
        assert any("travel" in e for e in errors)

    def test_keyword_mapping_wrong_structure(self):
        """keyword_mapping 이 dict 가 아니라 list → 거부."""
        from chain_publisher_core import validate_config
        config = _real_chain_config()
        config["keyword_mapping"] = ["travel", "depth"]
        errors = validate_config(config, "chain_config.yaml")
        assert errors
        assert any("keyword_mapping" in e for e in errors)

    def test_missing_required_prompts_field(self):
        """prompts.yaml 에 keyword_categories 누락 → 거부."""
        from chain_publisher_core import validate_config
        config = _real_prompts()
        del config["keyword_categories"]
        errors = validate_config(config, "prompts.yaml")
        assert errors
        assert any("keyword_categories" in e for e in errors)

    def test_missing_required_chain_config_field(self):
        """chain_config 에 keyword_mapping 누락 → 거부."""
        from chain_publisher_core import validate_config
        config = _real_chain_config()
        del config["keyword_mapping"]
        errors = validate_config(config, "chain_config.yaml")
        assert errors
        assert any("keyword_mapping" in e for e in errors)

    def test_category_patterns_wrong_type(self):
        """카테고리 patterns 가 배열이 아니라 문자열 → 거부."""
        from chain_publisher_core import validate_config
        config = _real_prompts()
        config["keyword_categories"]["travel"]["patterns"] = "여행"
        errors = validate_config(config, "prompts.yaml")
        assert errors
        assert any("patterns" in e for e in errors)

    def test_category_missing_cta_phrases(self):
        """카테고리 cta_phrases 누락 → 거부."""
        from chain_publisher_core import validate_config
        config = _real_prompts()
        del config["keyword_categories"]["stock"]["cta_phrases"]
        errors = validate_config(config, "prompts.yaml")
        assert errors
        assert any("cta_phrases" in e for e in errors)

    def test_char_count_wrong_type(self):
        """char_count.min 이 문자열 → 거부."""
        from chain_publisher_core import validate_config
        config = _real_prompts()
        config["keyword_categories"]["travel"]["char_count"]["rotcha"]["min"] = "1000"
        errors = validate_config(config, "prompts.yaml")
        assert errors
        assert any("min" in e for e in errors)


class TestLoadAndValidateConfig:
    """load_and_validate_config — 성공/실패 + 명확한 오류 메시지."""

    def test_success_returns_config(self):
        from chain_publisher_core import load_and_validate_config
        config = load_and_validate_config("chain_config.yaml")
        assert isinstance(config, dict)
        assert "keyword_mapping" in config

    def test_invalid_raises_with_filename(self, monkeypatch):
        import chain_publisher_core as cpc
        bad = _real_chain_config()
        bad["keyword_mapping"]["travel"] = 42
        monkeypatch.setattr(cpc, "load_config", lambda name: bad)
        with pytest.raises(cpc.ConfigValidationError) as excinfo:
            cpc.load_and_validate_config("chain_config.yaml")
        msg = str(excinfo.value)
        assert "chain_config.yaml" in msg          # 파일명 포함
        assert "keyword_mapping" in msg            # 오류 위치 포함

    def test_invalid_prompts_raises(self, monkeypatch):
        import chain_publisher_core as cpc
        bad = _real_prompts()
        del bad["keyword_categories"]
        monkeypatch.setattr(cpc, "load_config", lambda name: bad)
        with pytest.raises(cpc.ConfigValidationError) as excinfo:
            cpc.load_and_validate_config("prompts.yaml")
        msg = str(excinfo.value)
        assert "prompts.yaml" in msg
        assert "keyword_categories" in msg

    def test_validation_error_is_value_error(self):
        """ConfigValidationError 는 ValueError 계열 (호출자 try/except 호환)."""
        from chain_publisher_core import ConfigValidationError
        assert issubclass(ConfigValidationError, ValueError)

    def test_existing_load_config_unchanged(self):
        """기존 mc_paths.load_config 는 검증 없이 동작 (회귀 없음)."""
        config = _real_chain_config()
        assert isinstance(config, dict)
        assert "sites" in config
