# LangQuant — Roadmap

Status (2026-09): the `langquant` package, the `langquant` CLI, and the offline
test suite are maintained. The experiment runners and the artifacts under
`results/` are a frozen research record; `docs/EXPERIMENTS.md` states what
they do and do not support. Items below that need a model run require a local
Ollama service and are not scheduled.

## Done or superseded

- [x] Five-condition continuity run: 74 of 75 planned sessions completed
      (`results/lpci_rigorous_summary.jsonl`). The probe scorer is not uniform
      across conditions, so its table is a harness output, not a recall claim.
- [x] Transfer-entropy post-processing (`postprocess_te.py`): the estimator is
      non-discriminating and its outputs are retracted and non-citable. Do not
      rerun it for claim use.

## Next claim-bearing experiment (needs local Ollama)

- [ ] Frozen, condition-independent probe answer key and a scorer that grades
      saved responses without consulting condition-generated state.
- [ ] Independent rerun of the five conditions with a run manifest: model
      digests, Ollama version, hardware, seeds.
- [ ] Hard-clamped budget from turn 1 (a true fixed-size scaffold), instead of
      a ceiling trim that only fires late in the session.
- [ ] Integer-pointer extraction: the state model returns indices into numbered
      statements and the scaffold stores verbatim text, so extraction cannot
      paraphrase or invent content.
- [ ] Corrected information-flow study: distinct persisted scaffold/response
      representations and a positive/negative control preflight before any
      condition contrast is interpreted.

## Research (unscheduled)

- [ ] Validate behavioral complexity metric against human judgment
- [ ] Per-token ablation study (LLMLingua-style)
- [ ] Scaling law: compression ratio vs model size
- [ ] Cross-architecture comparison: deepseek-r1:8b, gemma3:4b, mistral:7b

## Infrastructure

- [ ] Inspect AI evals for behavioral complexity validation
- [ ] Analysis/reporting script over a corrected-scorer result set
