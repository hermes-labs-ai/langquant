"""Graceful degradation: when Ollama is unreachable, state extraction returns
an empty delta instead of crashing — letting the LPCI loop continue with
existing state. This is the contract that lets a long-running experiment survive
a transient ollama hiccup.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import lpci


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_state_extraction_returns_empty_when_ollama_down():
    state = lpci.SessionState()

    with patch("lpci.urllib.request.urlopen", side_effect=ConnectionError("ollama down")):
        delta = lpci.extract_state_delta(
            state,
            user_message="hello",
            assistant_response="hi",
        )

    assert delta == {}


def test_apply_delta_with_empty_delta_is_noop():
    state = lpci.SessionState()
    state.goal = "original-goal"
    lpci.apply_delta(state, {})
    assert state.goal == "original-goal"


def test_main_model_payload_excludes_ui_history():
    """The transcript may exist for display but must not enter model context."""
    session = lpci.LPCISession()
    session.configure(goal="current goal")
    session.history = [
        {"role": "user", "content": "prior secret user text"},
        {"role": "assistant", "content": "prior secret assistant text"},
    ]
    requests = []
    responses = iter([
        _FakeResponse({"message": {"content": "current reply"}}),
        _FakeResponse({"message": {"content": "{}"}}),
    ])

    def fake_urlopen(request, timeout):
        requests.append((json.loads(request.data), timeout))
        return next(responses)

    with patch("lpci.urllib.request.urlopen", side_effect=fake_urlopen):
        assert session.chat("current user text") == "current reply"

    main_payload, main_timeout = requests[0]
    assert main_timeout == 120
    assert main_payload["messages"] == [
        {"role": "system", "content": "## Current Goal\ncurrent goal\n\n\n[Session turn: 0]"},
        {"role": "user", "content": "current user text"},
    ]
    assert "prior secret" not in json.dumps(main_payload)

    extractor_payload, extractor_timeout = requests[1]
    assert extractor_timeout == 30
    extractor_prompt = extractor_payload["messages"][0]["content"]
    assert "current user text" in extractor_prompt
    assert "current reply" in extractor_prompt
    assert "prior secret" not in extractor_prompt
