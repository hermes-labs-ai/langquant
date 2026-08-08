<p align="center">
  <a href="https://github.com/hermes-labs-ai/langquant"><img src="https://img.shields.io/github/stars/hermes-labs-ai/langquant" alt="GitHub stars"></a>
  <a href="https://pypi.org/project/langquant/"><img src="https://img.shields.io/pypi/v/langquant?color=blue" alt="PyPI"></a>
  <a href="https://github.com/hermes-labs-ai/langquant/blob/main/LICENSE"><img src="https://img.shields.io/github/license/hermes-labs-ai/langquant" alt="License"></a>
  <a href="https://github.com/hermes-labs-ai/langquant/actions/workflows/ci.yml"><img src="https://github.com/hermes-labs-ai/langquant/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

# langquant

> Give a stateless local language model inspectable conversational state without sending it a transcript.

`langquant` is the reference implementation of LPCI (Linguistically Persistent Cognitive Interface), a Hermes Labs research prototype. On every turn, the main model receives exactly two messages:

1. a rendered, typed session-state scaffold; and
2. the current user message.

The prior conversation is never included in the main-model request. After the response, a smaller model extracts a JSON delta from the current scaffold and latest exchange. The delta updates `SessionState`, which is rendered for the next turn.

The state is plain text and JSON: you can inspect it, save it, edit it, and restore it. No fine-tuning, vector store, or retrieval step is required.

## Try it locally

