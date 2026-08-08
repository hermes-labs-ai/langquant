# Contributing to LangQuant

Thanks for your interest! LangQuant is a research project by [Hermes Labs](https://hermes-labs.ai).

## Getting Started

```bash
git clone https://github.com/hermes-labs-ai/langquant.git
cd langquant
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,experiments]"
```

## Running Tests

```bash
python -m pytest -v
ruff check .
```

The unit tests use mocked HTTP calls and do not require Ollama. The experiment
runners do require a local [Ollama](https://ollama.com) service and model
downloads; read [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md) before running them
because they write under `results/`.

## Submitting Changes

1. Fork the repo and create a feature branch
2. Make your changes
3. Run `ruff check .` and fix any issues
4. Run `python -m pytest -v` and ensure tests pass
5. Open a PR with a clear description

## Code Style

- We use [ruff](https://docs.astral.sh/ruff/) for linting
- Keep functions focused and well-named
- Add docstrings for public functions

## Research Contributions

If you're extending the experiments (new models, new scaffold conditions, scale tests), please:
- Include raw JSONL results in `results/`
- Document methodology in your PR description
- Update LOG.md with findings

## Questions?

Open an issue or email via GitHub Issues on this repository.
