"""LangQuant's explicit conversational-state loop.

Architecture:
  - User sees: normal conversation
  - Model sees: [state scaffold] + [current message only]
  - After each turn: state scaffold refreshes under an approximate text budget
  - The transcript is a UI concern, not a model concern

Every token the model sees (except the current message) is pure state.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass, field

OLLAMA_URL = "http://localhost:11434/api/chat"


# ── State Schema ─────────────────────────────────────────────────────────────

@dataclass
class ConversationState:
    """Explicit language state carried between conversation turns."""

    # Identity & mode
    role: str = ""                    # Who the model is in this session
    style: str = ""                   # Communication style constraints

    # What we're doing
    goal: str = ""                    # Current high-level objective
    subgoals: list[str] = field(default_factory=list)  # Active sub-tasks

    # What we know
    decisions: list[str] = field(default_factory=list)  # Things decided (irreversible)
    facts: list[str] = field(default_factory=list)      # Established truths for this session
    artifacts: list[str] = field(default_factory=list)   # Things produced (files, code, results)

    # What we must not do
    constraints: list[str] = field(default_factory=list)  # Hard boundaries (NOTs)

    # What's open
    open_threads: list[str] = field(default_factory=list)  # Unresolved questions/tasks
    uncertainties: list[str] = field(default_factory=list)  # Things we're unsure about

    # Vocabulary — domain terms that anchor the session
    vocabulary: dict[str, str] = field(default_factory=dict)  # term → meaning

    # Turn counter
    turn: int = 0

    def to_scaffold(self, approx_token_budget: int = 7000) -> str:
        """Render state as a dense scaffold for model injection."""
        sections = []

        if self.role or self.style:
            sections.append(f"## Identity\nRole: {self.role}\nStyle: {self.style}")

        if self.goal:
            goal_block = f"## Current Goal\n{self.goal}"
            if self.subgoals:
                goal_block += "\nActive sub-tasks:\n" + "\n".join(f"- {s}" for s in self.subgoals)
            sections.append(goal_block)

        if self.decisions:
            sections.append("## Decisions (final)\n" + "\n".join(f"- {d}" for d in self.decisions))

        if self.facts:
            sections.append("## Known Facts\n" + "\n".join(f"- {f}" for f in self.facts))

        if self.artifacts:
            sections.append("## Artifacts Produced\n" + "\n".join(f"- {a}" for a in self.artifacts))

        if self.constraints:
            sections.append("## Constraints (MUST respect)\n" + "\n".join(f"- NOT: {c}" for c in self.constraints))

        if self.open_threads:
            sections.append("## Open Threads\n" + "\n".join(f"- {t}" for t in self.open_threads))

        if self.uncertainties:
            sections.append("## Uncertainties\n" + "\n".join(f"- {u}" for u in self.uncertainties))

        if self.vocabulary:
            vocab_lines = [f"- {k}: {v}" for k, v in self.vocabulary.items()]
            sections.append("## Vocabulary\n" + "\n".join(vocab_lines))

        sections.append(f"\n[Session turn: {self.turn}]")

        scaffold = "\n\n".join(sections)

        # Enforce the documented approximate budget (rough: 1 token ≈ 4 chars)
        # without mutating the underlying state while rendering it.
        char_budget = max(0, approx_token_budget * 4)
        if len(scaffold) > char_budget:
            scaffold = self._trim_to_budget(scaffold, char_budget)

        return scaffold

    def _trim_to_budget(self, scaffold: str, char_budget: int) -> str:
        """Return a visibly truncated scaffold within the approximate budget."""
        if len(scaffold) <= char_budget:
            return scaffold
        if char_budget <= 0:
            return ""

        marker = "\n\n[State truncated]"
        if char_budget <= len(marker):
            return marker[:char_budget]
        return scaffold[: char_budget - len(marker)].rstrip() + marker


# ── State Updater ────────────────────────────────────────────────────────────

UPDATE_PROMPT = """You are a state extraction engine. Given a conversation turn (user message + assistant response), update the session state.

Current state:
{current_state}

