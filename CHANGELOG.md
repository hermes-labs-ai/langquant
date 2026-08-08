# Changelog

## v0.1.0 (2026-08-08)

### Added

- A real `langquant` Python package and console command.
- Public `ConversationState` and `LangQuantSession` APIs.
- PyPI-first installation, isolated-wheel smoke checks, and release validation.
- Tests for approximate budget enforcement, multi-item delta removal, and state
  save/load round trips.
- A security reporting policy and repository-local verification command.

### Changed

- Reframed LangQuant as experimental software for holding conversational state
  outside the chat transcript.
- Renamed the UI-only `history` surface and command to `transcript` and
  `/transcript`.
- Renamed current experiment runners while preserving historical result
  filenames and bytes for provenance.

### Fixed

- The previously published `0.0.8` wheel contained metadata but no importable
  package or console command.
- Approximate scaffold budgets now enforce their documented character bound
  without mutating session state during rendering.
- Multiple removal operations apply cumulatively, and repeated additions are
  deduplicated.
- State-update JSON parsing now accepts one object without greedily consuming
  trailing text.

## v0.0.8 (2026-03-28)

### Added
- Core LangQuant prototype: explicit conversation state, state extraction, scaffold refresh, interactive CLI
- A/B continuity experiment: 20 turns × 2 conditions, probes, scaffold evaluation, delta tracing
- Information-theoretic analysis (`analyze_results.py`): MI, KL divergence, transfer entropy via pyitlib + scipy
- Single-shot scaffold amplification harness (`run_experiment.py`): 4 models × 5 conditions × 12 tasks × 3 runs
- Result datasets: 40-row exploratory LangQuant trace + 720-trial matrix run
- README with complete methodology, results, architecture, and honest caveats

### Historical experiment note
- The A/B trace exercised the no-transcript, refreshing-scaffold mechanism for 20 turns.
- Subsequent audit found that the continuity scorer is not uniform across conditions and that the transfer-entropy path is non-discriminating. Those outputs are preserved as experiment history, not validated behavioral or Markov-state claims; see `docs/EXPERIMENTS.md`.
- The compressed trace ended at 789 counted scaffold words versus 1,945 counted conversation words in that single run; it was not fixed-size.
