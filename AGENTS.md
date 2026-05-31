# AGENTS.md — Agent Instructions for LangQuant

## What this project is

LangQuant is a research prototype exploring the LPCI (Linguistically Persistent Cognitive Interface) hypothesis: that a stateless LLM can maintain conversational coherence using only a refreshing structured language scaffold, no conversation history. In a single A/B run (n=1 per condition, 20 turns), the model held coherence under this setup and transfer entropy from history to the next turn dropped substantially once conditioned on the scaffold (0.608 naked vs 0.085 compressed) — a large reduction, not zero.

## Architecture

```
langquant/
├── lpci.py              # Core: SessionState, LPCISession, extraction, scaffold refresh, CLI
├── lpci_test.py         # A/B continuity test (20 turns × 2 conditions)
├── analyze_results.py   # Information-theoretic analysis (MI, KL, transfer entropy)
├── run_experiment.py    # Scaffold amplification matrix harness
├── results/             # JSONL data files (proof + matrix run)
├── tasks/               # Task definitions for matrix run
├── LOG.md               # Development log
└── TODO.md              # Future work
```

## Key concepts

1. **SessionState**: Typed dataclass with 12 fields (role, style, goal, subgoals, decisions, facts, artifacts, constraints, open_threads, uncertainties, vocabulary, turn). This is the scaffold.
2. **State extractor**: Smaller model (qwen3.5:4b) that reads scaffold + message + response and outputs JSON deltas (add/remove operations per field).
3. **Scaffold refresh**: Apply deltas to SessionState, re-render as text, inject as sole context for next turn.
4. **Transfer entropy drop**: For the compressed scaffold, conditioning on the current scaffold left little measurable information flow from prior turns (TE 0.608 naked vs 0.085 compressed) — consistent with the scaffold approximating a Markov state, though this is a single A/B observation, not a proof.

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
