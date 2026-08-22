"""
Copilot tool-calling loop.

The project's central architectural claim is that the LLM never computes a
monetary figure — it only selects tools and explains what they return. These
tests exercise that loop against a stubbed Anthropic client, so the control
flow, the tool dispatch, and every failure path are covered without spending
money or needing an API key.

What is deliberately NOT asserted: the quality of the model's prose. What IS
asserted: that the numbers reaching the model come from the same engine the
REST API uses, and that no failure mode returns a 500.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import anthropic
import httpx2
import pytest

import app.api.copilot as copilot_module

# --- Minimal stand-ins for the SDK's response objects -----------------------
# The loop only touches .type/.text/.name/.input/.id on blocks and .content /
# .stop_reason on the response, so these mirror exactly that surface.

@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    name: str
    input: dict
    id: str = "toolu_test"
    type: str = "tool_use"


@dataclass
class FakeResponse:
    content: list
    stop_reason: str = "end_turn"


class FakeMessages:
    def __init__(self, script: list):
        self._script = list(script)
        self.calls: list[dict] = []

    def create(self, **kwargs) -> Any:
        self.calls.append(kwargs)
        if not self._script:
            raise AssertionError("copilot called the LLM more times than the test scripted")
        nxt = self._script.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


class FakeClient:
    def __init__(self, script: list):
        self.messages = FakeMessages(script)


@pytest.fixture
def stub_llm(monkeypatch):
    """Installs a scripted fake Anthropic client and a dummy API key."""
    monkeypatch.setattr(copilot_module.settings, "LLM_API_KEY", "test-key", raising=False)
    holder: dict[str, FakeClient] = {}

    def install(script: list) -> FakeClient:
        client = FakeClient(script)
        holder["client"] = client
        monkeypatch.setattr(copilot_module.anthropic, "Anthropic", lambda **_: client)
        return client

    return install


def _http_response(status: int) -> httpx2.Response:
    return httpx2.Response(status_code=status, request=httpx2.Request("POST", "https://api.anthropic.com"))


def _set_budget(client, total=15000, savings=0):
    return client.put(
        "/api/v1/budgets", json={"total_income": total, "savings_target": savings, "rules": []}
    )


def _add_txn(client, amount, category, days_ago=0, **kw):
    return client.post("/api/v1/transactions", json={
        "amount": amount, "category": category,
        "transaction_date": (date.today() - timedelta(days=days_ago)).isoformat(), **kw,
    })


class TestToolLoop:
    def test_plain_answer_without_tools(self, auth_client, stub_llm):
        stub_llm([FakeResponse(content=[TextBlock("Hello, ask me about your budget.")])])
        res = auth_client.post("/api/v1/copilot/chat", json={"message": "hi"})
        assert res.status_code == 200
        assert res.json()["reply"].startswith("Hello")
        assert res.json()["tool_calls_made"] == []

    def test_tool_is_executed_and_result_fed_back(self, auth_client, stub_llm):
        _set_budget(auth_client, total=15000)
        client = stub_llm([
            FakeResponse(content=[ToolUseBlock("get_safe_to_spend", {})], stop_reason="tool_use"),
            FakeResponse(content=[TextBlock("You can spend about ₹500 today.")]),
        ])
        res = auth_client.post("/api/v1/copilot/chat", json={"message": "how much can I spend?"})
        assert res.status_code == 200
        assert res.json()["tool_calls_made"] == ["get_safe_to_spend"]

        # Second call must carry the assistant turn plus a tool_result for it.
        second = client.messages.calls[1]["messages"]
        assert second[-2]["role"] == "assistant"
        results = second[-1]["content"]
        assert second[-1]["role"] == "user"
        assert results[0]["type"] == "tool_result"
        assert results[0]["is_error"] is False
        assert "remaining_budget" in results[0]["content"]

    def test_tool_output_matches_the_rest_api_exactly(self, auth_client, stub_llm):
        """
        The whole point of routing both through financial_context: the copilot
        and the dashboard must never disagree about a number.
        """
        _set_budget(auth_client, total=20000, savings=1000)
        _add_txn(auth_client, 2500, "shopping", days_ago=1)

        client = stub_llm([
            FakeResponse(content=[ToolUseBlock("get_safe_to_spend", {})], stop_reason="tool_use"),
            FakeResponse(content=[TextBlock("done")]),
        ])
        auth_client.post("/api/v1/copilot/chat", json={"message": "status?"})

        import json
        tool_payload = json.loads(client.messages.calls[1]["messages"][-1]["content"][0]["content"])
        rest = auth_client.get("/api/v1/safe-to-spend").json()

        for field in ("safe_to_spend_today", "remaining_budget", "days_remaining",
                      "overspend_risk", "financial_health_score"):
            assert tool_payload[field] == rest[field], f"{field} disagrees with the REST API"

    def test_parallel_tool_calls_return_in_one_user_message(self, auth_client, stub_llm):
        """Splitting results across messages trains the model out of parallel calls."""
        _set_budget(auth_client)
        client = stub_llm([
            FakeResponse(
                content=[
                    ToolUseBlock("get_safe_to_spend", {}, id="a"),
                    ToolUseBlock("get_spending_by_category", {}, id="b"),
                ],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[TextBlock("here you go")]),
        ])
        res = auth_client.post("/api/v1/copilot/chat", json={"message": "full picture"})
        assert res.json()["tool_calls_made"] == ["get_safe_to_spend", "get_spending_by_category"]

        final_user_msg = client.messages.calls[1]["messages"][-1]
        assert len(final_user_msg["content"]) == 2
        assert {b["tool_use_id"] for b in final_user_msg["content"]} == {"a", "b"}

    def test_evaluate_purchase_tool_receives_arguments(self, auth_client, stub_llm):
        _set_budget(auth_client, total=15000)
        client = stub_llm([
            FakeResponse(
                content=[ToolUseBlock("evaluate_purchase", {"price": 9000, "category": "shopping"})],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[TextBlock("That's a big one.")]),
        ])
        auth_client.post("/api/v1/copilot/chat", json={"message": "can I buy a ₹9000 jacket?"})

        import json
        payload = json.loads(client.messages.calls[1]["messages"][-1]["content"][0]["content"])
        assert payload["evaluation"]["recommendation"] in {"BUY_NOW", "WAIT", "SKIP"}
        assert payload["evaluation"]["budget_impact_pct"] > 50
        assert "level_name" in payload["intervention"]

    def test_missing_budget_is_flagged_to_the_model(self, auth_client, stub_llm):
        """Otherwise the model sees zeros and tells the user they're broke."""
        client = stub_llm([
            FakeResponse(content=[ToolUseBlock("get_safe_to_spend", {})], stop_reason="tool_use"),
            FakeResponse(content=[TextBlock("Set a budget first.")]),
        ])
        auth_client.post("/api/v1/copilot/chat", json={"message": "how am I doing?"})
        result = client.messages.calls[1]["messages"][-1]["content"][0]["content"]
        assert "has NOT set a budget" in result

    def test_history_is_forwarded(self, auth_client, stub_llm):
        client = stub_llm([FakeResponse(content=[TextBlock("ok")])])
        auth_client.post("/api/v1/copilot/chat", json={
            "message": "and now?",
            "history": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
        })
        sent = client.messages.calls[0]["messages"]
        assert [m["role"] for m in sent] == ["user", "assistant", "user"]
        assert sent[-1]["content"] == "and now?"


