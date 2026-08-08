"""Graceful degradation: when Ollama is unreachable, state extraction returns
an empty delta instead of crashing, letting the LangQuant loop continue with
existing state. This is the contract that lets a long-running experiment survive
a transient ollama hiccup.
"""
from __future__ import annotations

import dataclasses
import json
import runpy
from pathlib import Path
from unittest.mock import patch

import pytest

from langquant import ConversationState, LangQuantSession, apply_delta, core


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
    state = ConversationState()

    with patch(
        "langquant.core.urllib.request.urlopen",
        side_effect=ConnectionError("ollama down"),
    ):
        delta = core.extract_state_delta(
            state,
            user_message="hello",
            assistant_response="hi",
        )

    assert delta == {}


def test_apply_delta_with_empty_delta_is_noop():
    state = ConversationState()
    state.goal = "original-goal"
    apply_delta(state, {})
    assert state.goal == "original-goal"


def test_main_model_payload_excludes_ui_history():
    """The transcript may exist for display but must not enter model context."""
    session = LangQuantSession()
    session.configure(goal="current goal")
    session.transcript = [
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

    with patch("langquant.core.urllib.request.urlopen", side_effect=fake_urlopen):
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


def test_public_api_uses_langquant_names():
    state = ConversationState(goal="inspectable state")
    session = LangQuantSession()
    session.state = state

    assert session.show_state().startswith("## Current Goal\ninspectable state")
    assert session.show_transcript() == []
    assert not hasattr(session, "history")
    assert not hasattr(session, "show_history")


def test_approximate_budget_is_enforced_without_mutating_state():
    state = ConversationState(
        goal="preserve the original state object",
        facts=[f"fact {index}" for index in range(20)],
        uncertainties=["one", "two", "three", "four"],
    )
    original = dataclasses.asdict(state)

    scaffold = state.to_scaffold(approx_token_budget=25)

    assert len(scaffold) <= 100
    assert scaffold.endswith("[State truncated]")
    assert dataclasses.asdict(state) == original


def test_approximate_budget_preserves_hard_constraints():
    constraint = "never send customer records to an external service"
    state = ConversationState(
        goal="preserve the release safety boundary",
        facts=[f"low-priority fact {index} " * 8 for index in range(20)],
        artifacts=[f"artifact-{index}" for index in range(10)],
        constraints=[constraint],
    )

    scaffold = state.to_scaffold(approx_token_budget=60)

    assert len(scaffold) <= 240
    assert f"## Constraints (MUST respect)\n- NOT: {constraint}" in scaffold
    assert scaffold.endswith("[State truncated]")


@pytest.mark.parametrize("approx_token_budget", [0, 5])
def test_approximate_budget_rejects_constraint_loss(approx_token_budget):
    state = ConversationState(constraints=["keep this entire hard boundary"])

    with pytest.raises(ValueError, match="too small to preserve hard constraints"):
        state.to_scaffold(approx_token_budget=approx_token_budget)


def test_chat_payload_preserves_constraints_under_budget():
    constraint = "never send customer records to an external service"
    session = LangQuantSession(approx_token_budget=60)
    session.state = ConversationState(
        goal="preserve the release safety boundary",
        facts=[f"low-priority fact {index} " * 8 for index in range(20)],
        constraints=[constraint],
    )
    requests = []
    responses = iter([
        _FakeResponse({"message": {"content": "current reply"}}),
        _FakeResponse({"message": {"content": "{}"}}),
    ])

    def fake_urlopen(request, timeout):
        requests.append((json.loads(request.data), timeout))
        return next(responses)

    with patch("langquant.core.urllib.request.urlopen", side_effect=fake_urlopen):
        session.chat("current user text")

    main_payload, _ = requests[0]
    scaffold = main_payload["messages"][0]["content"]
    assert len(scaffold) <= 240
    assert f"## Constraints (MUST respect)\n- NOT: {constraint}" in scaffold


def test_chat_gracefully_handles_updater_constraint_budget_failure(capsys):
    constraint = "preserve this hard boundary " * 400
    session = LangQuantSession(approx_token_budget=7000)
    session.state = ConversationState(constraints=[constraint])
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((json.loads(request.data), timeout))
        return _FakeResponse({"message": {"content": "main reply"}})

    with patch("langquant.core.urllib.request.urlopen", side_effect=fake_urlopen):
        reply = session.chat("current user text")

    assert reply == "main reply"
    assert requests[0][1] == 120
    assert len(requests) == 1
    assert session.transcript == [
        {"role": "user", "content": "current user text"},
        {"role": "assistant", "content": "main reply"},
    ]
    assert session.state.constraints == [constraint]
    assert session.state.turn == 1
    assert "State extraction failed" in capsys.readouterr().out


def test_apply_delta_removes_multiple_items_and_deduplicates_additions():
    state = ConversationState(
        subgoals=["alpha task", "beta task", "gamma task"],
        facts=["existing fact"],
    )

    apply_delta(
        state,
        {
            "remove_subgoals": ["alpha", "beta"],
            "add_facts": ["existing fact", "new fact", 42],
            "add_vocabulary": {"term": "meaning", "invalid": 42},
        },
    )

    assert state.subgoals == ["gamma task"]
    assert state.facts == ["existing fact", "new fact"]
    assert state.vocabulary == {"term": "meaning"}


def test_save_and_load_state_round_trip(tmp_path):
    path = tmp_path / "state.json"
    original = LangQuantSession()
    original.state = ConversationState(
        goal="ship an installable package",
        constraints=["keep the transcript outside the model request"],
        turn=3,
    )

    original.save_state(path)
    restored = LangQuantSession()
    restored.load_state(path)

    assert restored.state == original.state
    assert restored.transcript == []


def test_resume_runner_import_is_side_effect_free(tmp_path, monkeypatch):
    runner = Path(__file__).parents[1] / "resume_continuity_experiment.py"
    monkeypatch.chdir(tmp_path)

    namespace = runpy.run_path(
        str(runner),
        run_name="resume_continuity_experiment_import",
    )

    assert not (tmp_path / "results").exists()
    assert namespace["RESUME_CONDITIONS"] == (
        "naked",
        "compressed",
        "clamped",
        "naive",
    )
