"""pytest configuration and shared fixtures for mc project."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ─── Environment Setup ───

def pytest_configure(config):
    """Configure test environment before test collection."""
    # Set test environment variables
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    os.environ.setdefault("UNSPLASH_ACCESS_KEY", "test-unsplash")
    os.environ.setdefault("PEXELS_API_KEY", "test-pexels")
    os.environ.setdefault("KREA_API_KEY", "test-krea")
    os.environ.setdefault("R2_ENDPOINT_URL", "https://test.r2.cloudflarestorage.com")
    os.environ.setdefault("R2_ACCESS_KEY_ID", "test-access")
    os.environ.setdefault("R2_SECRET_ACCESS_KEY", "test-secret")
    os.environ.setdefault("R2_BUCKET_NAME", "test-bucket")
    os.environ.setdefault("R2_PUBLIC_URL", "https://img.test.com")


# ─── Fixtures ───

@pytest.fixture
def temp_dir():
    """Provide a temporary directory that cleans up after test."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def mock_openai():
    """Mock OpenAI API responses."""
    with patch("openai.OpenAI") as mock:
        client = MagicMock()
        mock.return_value = client
        # Default chat completion response
        client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "topics": [{"title": "Test Topic", "angle": "Test Angle", "category_guess": "tech", "bridge_logic": "Test bridge"}]
            })))]
        )
        yield client


@pytest.fixture
def mock_requests():
    """Mock requests.get/post for HTTP calls."""
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"results": [], "photos": []},
            raise_for_status=lambda: None,
            content=b"fake-image-data",
        )
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "test-job"},
            raise_for_status=lambda: None,
        )
        yield {"get": mock_get, "post": mock_post}


@pytest.fixture
def mock_boto3():
    """Mock boto3 R2 client."""
    with patch("boto3.client") as mock:
        client = MagicMock()
        mock.return_value = client
        client.upload_file.return_value = None
        client.head_object.return_value = {"ContentLength": 100}
        client.head_bucket.return_value = {}
        yield client


@pytest.fixture
def sample_chain_config():
    """Sample chain_config.yaml content for testing."""
    return {
        "sites": {
            "rotcha": {
                "site_path": "/fake/rotcha-blog",
                "blog_id": "manual_rotcha",
                "base_url": "https://rotcha.kr",
                "publisher_type": "hugo",
                "hugo_root": "/fake/rotcha-blog",
                "theme": "Blowfish",
                "cf_pages_project": "rotcha-blog",
                "permalink_pattern": "/posts/:slug/",
                "content_dir": "content/posts",
            },
            "issue.techpawz": {
                "site_path": "/fake/issue-techpawz-hugo",
                "blog_id": "manual_issue_techpawz",
                "base_url": "https://issue.techpawz.com",
                "publisher_type": "hugo",
                "hugo_root": "/fake/issue-techpawz-hugo",
                "theme": "Blowfish",
                "cf_pages_project": "issue-techpawz-hugo",
                "permalink_pattern": "/posts/:slug/",
                "content_dir": "content/posts",
            },
            "techpawz": {
                "site_path": "/fake/techpawz-hugo",
                "blog_id": "manual_techpawz",
                "base_url": "https://techpawz.com",
                "publisher_type": "hugo",
                "hugo_root": "/fake/techpawz-hugo",
                "theme": "Blowfish",
                "cf_pages_project": "techpawz-hugo",
                "permalink_pattern": "/:slug/",
                "content_dir": "content/posts",
            },
        },
        "chain_directions": {
            "depth": {"label": "깊이", "step_roles": {1: "기초", 2: "분석", 3: "전문"}},
            "swallow": {"label": "역방향", "step_roles": {1: "구매", 2: "절약", 3: "금융"}},
            "lateral": {"label": "횡방향", "step_roles": {1: "주제", 2: "비교", 3: "비즈니스"}},
        },
        "keyword_mapping": {"tech": "depth", "shopping": "swallow", "travel": "lateral"},
        "chain_blogs": {0: "rotcha", 1: "issue.techpawz", 2: "techpawz"},
        "ai_writer": {"tier": "default", "temperature": 0.85},
        "thumbnail": {
            "provider": "auto",
            "fallback_chain": ["unsplash", "pexels"],
            "target_size": [1024, 1024],
            "text_overlay": {"enabled": True, "font": "assets/fonts/NotoSansKR-Regular.otf", "bg_alpha": 0.55},
        },
        "pollinations": {
            "enabled": False,
            "base_url": "https://image.pollinations.ai/prompt/",
            "width": 1024,
            "height": 1024,
            "model": "flux",
            "rate_limit_seconds": 15,
        },
    }


