"""BUG-003 (Phase 36 T5): use_context 스킵('id' 예외) 검증 테스트.

검증 항목:
- 과목 2: retrieve_context_for_post 재시도 로직 단위 테스트 (retries 인자)
- 과목 4: draft_single_post에서 post dict에 id가 없어도 검색 컨텍스트 주입이
          중단되지 않는지 (id 부재 시 DB 저장만 스킵)
- 과목 7: draft에 검색 컨텍스트(참고 자료) 포함 여부

참고:
- BUG-003 증상: 16회 루프 중 use_context=True 12회 전부
  "검색 컨텍스트 스킵: 'id'" 예외 → 컨텍스트 없는 상태로 초안 생성.
- 수정(기존 구현 확인): chain_drafter.py draft_single_post —
  post.get("id") + None 체크 + DB 저장 try/except 격리.
  search_retriever.py retrieve_context_for_post — retries 인자 추가.
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, ".")

from search_retriever import retrieve_context_for_post  # noqa: E402


# ── 재시도 로직 단위 테스트 (과목 2) ──

class TestRetrieveContextRetries:
    """retrieve_context_for_post retries 로직 검증"""

    def _make_client(self, results):
        """results: endpoint 호출 시 순서대로 반환할 (ok, data) 목록"""
        client = MagicMock()
        client.search.side_effect = results
        return client

    def _ok_data(self):
        return (True, json.dumps({
            "items": [{"title": "제목", "description": "설명", "link": "http://x/1"}]
        }))

    def test_success_no_extra_retry(self):
        """첫 호출 성공 → 재시도 없음 (retries=1이지만 추가 호출 0)"""
        client = self._make_client([self._ok_data()] * 10)
        with patch("search_retriever.time.sleep"):
            ok, ctx = retrieve_context_for_post("키워드", "basic", client, retries=1)
        assert ok is True
        assert "참고 자료" in ctx
        # 3개 endpoint(basic: encyc/kin/webkr) 모두 1회씩만 호출
        assert client.search.call_count == 3

    def test_transient_failure_retried(self):
        """일시적 실패(첫 호출) → 재시도 성공 (retries=1)"""
        fail = (False, "Naver API error: timed out")
        ok = self._ok_data()
        # encyc 실패→재시도 성공, 나머지 endpoint 성공
        results = [fail, ok, ok, ok]
        client = self._make_client(results)
        with patch("search_retriever.time.sleep"):
            ok_flag, ctx = retrieve_context_for_post("키워드", "basic", client, retries=1)
        assert ok_flag is True
        assert "참고 자료" in ctx
        # encyc 2회(실패+재시도) + kin 1회 + webkr 1회 = 4회
        assert client.search.call_count == 4

    def test_retries_zero_no_retry(self):
        """retries=0 → 실패 시 재시도 없음, 해당 endpoint 스킵"""
        fail = (False, "Naver API error")
        ok = self._ok_data()
        # encyc 실패(재시도 없음), kin/webkr 성공
        client = self._make_client([fail, ok, ok])
        with patch("search_retriever.time.sleep"):
            ok_flag, ctx = retrieve_context_for_post("키워드", "basic", client, retries=0)
        assert ok_flag is True
        assert "참고 자료" in ctx
        assert client.search.call_count == 3  # encyc 1 + kin 1 + webkr 1

    def test_all_endpoints_fail_returns_false(self):
        """모든 endpoint 실패 → (False, 에러) 반환"""
        client = self._make_client([(False, "fail")] * 10)
        with patch("search_retriever.time.sleep"):
            ok_flag, err = retrieve_context_for_post("키워드", "basic", client, retries=1)
        assert ok_flag is False
        assert err == "No search results found"


# ── draft_single_post id 부재 격리 (과목 4/7) ──

VALID_AI_OUTPUT = """```json
{
  "title": "테스트 포스트",
  "image_type": "photo",
  "image_keyword": "테스트",
  "chart_type": "none"
}
```

## 소개

정상 본문입니다.

## 결론

