"""Tests for audit/audit_chain.py — whitelist content check conversion."""
import pytest


class TestAuditWhitelist:
    """audit_chain.py whitelist 검증: 허용 마크다운만 통과, 비허용 요소 경고."""

    def test_audit_flags_raw_json_in_body(self):
        """raw JSON이 본문에 있으면 audit이 경고."""
        from audit.audit_chain import check_content_by_whitelist

        body = '## 제목\n\n본문 내용입니다.\n{"image_type": "photo", "image_keyword": "cat"}\n\n추가 내용.'
        issues = check_content_by_whitelist(body)
        assert len(issues) > 0, "raw JSON이 감지되어야 함"
        assert any("JSON" in issue or "json" in issue.lower() for issue in issues)

    def test_audit_flags_html_comment(self):
        """HTML 주석이 본문에 있으면 audit이 경고."""
        from audit.audit_chain import check_content_by_whitelist

        body = "## 제목\n\n본문입니다.\n<!-- 광고 삽입 위치 -->\n\n계속."
        issues = check_content_by_whitelist(body)
        assert len(issues) > 0
        assert any("주석" in issue or "comment" in issue.lower() for issue in issues)

    def test_audit_flags_meta_tag(self):
        """<meta> 태그가 본문에 있으면 audit이 경고."""
        from audit.audit_chain import check_content_by_whitelist

        body = "## 제목\n\n본문입니다.\n<meta name=\"keywords\" content=\"test\">\n\n계속."
        issues = check_content_by_whitelist(body)
        assert len(issues) > 0
        assert any("태그" in issue or "meta" in issue.lower() for issue in issues)

    def test_audit_passes_clean_markdown(self):
        """유효한 마크다운만 있으면 audit이 경고 0건."""
        from audit.audit_chain import check_content_by_whitelist

        body = """# 제목

본문 단락입니다. 여러 내용이 들어갑니다.

## 부제목

- 목록 항목 1
- 목록 항목 2

| 헤더1 | 헤더2 |
|-------|-------|
| 셀1   | 셀2   |

```python
print("hello")
```

마지막 문단입니다."""
        issues = check_content_by_whitelist(body)
        assert len(issues) == 0, f"0건이어야 함: {issues}"

    def test_audit_consistent_with_main_pipeline(self):
        """메인이 차단하는 핵심 항목을 audit도 차단하는지 검증."""
        from audit.audit_chain import check_content_by_whitelist

        # 메인 파이프라인(_extract_clean_body)이 차단하는 항목들
        cases = {
            "raw JSON in body": '## 제목\n\n{"image_type": "photo"}',
            "HTML comment": "## 제목\n\n<!-- hidden -->",
            "<meta> tag": "## 제목\n\n<meta charset='utf-8'>",
        }
        for name, body in cases.items():
            issues = check_content_by_whitelist(body)
            assert len(issues) > 0, f"메인 차단 항목을 audit이 놓침: {name}"