@pytest.fixture
def sample_prompts():
    """Sample prompts.yaml content for testing - matches actual prompt keys."""
    return {
        "derive_system": "You are a blog chain planner.",
        "derive_user_depth": "Seed: {seed}\nCategory: {category}\nChain type: depth\nReturn JSON with 3 topics.",
        "derive_user_swallow": "Seed: {seed}\nCategory: {category}\nChain type: swallow\nReturn JSON with 3 topics.",
        "derive_user_lateral": "Seed: {seed}\nCategory: {category}\nChain type: lateral\nReturn JSON with 3 topics.",
        "derive_user_lateral_travel": "Seed: {seed}\nCategory: {category}\nChain type: lateral (travel)\nStep 3 angle: 현장 실전과 방문 전 체크포인트\nReturn JSON with 3 topics.",
        "derive_user_lateral_real_estate": "Seed: {seed}\nCategory: {category}\nChain type: lateral (real_estate)\nStep 3 angle: 계약 확정과 입주 완료\nReturn JSON with 3 topics.",
        "derive_user_lateral_automotive": "Seed: {seed}\nCategory: {category}\nChain type: lateral (automotive)\nStep 3 angle: 구매 확정과 인도 완료\nReturn JSON with 3 topics.",
        "derive_user_lateral_stock": "Seed: {seed}\nCategory: {category}\nChain type: lateral (stock)\nStep 3 angle: 매수/매도 실행과 포트폴리오 관리\nReturn JSON with 3 topics.",
        "derive_user_lateral_etc": "Seed: {seed}\nCategory: {category}\nChain type: lateral (etc)\nStep 3 angle: 최종 구매 확정과 장기 활용\nReturn JSON with 3 topics.",
        "draft_system": "You are a blog writer.",
        "draft_user": "Blog: {blog_name} ({blog_url})\nKeyword: {target_keyword}\nTitle: {title}\nAngle: {angle}\nCategory: {category}\n\nChain Context: {step} / {depth_role}\n\n{prev_context}\n\n{next_context}\n\n[STRUCTURE]\n{h2_guidelines}",
        "keyword_categories": {
            "travel": {
                "patterns": [
                    "(여행|관광|맛집|호텔|리조트|풀빌라|숙소|펜션|빌라|캠핑|글램핑|민박|게스트하우스|호스텔|항공|비행기|투어|패키지|항공권|워터파크|해수욕장|계곡|테마파크|온천|스파$|사우나|액티비티|렌트카|렌터카)",
                    "(제주|부산|서울|경주|강릉|속초|여수|통영|일본|동남아|유럽|미국|괌|사이판|인천|대구|대전|수원|창원|전주|안동|담양|보성|남해|거제|포항|울릉도|춘천|양양|평창|정선|태백|삼척|영덕|남원|부안|군산|익산)",
                    "(소노벨|소노문|소노인|한화리조트|대명리조트|신라스테이|신라호텔|제일리조트|금호리조트|홀리데이인)",
                ],
                "step1_sections": [
                    "## {keyword} — 위치와 기본 정보",
                    "## {keyword} — 시설과 특징 살펴보기",
                    "## {keyword} — 이용 안내와 방문 팁",
                    "## 마무리 — {keyword} 핵심 요약",
                ],
                "step2_sections": [
                    "## {keyword} — 비교 탐색과 선택 기준",
                    "## {keyword} — 시즌별 이용 꿀팁",
                    "## {keyword} — 실제 이용 후기로 보는 장단점",
                    "## 마무리 — {keyword} 최상의 경험하기",
                ],
                "step3_sections": [
                    "## {keyword} — 실전 준비와 방문 전 체크포인트",
                    "## {keyword} — 현장에서 알아두면 좋은 점",
                    "## {keyword} — 실제 경험담으로 보는 장단점",
                    "## 마무리 — {keyword} 최상의 경험을 위해",
                ],
            },
            "real_estate": {
                "patterns": ["(아파트|분양|청약|오피스텔|빌딩|상가|토지|재건축|재개발|리모델링)"],
                "step1_sections": [
                    "## {keyword} — 단지 기본 정보",
                    "## {keyword} — 평면도와 타입별 특징",
                    "## {keyword} — 분양가와 주변 시세",
                    "## 마무리 — {keyword} 핵심 체크포인트",
                ],
                "step2_sections": [
                    "## {keyword} — 청약과 계약 전략",
                    "## {keyword} — 대출과 세금 미리보기",
                    "## {keyword} — 입주민 후기와 단지 평가",
                    "## 마무리 — {keyword} 계약 전 꼭 확인할 것",
                ],
                "step3_sections": [
                    "## {keyword} — 계약서 핵심 조항 살펴보기",
                    "## {keyword} — 등기 이전과 소유권 확인",
                    "## {keyword} — 입주 전 하자 보수 체크리스트",
                    "## 마무리 — {keyword} 이사 계획과 입주 준비",
                ],
            },
            "automotive": {
                "patterns": ["(하이브리드|전기차|SUV|세단|RV|EV|내연기관|자동차|차량|신차|중고차|리스|할부|렌트카|카셰어링)"],
                "step1_sections": [
                    "## {keyword} — 제품 개요와 스펙",
                    "## {keyword} — 트림별 가격과 옵션",
                    "## {keyword} — 경쟁 모델과 비교하기",
                    "## 마무리 — {keyword} 선택 전에",
                ],
                "step2_sections": [
                    "## {keyword} — 구매 전략 (신차 vs 중고차)",
                    "## {keyword} — 프로모션과 할인 혜택",
                    "## {keyword} — 오너 후기로 보는 장단점",
                    "## 마무리 — {keyword} 계약 전 확인",
                ],
                "step3_sections": [
                    "## {keyword} — 유지비 따져보기",
                    "## {keyword} — 차량 인도 시 확인할 점검표",
                    "## {keyword} — 실제 리스크와 주의점",
                    "## 마무리 — {keyword} 결정 전 최종 점검",
                ],
            },
            "stock": {
                "patterns": ["(주식|코스피|코스닥|나스닥|ETF|펀드|배당|IRP|연금|적립식|재테크|투자|매수|매도|증권|금리|환율|채권|원자재|선물|옵션|주가)"],
                "step1_sections": [
                    "## {keyword} — 기본 개념과 시장 흐름",
                    "## {keyword} — 최근 성과와 수익률",
                    "## {keyword} — 특징과 리스크 요인",
                    "## 마무리 — {keyword} 투자 전 체크리스트",
                ],
                "step2_sections": [
                    "## {keyword} — 실전 투자 전략",
                    "## {keyword} — 세금과 수수료 줄이기",
                    "## {keyword} — 포트폴리오에 담는 법",
                    "## 마무리 — {keyword} 실전 적용하기",
                ],
                "step3_sections": [
                    "## {keyword} — 매수 타이밍 구체화하기",
                    "## {keyword} — 손절과 익절 기준 세우기",
                    "## {keyword} — 리스크 관리와 분산 전략",
                    "## 마무리 — {keyword} 정기 리밸런싱과 배당 재투자",
                ],
            },
            "etc": {
                "patterns": [],
                "step1_sections": [
                    "## {keyword} — 개요와 핵심 특징",
                    "## {keyword} — 주요 기능과 장점",
                    "## {keyword} — 선택 시 고려사항",
                    "## 마무리 — {keyword} 핵심 요약",
                ],
                "step2_sections": [
                    "## {keyword} — 실전 활용법",
                    "## {keyword} — 효과적인 설정과 팁",
                    "## {keyword} — 유사 서비스와 비교",
                    "## 마무리 — {keyword} 실전 가치",
                ],
                "step3_sections": [
                    "## {keyword} — 실제 사용 후기와 평점",
                    "## {keyword} — 가격 비교와 구매처",
                    "## {keyword} — 최종 추천과 선택 기준",
                    "## 마무리 — {keyword} 종합 정리",
                ],
            },
        },
        "image_system": "Create image prompt.",
        "image_user": "Keyword: {keyword}, Blog: {blog}, Step: {step}",
    }


