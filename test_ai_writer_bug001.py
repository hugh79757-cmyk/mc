"""BUG-001: shared/ai_writer.py reasoning_content 추출 시 응답 중간 절단 수정 검증.

재현 (BUG-QUEUE.md):
- reasoning 모델에서 content가 비어있으면 reasoning_content(사고 과정)를 그대로 반환.
  reasoning_content는 완결된 문장이 아니어서 JSON이 중간에 잘림 (`Unterminated string`).
- `derive_chain("함안연꽃테마파크")` 2차 재현: 742자 응답 — `"image_prompt": "Overhead
  panoramic view...` 문자열 도중 절단.

수정 방향 (검증 대상):
- finish_reason=="length" 또는 잘림 시그니처(마지막 문자가 `,:{"[` / 백슬래시)로 끝나면
  잘린 조각을 결과로 반환하지 않고 max_tokens 증분 재요청.
- 기존 동작 보존: 정상 응답 / 완결된 reasoning_content 추출은 그대로 반환.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import mc_paths  # 5000 repo를 sys.path에 등록 (shared.* import 가능하게)
from shared.ai_writer import TRUNCATION_MAX_TOKENS_CAP, _is_truncated, generate


# ── 재현 데이터 ──

# BUG-QUEUE 재현: "Overhead panoramic view... 문자열 도중 절단" — 마지막 문자가 평범한 글자
TRUNCATED_REASONING = (
    '{"posts":[{"title":"함안연꽃테마파크","angle":"개요","image_prompt": '
    '"Overhead panoramic view of the lotus park at sunset with soft golden light '
    'reflecting on the pond, lush green leaves and pink blooms scattered across '
    'the water surface, a wooden walking bridge crossing the lotus'
)

VALID_JSON = json.dumps(
    [
        {"title": "함안연꽃테마파크 개요", "angle": "기초", "image_prompt": "overhead"},
        {"title": "함안연꽃테마파크 비교", "angle": "심화", "image_prompt": "wide"},
        {"title": "함안연꽃테마파크 실전", "angle": "전문", "image_prompt": "close"},
    ],
    ensure_ascii=False,
)


# ── 헬퍼 ──

def _fake_config(max_tokens=6000):
    """모든 tier가 존재하는 fake models.yaml config."""
    tiers = {}
    for name in ("default", "fallback1", "fallback2", "fallback3", "economy"):
        tiers[name] = {
            "provider": "deepseek",
            "model": f"model-{name}",
            "temperature": 0.85,
            "max_tokens": max_tokens,
        }
    return {
        "providers": {"deepseek": {"api_key_env": "DEEPSEEK_API_KEY", "base_url": "http://x"}},
        "tier_order": list(tiers),
        **tiers,
    }


def _response(content=None, reasoning_content=None, finish_reason="stop"):
    """create()가 반환하는 fake OpenAI ChatCompletion."""
    message = MagicMock()
    message.content = content
    message.reasoning_content = reasoning_content
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = finish_reason
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock()
    resp.usage.total_tokens = 10
    return resp


@pytest.fixture(autouse=True)
def _reset_circuit_state():
    from shared import ai_writer

    ai_writer._circuit_state["failures"] = 0
    ai_writer._circuit_state["open_until"] = 0.0
    yield
    ai_writer._circuit_state["failures"] = 0
    ai_writer._circuit_state["open_until"] = 0.0


# ── generate() 절단 재시도 검증 (과목 2/4: mock 재현) ──

class TestGenerateTruncationRetry:
    def _generate(self, client, max_tokens=None):
        with (
            patch("shared.ai_writer.load_models_config", return_value=_fake_config()),
            patch("shared.ai_writer.get_client", return_value=client),
            patch("shared.ai_writer.time.sleep"),
        ):
            return generate("system", "user", max_tokens=max_tokens)
    def test_reasoning_content_is_ignored_and_retries_without_leak(self):
        """Reasoning content is never promoted to user-visible content."""
        # The production policy ignores reasoning_content to prevent chain-of-thought leakage.
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _response(content=None, reasoning_content=TRUNCATED_REASONING, finish_reason="length"),
            _response(content=VALID_JSON, finish_reason="stop"),
        ]
        result = self._generate(client)

        assert result["content"] == VALID_JSON
        assert client.chat.completions.create.call_count == 2
        assert TRUNCATED_REASONING not in result["content"]
        calls = client.chat.completions.create.call_args_list
        assert calls[1].kwargs["max_tokens"] == calls[0].kwargs["max_tokens"] == 6000

    def test_finish_reason_length_with_nonempty_content_retries(self):
        """content가 있어도 finish_reason=length면 절단으로 보고 재시도."""
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _response(content='{"posts": [{"title": "A"},', finish_reason="length"),
            _response(content=VALID_JSON, finish_reason="stop"),
        ]
        result = self._generate(client)

        assert result["content"] == VALID_JSON
        assert client.chat.completions.create.call_count == 2

    def test_valid_content_returns_without_retry(self):
        """정상 응답(finish_reason=stop)은 1회 호출로 그대로 반환 — 기존 동작 보존."""
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _response(content=VALID_JSON, finish_reason="stop"),
        ]
        result = self._generate(client)

        assert result["content"] == VALID_JSON
        assert client.chat.completions.create.call_count == 1

    def test_complete_reasoning_content_is_rejected(self):
        """Complete reasoning_content is not promoted to user-visible content."""
        client = MagicMock()
        response = _response(content=None, reasoning_content=VALID_JSON, finish_reason="stop")
        client.chat.completions.create.side_effect = [response] * (5 * 3)
        with pytest.raises(RuntimeError):
            self._generate(client)
        assert client.chat.completions.create.call_count == 5 * 3

    def test_all_truncated_raises_runtime_error(self):
        """모든 tier/재시도가 잘리면 RuntimeError — 잘린 조각을 성공으로 반환하지 않음."""
        client = MagicMock()
        truncated = _response(
            content=None, reasoning_content=TRUNCATED_REASONING, finish_reason="length"
        )
        client.chat.completions.create.side_effect = [truncated] * (5 * 3)  # explicit tier_order: 5 tiers x 3 retries
        with pytest.raises(RuntimeError):
            self._generate(client)
        assert client.chat.completions.create.call_count == 5 * 3

    def test_max_tokens_cap_applied(self):
        """증분 계산 시 TRUNCATION_MAX_TOKENS_CAP 상한 적용."""
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _response(content=TRUNCATED_REASONING, finish_reason="length"),
            _response(content=VALID_JSON, finish_reason="stop"),
        ]
        self._generate(client, max_tokens=20000)

        second_kwargs = client.chat.completions.create.call_args_list[1].kwargs
        assert second_kwargs["max_tokens"] == TRUNCATION_MAX_TOKENS_CAP  # 20000*2+512 > cap


# ── _is_truncated 판정 단위 검증 (과목 2) ──

class TestIsTruncated:
    def test_finish_reason_length_always_truncated(self):
        assert _is_truncated("...abc", "length") is True
        assert _is_truncated("", "length") is True

    def test_signature_endings_are_truncated(self):
        for ch in (",", ":", "{", "[", '"', "\\"):
            assert _is_truncated("something" + ch, "stop") is True, repr(ch)

    def test_complete_endings_not_truncated(self):
        for text in ('{"a": 1}', "[1, 2]", "완결된 문장입니다.", "done", "   "):
            assert _is_truncated(text, "stop") is False, repr(text)

    def test_empty_not_truncated_when_no_length(self):
        assert _is_truncated("", None) is False
        assert _is_truncated(None, "stop") is False

    def test_midword_cut_requires_finish_reason(self):
        """BUG-001: 문자열 도중 절단은 JSON 완결성 검사로 finish_reason 없이도 감지.

        T1 수정(Phase 36): `_is_truncated`에 JSON 완결성 검사 추가 — `{`로 시작하면
        count({) > count(}) → truncated. 구버전은 finish_reason 신호에만 의존해
        이 재현 케이스를 놓쳤다 (removed: finish_reason 미존재 시 False였던 동작).
        """
        assert _is_truncated(TRUNCATED_REASONING, None) is True
        assert _is_truncated(TRUNCATED_REASONING, "length") is True

class TestTimeoutFallback:
    def test_request_timeout_moves_to_next_tier(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            TimeoutError('request timed out'),
            _response(content=VALID_JSON, finish_reason='stop'),
        ]
        owner = TestGenerateTruncationRetry()
        with (
            patch('shared.ai_writer.load_models_config', return_value=_fake_config()),
            patch('shared.ai_writer.get_client', return_value=client),
            patch('shared.ai_writer.time.sleep'),
        ):
            result = generate('system', 'user')
        assert result['content'] == VALID_JSON
        assert client.chat.completions.create.call_count == 2
