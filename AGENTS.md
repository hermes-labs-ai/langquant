# AGENTS.md — Agent Instructions for LangQuant

## What this project is

LangQuant is a research prototype exploring the LPCI (Linguistically Persistent Cognitive Interface) hypothesis: that a stateless LLM can maintain conversational continuity using only a refreshing structured language scaffold, with no conversation history in the main-model request. The no-transcript request boundary is directly inspectable in code. Current behavioral and information-flow artifacts are exploratory; do not present them as a validated recall lift or Markov-state result.

## Architecture

```
langquant/
├── lpci.py              # Core: SessionState, LPCISession, extraction, scaffold refresh, CLI
├── lpci_test.py         # A/B continuity test (20 turns × 2 conditions)
├── analyze_results.py   # Information-theoretic analysis (MI, KL, transfer entropy)
├── run_experiment.py    # Scaffold amplification matrix harness
├── results/             # JSONL experiment artifacts (continuity + matrix run)
├── tasks/               # Task definitions for matrix run
├── LOG.md               # Development log
└── TODO.md              # Future work
```

## Key concepts

1. **SessionState**: Typed dataclass with 12 fields (role, style, goal, subgoals, decisions, facts, artifacts, constraints, open_threads, uncertainties, vocabulary, turn). This is the scaffold.
2. **State extractor**: Smaller model (qwen3.5:4b) that reads scaffold + message + response and outputs JSON deltas (add/remove operations per field).
3. **Scaffold refresh**: Apply deltas to SessionState, re-render as text, inject as sole context for next turn.
4. **Evidence boundary**: Transfer-entropy outputs in historical artifacts are invalid for claim use. The rigorous estimator falls back from a missing scaffold field to the response itself and is non-discriminating. See `docs/EXPERIMENTS.md` before describing results.

## Running experiments

Requires [Ollama](https://ollama.ai) with models pulled locally:
```bash
ollama pull qwen3.5:9b
ollama pull qwen3.5:4b
```

Run the LPCI A/B test:
```bash
python lpci_test.py
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

```bash
pip install pytest pyitlib scipy numpy
pytest -v
```

## Style

- Pure Python, minimal dependencies
- Results stored as JSONL for reproducibility
- Honest about limitations (see Caveats in README)
- Google-style docstrings