Requirements: Python 3.11+, [Ollama](https://ollama.com), and the two default local models.

```bash
git clone https://github.com/hermes-labs-ai/langquant.git
cd langquant
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
ollama pull qwen3.5:9b
ollama pull qwen3.5:4b
python -m lpci
```

Inside the session, `/state` shows the scaffold that will be sent on the next turn, `/history` shows the separate UI transcript, and `/save <path>` persists the typed state.

As a library:

```python
from lpci import LPCISession

session = LPCISession(
    main_model="qwen3.5:9b",
    state_model="qwen3.5:4b",
    token_budget=7000,
)
session.configure(
    role="senior backend engineer",
    style="direct, concise, technical",
    goal="design a rate limiter for the payments API",
)

reply = session.chat("We decided to use a token bucket. Constraint: no Redis.")
print(reply)
print(session.show_state())

session.save_state("state.json")
session.load_state("state.json")
```

## How it works

```text
current SessionState
        |
        v
render typed scaffold ───────────────┐
        |                            |
        v                            |
[system: scaffold]                   |
[user: current message]              |  no previous messages
        |                            |  enter this request
        v                            |
main model (stateless)               |
        |                            |
        v                            |
response                             |
        |                            |
        v                            |
state extractor reads scaffold       |
  + current message + response       |
        |                            |
        v                            |
JSON delta -> update SessionState ───┘
```

`SessionState` is a dataclass with 12 fields: `role`, `style`, `goal`, `subgoals`, `decisions`, `facts`, `artifacts`, `constraints`, `open_threads`, `uncertainties`, `vocabulary`, and `turn`. Field names and rendered sections keep the state legible instead of hiding it in a latent vector.

The human-facing transcript is stored in `LPCISession.history`, but `LPCISession.chat()` does not read that list when building the main-model payload. The extractor receives only the current scaffold and the latest exchange.

## What the current evidence supports

The strongest result is structural and directly inspectable in `LPCISession.chat()`: the main-model request contains the rendered scaffold and current user message, while `self.history` is not read. The state updater and persistence path are likewise executable and inspectable.

The behavioral study is useful experiment history, but its current scorer does not support a clean between-condition recall claim.

The rigorous run attempted 75 sessions: 3 planning topics × 5 context conditions × 5 replications. It completed 74 sessions (1,480 turns); one `startup`/`compressed` replication is absent. The main model was `qwen3.5:9b`, the state/summary model was `qwen3.5:4b`, and each session ran for 20 turns.

The run reported the following harness outputs. “Mean probe score” is the mean of keyword-based recall probes within each completed session, then averaged by condition:

| Condition | Completed sessions | Mean probe score | Mean final state words | Main-model context |
|---|---:|---:|---:|---|
| `naked` | 15 | 0.846 | 975 | typed scaffold, without added contrastive instructions |
| `compressed` | 14 | 0.831 | 1,026 | typed scaffold with contrastive instructions |
| `naive` | 15 | 0.792 | 109 | freeform summary of the latest 10 messages |
| `clamped` | 15 | 0.759 | 490 | typed scaffold with an approximately 500-word clamp |
| `raw` | 15 | 0.000 | 0 | current message only |

The often-quoted table contrast is `naked` 0.846 versus `raw` 0.000, with **n=15 completed sessions per arm**. The 74-session count describes the whole five-condition run; it is not the sample size for that contrast. However, the current evaluator gives `raw` an empty `SessionState`, so its decision-recall score is zero by construction even if a response happened to match an earlier fact. This table must not be interpreted as a validated 0.846-point model-recall lift.

The naive-summary result is competitive. It scored 0.792 with a much smaller prompt than any unclamped typed scaffold, and it exceeded the clamped condition on this harness metric. The evaluator builds the naive arm's comparison state from prior assistant-response prefixes, while LPCI arms use extractor-produced decisions, so this is also not a uniform ground-truth comparison. LangQuant does **not** claim recall superiority over ordinary summarization. What the implementation demonstrates is a different system property: no transcript reaches the main model, while the refreshed state remains typed and inspectable.

The committed 20-turn A/B trace and the separate 720-trial scaffold-amplification matrix are also included in [`results/`](results/). See [Experiment record and limitations](docs/EXPERIMENTS.md) for data provenance, scoring details, the naive baseline, estimator failure history, and exact reproduction commands.

## What this does not establish

- **Not production readiness.** State extraction can paraphrase, misclassify, or silently omit information.
- **Not a validated recall effect.** The conditions are not scored against one shared ground-truth state, and the `raw` arm's zero is imposed by an empty evaluator state.
- **Not semantic-memory completeness.** The exploratory score is keyword-based and derived partly from extractor-produced state; it is not blinded human adjudication.
- **Not a fixed token bound.** The default renderer uses an approximate four-characters-per-token trim. Only the experimental `clamped` condition applies an additional hard word-count routine, and even that routine has fallback limits.
- **Not scale beyond 20 turns.** No committed continuity run is longer.
- **Not cross-model or cross-language generality.** The continuity study used one Qwen model family and English planning tasks.
- **Not a claim that the current scaffold is a sufficient Markov state.** The attempted transfer-entropy analyses are not valid evidence for that proposition; the rigorous estimator was non-discriminating.
- **Not a durability layer by itself.** `save_state()` and `load_state()` persist a single JSON state, but there is no concurrent store, audit log, retrieval system, or access-control layer.

## LPCI and adjacent approaches

LPCI combines three familiar ideas in one deliberately narrow design: stateless inference, externalized state, and structured context engineering. The label applies to this combination—zero transcript to the main model, a typed language scaffold, and model-assisted refresh—not to summarization or external memory in general.

| Approach | What the main model receives | State representation | Fine-tune | Retrieval |
|---|---|---|---:|---:|
| Full transcript | all prior messages | transcript | no | no |
| Naive rolling summary | freeform summary, sometimes recent messages | text summary | no | no |
| MemGPT / Letta | recent context plus retrieved memory | tiered memory | no | yes |
| Gist tokens / AutoCompressors | learned compressed representation | latent | yes | no |
| **LPCI in this repo** | **typed scaffold + current message** | **inspectable text/JSON** | **no** | **no** |

This is a structural comparison, not a benchmark ranking. Relevant prior work includes [MemGPT](https://arxiv.org/abs/2310.08560), [Gist Tokens](https://arxiv.org/abs/2304.08467), [AutoCompressors](https://arxiv.org/abs/2305.14788), and work on [long-context position effects](https://arxiv.org/abs/2307.03172).

## Run the existing checks

The unit tests do not require Ollama:

```bash
python -m pytest -v --ignore=results/
ruff check .
```

The experiment runners do require the local models and can be slow. They overwrite result paths, so copy the committed files before intentionally reproducing a run.

```bash
python lpci_test.py
python lpci_rigorous.py
python run_experiment.py
python analyze_results.py
```

No new model run is needed to inspect the shipped evidence. The JSONL files can be recounted directly; the commands are in [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).

## Project status

LangQuant is an alpha research prototype. Contributions that improve state fidelity, deterministic scoring, experiment manifests, or bounded-state behavior are especially welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

If you use this repository in research, citation metadata is available in [CITATION.cff](CITATION.cff):

```bibtex
@misc{langquant2026,
  author = {Bosch, Rolando},
  title  = {langquant: the Linguistically Persistent Cognitive Interface (LPCI) reference implementation},
  year   = {2026},
  url    = {https://github.com/hermes-labs-ai/langquant},
  note   = {Hermes Labs}
}
```

## About Hermes Labs

[Hermes Labs](https://hermes-labs.ai) is an AI reliability engineering studio for product and engineering teams shipping production agents and LLM applications. We find the structural AI failures standard evals miss, then harden retrieval, memory, agents, and the language layers around production AI systems with runtime controls and defensible evidence. Everything released here is Apache-2.0, free, no SaaS tier. The longer-horizon framing is in [ambient assurance](https://hermes-labs.ai/archive/ambient-assurance).

- Site: https://hermes-labs.ai
- Contact: roli@hermes-labs.ai
- Writing: https://rolibosch.substack.com
- Video: https://youtube.com/@rolifromhermes
- Full OSS stack: https://github.com/hermes-labs-ai

## License

Apache 2.0.
