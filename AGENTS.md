# AGENTS.md — Agent Instructions for LangQuant

## What this project is

LangQuant is a research prototype exploring explicit conversational state outside the chat. A local conversational model receives only a refreshing structured language scaffold and the current message; the prior transcript stays outside its request. The no-transcript request boundary is directly inspectable in code. Current behavioral and information-flow artifacts are exploratory; do not present them as a validated recall lift or Markov-state result.

## Architecture

```
langquant/
├── langquant/           # ConversationState, LangQuantSession, state update, CLI
├── conversation_ab_experiment.py  # A/B continuity experiment
├── continuity_experiment.py       # Five-condition continuity experiment
├── analyze_results.py   # Information-theoretic analysis (MI, KL, transfer entropy)
├── run_experiment.py    # Scaffold amplification matrix harness
├── tests/               # Offline tests: request boundary, budgets, claim guard
├── docs/EXPERIMENTS.md  # Experiment record and claim limits
├── results/             # JSONL experiment artifacts (continuity + matrix run)
├── tasks/               # Task definitions for matrix run
├── LOG.md               # Development log
└── TODO.md              # Roadmap: done/superseded items and unscheduled model runs
```

## Key concepts

1. **ConversationState**: Typed dataclass with 12 fields (role, style, goal, subgoals, decisions, facts, artifacts, constraints, open_threads, uncertainties, vocabulary, turn). This is the scaffold.
2. **State extractor**: Smaller model (qwen3.5:4b) that reads scaffold + message + response and outputs JSON deltas (add/remove operations per field).
3. **Scaffold refresh**: Apply deltas to ConversationState, re-render as text, inject as sole context for next turn.
4. **Evidence boundary**: Transfer-entropy outputs in historical artifacts are invalid for claim use. The rigorous estimator falls back from a missing scaffold field to the response itself and is non-discriminating. See `docs/EXPERIMENTS.md` before describing results.

## Running experiments

Requires [Ollama](https://ollama.ai) with models pulled locally:
```bash
ollama pull qwen3.5:9b
ollama pull qwen3.5:4b
```

Run the LangQuant A/B experiment:
```bash
python conversation_ab_experiment.py
```

Run the scaffold amplification matrix:
```bash
python run_experiment.py
```

Analyze results:
```bash
python analyze_results.py
```

## Running tests

The unit tests mock the model calls and do not need Ollama or the
`experiments` extra. This is the CI command set:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
ruff check .
```

`tests/test_public_metadata_claims.py` is the claim guard: it fails if a public
surface carries a retracted result or if the version differs between
`pyproject.toml`, `CITATION.cff`, and `sbom.cdx.json`.

## Style

- Pure Python, minimal dependencies
- Results stored as JSONL for reproducibility
- Honest about limitations (see Caveats in README)
- Google-style docstrings
