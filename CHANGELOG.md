# Changelog

## v0.0.8 (2026-03-28)

### Added
- Core LPCI prototype (`lpci.py`): SessionState, LPCISession, state extraction, scaffold refresh, interactive CLI
- A/B continuity test (`lpci_test.py`): 20 turns × 2 conditions, probes, scaffold evaluation, delta tracing
- Information-theoretic analysis (`analyze_results.py`): MI, KL divergence, transfer entropy via pyitlib + scipy
- Single-shot scaffold amplification harness (`run_experiment.py`): 4 models × 5 conditions × 12 tasks × 3 runs
- Result datasets: 40-row exploratory LPCI trace + 720-trial matrix run
- README with complete methodology, results, architecture, and honest caveats

### Historical experiment note
- The A/B trace exercised the no-transcript, refreshing-scaffold mechanism for 20 turns.
- Subsequent audit found that the continuity scorer is not uniform across conditions and that the transfer-entropy path is non-discriminating. Those outputs are preserved as experiment history, not validated behavioral or Markov-state claims; see `docs/EXPERIMENTS.md`.
- The compressed trace ended at 789 counted scaffold words versus 1,945 counted conversation words in that single run; it was not fixed-size.