Latest exchange:
User: {user_message}
Assistant: {assistant_response}

Extract state changes as JSON. Only include fields that changed. Possible fields:
- "goal": string (if goal changed or was clarified)
- "add_subgoals": [strings] (new sub-tasks identified)
- "remove_subgoals": [strings] (sub-tasks completed)
- "add_decisions": [strings] (new irreversible decisions)
- "add_facts": [strings] (new established truths)
- "add_artifacts": [strings] (new things produced)
- "add_constraints": [strings] (new hard boundaries)
- "add_open_threads": [strings] (new unresolved questions)
- "remove_open_threads": [strings] (questions resolved)
- "add_uncertainties": [strings] (new unknowns)
- "remove_uncertainties": [strings] (unknowns resolved)
- "add_vocabulary": {{"term": "meaning"}} (new domain terms)
- "style": string (if communication style changed)

Respond ONLY with valid JSON. Be precise and terse. Every word costs tokens."""


def extract_state_delta(
    state: ConversationState,
    user_message: str,
    assistant_response: str,
    model: str = "qwen3.5:4b",
    ollama_url: str = "http://localhost:11434",
) -> dict:
    """Use a small model to extract state changes from a conversation turn."""
    prompt = UPDATE_PROMPT.format(
        current_state=state.to_scaffold(approx_token_budget=2000),
        user_message=user_message[:1000],
        assistant_response=assistant_response[:1000],
    )

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.1, "num_predict": 512},
    }).encode()

    req = urllib.request.Request(
        f"{ollama_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            content = data.get("message", {}).get("content", "")
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            # Try to extract JSON
            start = content.find("{")
            if start >= 0:
                decoded, _ = json.JSONDecoder().raw_decode(content[start:])
                if isinstance(decoded, dict):
                    return decoded
    except Exception as e:
        print(f"[langquant] State extraction failed: {e}")

    return {}


def apply_delta(state: ConversationState, delta: dict) -> None:
    """Apply extracted state changes to the session state."""
    if isinstance(delta.get("goal"), str):
        state.goal = delta["goal"]
    if isinstance(delta.get("style"), str):
        state.style = delta["style"]

    for key, attr in [
        ("add_subgoals", "subgoals"),
        ("add_decisions", "decisions"),
        ("add_facts", "facts"),
        ("add_artifacts", "artifacts"),
        ("add_constraints", "constraints"),
        ("add_open_threads", "open_threads"),
        ("add_uncertainties", "uncertainties"),
    ]:
        if isinstance(delta.get(key), list):
            target = getattr(state, attr)
            for item in delta[key]:
                if isinstance(item, str) and item not in target:
                    target.append(item)

    for key, attr in [
        ("remove_subgoals", "subgoals"),
        ("remove_open_threads", "open_threads"),
        ("remove_uncertainties", "uncertainties"),
    ]:
        if isinstance(delta.get(key), list):
            removals = [item.lower() for item in delta[key] if isinstance(item, str)]
            current = getattr(state, attr)
            setattr(
                state,
                attr,
                [item for item in current if not any(term in item.lower() for term in removals)],
            )

    if "add_vocabulary" in delta and isinstance(delta["add_vocabulary"], dict):
        state.vocabulary.update({
            key: value
            for key, value in delta["add_vocabulary"].items()
            if isinstance(key, str) and isinstance(value, str)
        })

    state.turn += 1


# ── LangQuant Session ────────────────────────────────────────────────────────

class LangQuantSession:
    """
    A conversation session where the model only ever sees:
      [state scaffold] + [current message]

    The transcript is retained for the human interface, not sent to the model.
    """

    def __init__(
        self,
        main_model: str = "qwen3.5:9b",
        state_model: str = "qwen3.5:4b",
        approx_token_budget: int = 7000,
        ollama_url: str = "http://localhost:11434",
    ):
        self.main_model = main_model
        self.state_model = state_model
        self.approx_token_budget = approx_token_budget
        self.ollama_url = ollama_url
        self.state = ConversationState()

        # UI-only transcript (not sent to model)
        self.transcript: list[dict] = []

    def configure(self, role: str = "", style: str = "", goal: str = "", constraints: list[str] | None = None):
        """Set initial session parameters."""
        if role:
            self.state.role = role
        if style:
            self.state.style = style
        if goal:
            self.state.goal = goal
        if constraints:
            self.state.constraints = constraints

    def chat(self, user_message: str) -> str:
        """
        Send a message. The model sees ONLY the scaffold + this message.
        After response, scaffold refreshes with new state.
        """
        # Build what the model sees
        scaffold = self.state.to_scaffold(approx_token_budget=self.approx_token_budget)

        messages = [
            {"role": "system", "content": scaffold},
            {"role": "user", "content": user_message},
        ]

        # Call main model
        payload = json.dumps({
            "model": self.main_model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.7, "num_predict": 2048},
        }).encode()

        req = urllib.request.Request(
            f"{self.ollama_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                response = data.get("message", {}).get("content", "")
                response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
        except Exception as e:
            response = f"[Error: {e}]"

        # Store in UI transcript (human-readable, not sent to model)
        self.transcript.append({"role": "user", "content": user_message})
        self.transcript.append({"role": "assistant", "content": response})

        # Refresh state: extract delta and apply
        delta = extract_state_delta(
            state=self.state,
            user_message=user_message,
            assistant_response=response,
            model=self.state_model,
            ollama_url=self.ollama_url,
        )
        apply_delta(self.state, delta)

        return response

    def show_state(self) -> str:
        """Show current scaffold (what the model would see)."""
        return self.state.to_scaffold(approx_token_budget=self.approx_token_budget)

    def show_transcript(self) -> list[dict]:
        """Show the UI transcript (what the user sees)."""
        return self.transcript

    def save_state(self, path: str) -> None:
        """Persist state to disk."""
        import dataclasses
        with open(path, "w") as f:
            json.dump(dataclasses.asdict(self.state), f, indent=2)

    def load_state(self, path: str) -> None:
        """Restore state from disk."""
        with open(path) as f:
            data = json.load(f)
        self.state = ConversationState(**data)


# ── Interactive CLI ──────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="langquant",
        description="Hold conversational state outside the chat transcript.",
    )
    parser.add_argument("--model", default="qwen3.5:9b", help="Main conversation model")
    parser.add_argument("--state-model", default="qwen3.5:4b", help="Model for state extraction")
    parser.add_argument(
        "--budget",
        type=int,
        default=7000,
        help="Approximate token budget for the state scaffold",
    )
    parser.add_argument("--role", default="helpful assistant", help="Model role")
    parser.add_argument("--goal", default="", help="Initial session goal")
    args = parser.parse_args()

    session = LangQuantSession(
        main_model=args.model,
        state_model=args.state_model,
        approx_token_budget=args.budget,
    )
    session.configure(
        role=args.role,
        style="direct, concise, technical",
        goal=args.goal,
    )

    print(
        f"LangQuant session started | model: {args.model} | "
        f"state: {args.state_model} | approximate budget: {args.budget} tokens"
    )
    print("Commands: /state (show scaffold), /transcript (show turns), /save <path>, /quit")
    print("-" * 60)

    while True:
        try:
            user_input = input("\nyou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[session ended]")
            break

        if not user_input:
            continue
        if user_input == "/quit":
            break
        if user_input == "/state":
            print("\n--- SCAFFOLD (what the model sees) ---")
            print(session.show_state())
            print("--- END SCAFFOLD ---")
            continue
        if user_input == "/transcript":
            for msg in session.show_transcript():
                role = msg["role"]
                content = msg["content"][:200]
                print(f"[{role}] {content}...")
            continue
        if user_input.startswith("/save "):
            path = user_input[6:].strip()
            session.save_state(path)
            print(f"State saved to {path}")
            continue

        t0 = time.monotonic()
        response = session.chat(user_input)
        elapsed = time.monotonic() - t0

        print(f"\nassistant: {response}")
        print(f"\n[turn {session.state.turn} | {elapsed:.1f}s | state: {len(session.show_state())} chars]")
