import json

from chain_publisher_core import _request_safe_url
from search_retriever import retrieve_medical_context_for_post


class FakeMedicalClient:
    def __init__(self):
        self.queries = []

    def search(self, query, endpoint="webkr", display=5, start=1, sort="sim"):
        self.queries.append(query)
        if "site:mfds.go.kr" in query:
            title = "식품의약품안전처 의약품 정보"
            link = "https://www.mfds.go.kr/drug/리바로정"
        elif "site:nedrug.mfds.go.kr" in query:
            title = "의약품안전나라 품목정보"
            link = "https://nedrug.mfds.go.kr/pbp/cmn/item/리바로정"
        else:
            title = "한국의약품안전관리원 이상사례 정보"
            link = "https://www.drugsafe.or.kr/리바로정"
        return True, json.dumps({"items": [{"title": title, "description": "공식 설명", "link": link}]})


def test_medical_context_queries_official_sources():
    client = FakeMedicalClient()
    ok, context = retrieve_medical_context_for_post("리바로정", client)
    assert ok is True
    assert len(client.queries) == 3
    assert any("site:mfds.go.kr" in q for q in client.queries)
    assert any("site:nedrug.mfds.go.kr" in q for q in client.queries)
    assert any("site:drugsafe.or.kr" in q for q in client.queries)
    assert "식품의약품안전처(MFDS)" in context
    assert "의약품안전나라(DrugSafe)" in context
    assert "한국의약품안전관리원" in context


def test_request_safe_url_quotes_non_ascii_path_and_preserves_percent_encoding():
    raw = "https://img-issue.techpawz.com/리바로정 2026.webp?x=한글&ok=1"
    safe = _request_safe_url(raw)
    assert "/%EB%A6%AC%EB%B0%94%EB%A1%9C%EC%A0%95%202026.webp" in safe
    assert "x=%ED%95%9C%EA%B8%80&ok=1" in safe
    assert "%25EB" not in safe
