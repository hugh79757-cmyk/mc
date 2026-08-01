"""Tests for chain_models.py — AI 출력 파싱 및 JSON 메타데이터 분리."""
import json
import pytest

from chain_models import (
    parse_ai_output, _extract_meta_from_raw, _extract_body_from_raw,
    AIOutput, AIOutputMeta, AIParseError
)


class TestParseAIOutputJSONSeparation:
    """parse_ai_output() JSON 메타 분리 검증"""

    def test_code_fence_json(self):
        """코드펜스 있는 JSON (```json\n{...}\n```)"""
        raw = '''본문입니다.
```json
{"image_type": "photo", "image_keyword": "test"}
```
'''
        out = parse_ai_output(raw)
        assert out.meta.image_type == "photo"
        assert out.meta.image_keyword == "test"
        assert "image_type" not in out.body
        assert "image_keyword" not in out.body

    def test_plain_json_no_fence(self):
        """코드펜스 없는 평문 JSON ({...})"""
        raw = '''본문입니다.
{"image_type": "chart", "chart_type": "bar", "chart_data": {}}
'''
        out = parse_ai_output(raw)
        assert out.meta.image_type == "chart"
        assert out.meta.chart_type == "bar"
        assert "image_type" not in out.body

    def test_indented_multiline_json(self):
        """들여쓰기·다중라인 JSON"""
        raw = '''본문입니다.
  {
    "image_type": "photo",
    "image_keyword": "test"
  }
'''
        out = parse_ai_output(raw)
        assert out.meta.image_type == "photo"
        assert "image_type" not in out.body

    def test_no_meta(self):
        """메타데이터 없는 출력"""
        raw = "본문만 있습니다. JSON 없습니다."
        out = parse_ai_output(raw)
        assert out.meta.image_type == "none"
        assert out.body == "본문만 있습니다. JSON 없습니다."

    def test_broken_json_fallback(self):
        """깨진 JSON ({image_type: "photo"}) → 폴백: 기본값, 원문 유지"""
        raw = '본문 {image_type: "photo"} 올바르지 않음'
        out = parse_ai_output(raw)
        assert out.meta.image_type == "none"  # 폴백: 기본값
        assert "image_type" in out.body  # 원문 유지

    def test_multiple_json_first_meta_only(self):
        """다중 JSON → 첫 번째 메타만 사용"""
        raw = '''본문
{"image_type": "photo", "image_keyword": "first"}
다른 내용
{"image_type": "chart", "chart_type": "bar"}
'''
        out = parse_ai_output(raw)
        assert out.meta.image_type == "photo"  # 첫 번째만
        # 두 번째 JSON은 본문에 잔류 → 2차 방어(_extract_clean_body)가 처리

    def test_code_fence_with_extra_whitespace(self):
        """코드펜스에 여분의 공백/개행 포함"""
        raw = '''내용입니다.

```json
{
  "image_type": "photo",
  "image_keyword": "spaced"
}
```

끝.'''
        out = parse_ai_output(raw)
        assert out.meta.image_type == "photo"
        assert out.meta.image_keyword == "spaced"
        assert "image_type" not in out.body

    def test_generic_code_fence_json(self):
        """일반 코드펜스(``` 만) 내 JSON"""
        raw = '''본문
```
{"image_type": "chart", "chart_type": "line", "chart_data": {"x": [1,2]}}
```
나머지'''
        out = parse_ai_output(raw)
        assert out.meta.image_type == "chart"
        assert out.meta.chart_type == "line"
        assert "image_type" not in out.body

    def test_nested_json_in_text(self):
        """텍스트 중간에 중첩된 JSON 유사 구조 → 외부 키가 있어 스키마 검증 실패, 폴백"""
        raw = '''설명: {"nested": {"image_type": "photo", "image_keyword": "inner"}}
본문 계속'''
        out = parse_ai_output(raw)
        # 외부 키(nested)가 있어 AIOutputMeta 스키마 검증 실패 → 폴백
        assert out.meta.image_type == "none"
        assert "설명:" in out.body
        assert "본문 계속" in out.body

    def test_chart_type_only_meta(self):
        """chart_type만 있는 메타 (image_type 명시 안 함) → image_type=none 기본값"""
        raw = '''데이터 분석 결과
{"chart_type": "bar", "chart_data": {"labels": ["A", "B"], "values": [1, 2]}}
끝'''
        out = parse_ai_output(raw)
        # image_type이 명시되지 않으면 "none" 기본값 (AI가 image_type을 명시해야 함)
        assert out.meta.image_type == "none"
        assert out.meta.chart_type == "bar"  # 차트 필드는 저장됨
        assert "chart_type" not in out.body