class TestToolFailuresDoNotCrash:
    def test_unknown_tool_is_reported_as_a_tool_error(self, auth_client, stub_llm):
        client = stub_llm([
            FakeResponse(content=[ToolUseBlock("nonexistent_tool", {})], stop_reason="tool_use"),
            FakeResponse(content=[TextBlock("I couldn't look that up.")]),
        ])
        res = auth_client.post("/api/v1/copilot/chat", json={"message": "?"})
        assert res.status_code == 200
        block = client.messages.calls[1]["messages"][-1]["content"][0]
        assert block["is_error"] is True
        assert "Unknown tool" in block["content"]

    def test_exception_inside_a_tool_becomes_a_tool_error_not_a_500(self, auth_client, stub_llm):
        # Missing the required 'price' argument makes the executor raise.
        client = stub_llm([
            FakeResponse(
                content=[ToolUseBlock("evaluate_purchase", {"category": "shopping"})],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[TextBlock("Tell me the price?")]),
        ])
        res = auth_client.post("/api/v1/copilot/chat", json={"message": "should I buy it?"})
        assert res.status_code == 200
        assert client.messages.calls[1]["messages"][-1]["content"][0]["is_error"] is True

    def test_iteration_cap_returns_a_graceful_message(self, auth_client, stub_llm):
        _set_budget(auth_client)
        # Always asks for another tool; must stop rather than loop forever.
        stub_llm([
            FakeResponse(content=[ToolUseBlock("get_safe_to_spend", {})], stop_reason="tool_use")
            for _ in range(copilot_module.MAX_TOOL_ITERATIONS)
        ])
        res = auth_client.post("/api/v1/copilot/chat", json={"message": "loop"})
        assert res.status_code == 200
        assert "couldn't settle on an answer" in res.json()["reply"]

    def test_refusal_stop_reason_is_handled(self, auth_client, stub_llm):
        stub_llm([FakeResponse(content=[], stop_reason="refusal")])
        res = auth_client.post("/api/v1/copilot/chat", json={"message": "something off-limits"})
        assert res.status_code == 200
        assert "can't help with that" in res.json()["reply"]

    def test_empty_text_response_still_says_something(self, auth_client, stub_llm):
        stub_llm([FakeResponse(content=[TextBlock("   ")])])
        res = auth_client.post("/api/v1/copilot/chat", json={"message": "hm"})
        assert res.status_code == 200
        assert res.json()["reply"].strip() != ""


class TestProviderErrorMapping:
    @pytest.mark.parametrize(
        "exc,expected_status,must_not_leak",
        [
            (
                anthropic.RateLimitError("slow down", response=_http_response(429), body=None),
                429,
                "slow down",
            ),
            (
                anthropic.AuthenticationError(
                    "bad key sk-ant-secret", response=_http_response(401), body=None
                ),
                503,
                "sk-ant-secret",
            ),
            (
                anthropic.APIStatusError("upstream exploded", response=_http_response(500), body=None),
                502,
                "exploded",
            ),
        ],
    )
    def test_provider_errors_map_to_clean_statuses(
        self, auth_client, stub_llm, exc, expected_status, must_not_leak
    ):
        stub_llm([exc])
        res = auth_client.post("/api/v1/copilot/chat", json={"message": "hi"})
        assert res.status_code == expected_status
        # The provider's own message may carry keys or request metadata.
        assert must_not_leak not in res.json()["detail"]