마무리 문단입니다."""


def _fake_generate_result(content):
    """generate()가 반환하는 dict 형태 (result["content"], result["model"])"""
    return {"content": content, "model": "test-model"}


class TestDraftSinglePostIdIsolation:
    """post dict에 id가 없어도 검색 컨텍스트 주입이 중단되지 않아야 함 (BUG-003)"""

    def _call_draft(self, post, search_ok=True):
        """draft_single_post 호출 (generate/Naver/DB 모두 mock)"""
        ctx_md = (
            "## 참고 자료\n\n"
            "다음은 이 글의 주제와 관련된 검색 결과입니다.\n\n"
            "### 1. 용인로만바스 정보\n> 시설이 좋습니다.\n"
        )
        client = MagicMock()
        if search_ok:
            client.search.return_value = (True, json.dumps({
                "items": [{"title": "용인로만바스", "description": "시설", "link": "http://x/1"}]
            }))
        else:
            client.search.return_value = (False, "Naver API error")

        with (
            patch("chain_drafter.NaverSearchClient", return_value=client),
            patch("chain_drafter.generate", return_value=_fake_generate_result(VALID_AI_OUTPUT)),
            patch("chain_db.update_post_context") as mock_db_save,
        ):
            from chain_drafter import draft_single_post
            return draft_single_post(
                post=post,
                posts=[post],
                seed_keyword="용인로만바스",
                use_context=True,
            ), mock_db_save

    def test_post_without_id_draft_succeeds(self):
        """id 없는 post → 예외 없이 초안 생성 + 컨텍스트 주입 유지"""
        post = {
            "depth": 1,
            "step": 1,
            "chain_type": "depth",
            "title": "용인로만바스 개요",
            "angle": "기초",
            "chain_id": 99999,
        }
        (draft_md, meta, raw), mock_db_save = self._call_draft(post)
        # 초안 본문 존재
        assert "정상 본문입니다" in draft_md
        # id 부재 → DB 저장 스킵 (호출 없음)
        mock_db_save.assert_not_called()

    def test_post_with_id_db_saved(self):
        """id 있는 post → 컨텍스트 DB 저장 호출됨 (기존 동작 보존)"""
        post = {
            "id": 777,
            "depth": 1,
            "step": 1,
            "chain_type": "depth",
            "title": "용인로만바스 개요",
            "angle": "기초",
            "chain_id": 99999,
        }
        _, mock_db_save = self._call_draft(post)
        mock_db_save.assert_called_once()
        # DB 저장 인자는 (post_id, 컨텍스트) 형식
        args, kwargs = mock_db_save.call_args
        assert args[0] == 777

    def test_context_injected_in_draft(self):
        """검색 컨텍스트가 generate user_prompt에 주입됨 (과목 7)"""
        post = {
            "id": 777,
            "depth": 1,
            "step": 1,
            "chain_type": "depth",
            "title": "용인로만바스 개요",
            "angle": "기초",
            "chain_id": 99999,
        }
        client = MagicMock()
        client.search.return_value = (True, json.dumps({
            "items": [{"title": "용인로만바스", "description": "시설", "link": "http://x/1"}]
        }))
        with (
            patch("chain_drafter.NaverSearchClient", return_value=client),
            patch("chain_drafter.generate") as mock_gen,
            patch("chain_db.update_post_context"),
        ):
            from chain_drafter import draft_single_post
            mock_gen.return_value = _fake_generate_result(VALID_AI_OUTPUT)
            draft_single_post(
                post=post, posts=[post], seed_keyword="용인로만바스", use_context=True
            )
        # generate 호출의 user_prompt(2번째 인자)에 참고 자료 포함
        assert mock_gen.call_count == 1
        user_prompt = mock_gen.call_args[0][1]
        assert "참고 자료" in user_prompt

    def test_context_skip_when_search_fails(self):
        """검색 실패 시 스킵하되 초안 생성은 계속 (기존 동작 보존)"""
        post = {
            "id": 777,
            "depth": 1,
            "step": 1,
            "chain_type": "depth",
            "title": "용인로만바스 개요",
            "angle": "기초",
            "chain_id": 99999,
        }
        (draft_md, _, _), mock_db_save = self._call_draft(post, search_ok=False)
        assert "정상 본문입니다" in draft_md
        mock_db_save.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