class TestExtractMetaFromRaw:
    """_extract_meta_from_raw() 단위 테스트"""

    def test_finds_first_valid_meta(self):
        """첫 번째 유효 메타만 반환"""
        raw = '{"image_type": "photo", "image_keyword": "first"} 텍스트 {"image_type": "chart"}'
        meta = _extract_meta_from_raw(raw)
        assert meta["image_type"] == "photo"
        assert meta["image_keyword"] == "first"

    def test_returns_empty_on_no_meta_keys(self):
        """메타 키 없는 JSON은 무시"""
        raw = '{"other": "value"}'
        meta = _extract_meta_from_raw(raw)
        assert meta == {}

    def test_lookback_expansion_2000_chars(self):
        """2000자 룩백으로 깊은 위치 JSON 탐지"""
        # 1000자 텍스트 + JSON
        long_text = "x " * 600  # ~1200자
        raw = f'{long_text}{{"image_type": "photo", "image_keyword": "deep"}}'
        meta = _extract_meta_from_raw(raw)
        assert meta["image_type"] == "photo"
        assert meta["image_keyword"] == "deep"


class TestExtractBodyFromRaw:
    """_extract_body_from_raw() 단위 테스트"""

    def test_removes_code_fence_json(self):
        """코드펜스 JSON 제거"""
        raw = '''본문
```json
{"image_type": "photo"}
```
끝'''
        body = _extract_body_from_raw(raw)
        assert "image_type" not in body
        assert "본문" in body
        assert "끝" in body

    def test_removes_plain_json(self):
        """평문 JSON 제거"""
        raw = '''본문
{"image_type": "photo", "image_keyword": "test"}
끝'''
        body = _extract_body_from_raw(raw)
        assert "image_type" not in body
        assert "image_keyword" not in body
        assert "본문" in body
        assert "끝" in body

    def test_removes_indented_multiline_json(self):
        """들여쓰기 다중라인 JSON 제거"""
        raw = '''본문
  {
    "image_type": "chart",
    "chart_type": "bar"
  }
끝'''
        body = _extract_body_from_raw(raw)
        assert "image_type" not in body
        assert "chart_type" not in body
        assert "본문" in body
        assert "끝" in body

    def test_removes_multiple_json_blocks(self):
        """다중 JSON 블록 모두 제거"""
        raw = '''첫 번째
{"image_type": "photo"}
중간
{"chart_type": "bar"}
마지막'''
        body = _extract_body_from_raw(raw)
        assert "image_type" not in body
        assert "chart_type" not in body
        assert "첫 번째" in body
        assert "중간" in body
        assert "마지막" in body

    def test_preserves_non_meta_json(self):
        """메타 키 없는 JSON은 보존 (의도된 데이터일 수 있음)"""
        raw = '''데이터: {"name": "test", "value": 123}'''
        body = _extract_body_from_raw(raw)
        assert "name" in body
        assert "value" in body

    def test_removes_frontmatter_block(self):
        """AI가 출력한 FM 블록 제거"""
        raw = '''---
title: "Test"
draft: true
---
본문 내용'''
        body = _extract_body_from_raw(raw)
        assert "title" not in body
        assert "draft" not in body
        assert "본문 내용" in body

    def test_removes_placeholders(self):
        """플레이스홀더 제거"""
        raw = '''본문
<!-- thumbnail: test.jpg -->
<!-- todo: image -->
끝'''
        body = _extract_body_from_raw(raw)
        assert "thumbnail" not in body
        assert "todo" not in body
        assert "본문" in body
        assert "끝" in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])