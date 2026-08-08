# LangQuant

**Hold the state of a conversation outside the chat.**

LangQuant is experimental Python software for conversing with a local LLM from an explicit, refreshable language state instead of replaying the transcript on every turn.

The conversational model receives only the current state and the current message. A second model reads the latest exchange and prepares the next state. The transcript can remain visible to the human without becoming model input.

```text
current language state + current message
                    │
                    ▼
          conversational model ────► reply
                    │                  │
                    └──── state updater┘
                               │
                               ▼
                     next language state

transcript ──► human interface only
```

A transcript records what happened. LangQuant keeps a working description of what matters now: the goal, decisions, facts, constraints, unresolved threads, vocabulary, and other explicit session state.

## What this enables

- **A different kind of local conversation.** Inspect, save, edit, and restore the state that moves the conversation forward.
- **State and compaction experiments.** Change the schema, updater, model pair, or budget and observe what survives across turns.
- **A primitive for internal tools.** Put an explicit state boundary between a conversational model and the rest of an application.
- **Research on language as operational state.** Study when a language scaffold is adequate, what it omits, and how state updates fail.

LangQuant is not a vector database, transcript search engine, user-profile store, or production memory layer. It is a small state-transition mechanism you can run and inspect.

## Quick start

Requirements: Python 3.11+ and a running [Ollama](https://ollama.com) service.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install langquant

ollama pull qwen3.5:9b
ollama pull qwen3.5:4b

langquant --goal "Plan a small API change"
```

Inside the conversation:

```text
/state             show the exact state for the next model call
/transcript        show the human-facing transcript
/save state.json   save the current state
/quit              end the session
```

Try `/state` before and after a message. The change you see is the context that carries forward; earlier chat messages are not replayed to the conversational model.

## Use it from Python

```python
from langquant import LangQuantSession

session = LangQuantSession(
    main_model="qwen3.5:9b",
    state_model="qwen3.5:4b",
    approx_token_budget=7000,
)

session.configure(
    role="senior backend engineer",
    style="direct, concise, technical",
    goal="design a rate limiter for a payments API",
    constraints=["no Redis"],
)

reply = session.chat("We decided to use a token bucket.")
print(reply)

print(session.show_state())
session.save_state("state.json")
```

The saved state is ordinary JSON. It can be inspected, versioned, edited, or loaded into a later session.

```python
from langquant import LangQuantSession

session = LangQuantSession()
session.load_state("state.json")
print(session.chat("What should we decide next?"))
```

## The state transition

For turn `t`, LangQuant has the following operational shape:

```text
reply_t       = conversational_model(state_t, message_t)
state_(t + 1) = state_updater(state_t, message_t, reply_t)
```

The prior transcript is not an argument to either call. In that narrow architectural sense, this is a first-order state-transition loop.

That shape does **not** establish that the current state contains everything a conversation could need. State adequacy is the research question. An updater can omit, distort, or misclassify information, and different schemas will preserve different things.

## What is in the state?

The reference schema is typed and deliberately legible:

| Field | Purpose |
|---|---|
| `role`, `style` | how the model should act and communicate |
| `goal`, `subgoals` | what the session is trying to accomplish |
| `decisions`, `facts` | current commitments and established session facts |
| `artifacts` | files, code, or other outputs produced |
| `constraints` | boundaries that must remain active |
| `open_threads`, `uncertainties` | unresolved work and unknowns |
| `vocabulary` | session-specific terms and meanings |
| `turn` | current transition count |

The state updater proposes a JSON delta after each exchange. LangQuant applies that delta and renders the result as the next plain-language scaffold.

## Inspect the boundary

The request-boundary tests use mocked model calls, so they do not require Ollama:

```bash
python -m pytest -q
ruff check .
```

The focused tests verify that UI transcript content is absent from the conversational-model request and from the following state-update request. They also exercise graceful behavior when the local model service is unavailable.

The repository includes exploratory conversation and scaffold experiments. Read
[the experiment record](https://github.com/hermes-labs-ai/langquant/blob/main/docs/EXPERIMENTS.md)
for their design, defects, and exact claim limits. Those artifacts are research
material, not a benchmark claim that this approach outperforms summaries,
retrieval, or full transcripts.

## Project status

LangQuant is an alpha research prototype. The useful, inspectable result today is the mechanism itself: a local conversation can be wired through explicit current state while keeping prior messages out of the conversational-model request.

Good contributions include stronger state schemas, validated state deltas, deterministic evaluation, exact budget enforcement, model-provider adapters, and tools for comparing state against the transcript it replaces.

See the [contribution guide](https://github.com/hermes-labs-ai/langquant/blob/main/CONTRIBUTING.md)
to contribute.

## License

Apache 2.0.