@pytest.fixture
def sample_draft_md():
    """Sample draft markdown with frontmatter."""
    return """---
title: "Test Post Title"
description: "Test description for SEO"
tags: ["테스트", "기술", "블로그"]
categories: ["기술"]
draft: true
---

## 서론

이것은 테스트 서론입니다.

## 본론

본론 내용입니다.

## 결론

결론입니다.

<!--todo:image-->
"""


@pytest.fixture
def sample_chain_post():
    """Sample chain post dict for testing."""
    return {
        "id": 1,
        "chain_id": 1,
        "step": 1,
        "depth": 0,
        "slug": "test-post-1",
        "title": "Test Post Title",
        "target_keyword": "test keyword",
        "category_guess": "기술",
        "image_keyword": "test image",
        "image_prompt": "test prompt",
        "draft_md": """---
title: "Test Post Title"
description: "Test description"
tags: ["테스트", "기술"]
categories: ["기술"]
draft: true
---

## 서론

서론 내용.

## 본론

본론 내용.

## 결론

결론 내용.

<!--todo:image-->
""",
        "status": "drafted",
        "thumbnail_path": None,
        "thumbnail_source": None,
        "published_url": None,
    }


# ─── Test Helpers ───

def assert_valid_frontmatter(fm_text: str):
    """Assert frontmatter has required fields and valid format."""
    assert fm_text.startswith("---")
    assert "title:" in fm_text
    assert "description:" in fm_text
    assert "tags:" in fm_text
    assert "categories:" in fm_text
    assert "draft:" in fm_text
    # Check no colon in title (common bug)
    for line in fm_text.splitlines():
        if line.strip().startswith("title:"):
            assert ":" not in line.split("title:", 1)[1].strip().strip('"'), "Title contains colon"
    # Check one-line arrays
    for line in fm_text.splitlines():
        if "tags:" in line or "categories:" in line:
            assert line.count("[") == 1 and line.count("]") == 1, f"Array not one-line: {line}"


def assert_no_prompt_leak(text: str):
    """Assert no prompt leak patterns in text (uses mc.leak_defense)."""
    from mc.leak_defense import strip_leaks
    _, report = strip_leaks(text, context="test")
    for leak_type, data in report.items():
        if leak_type == "prompt_leak" and data["removed"] > 0:
            matches = [m.get("match", "") for m in data["matches"]]
            assert False, f"Prompt leak detected: {matches}"


def assert_no_unresolved_markers(text: str):
    """Assert no unresolved image/chart markers."""
    forbidden = [
        "<!-- thumbnail:",
        "<!-- image:",
        "<!--todo:image-->",
        "<!--todo:chart-->",
        "<!-- todo:image -->",
        "<!-- todo:chart -->",
    ]
    for pattern in forbidden:
        assert pattern not in text, f"Unresolved marker: {pattern}"


def assert_no_cta_leak(text: str):
    """Assert no AI-generated CTA blocks (uses mc.leak_defense)."""
    from mc.leak_defense import strip_leaks
    _, report = strip_leaks(text, context="test")
    cta_data = report.get("cta_leak", {})
    if cta_data["removed"] > 0:
        matches = [m.get("match", "") for m in cta_data["matches"]]
        assert False, f"CTA leak detected: {matches}"