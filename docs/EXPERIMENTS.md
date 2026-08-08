# Experiment record and limitations

This document separates what can be inspected directly from what the current experiment artifacts can support. It preserves the exploratory measurements, including failed estimators, without promoting them into behavioral claims.

## Licensed conclusions

### Directly verified mechanism

The architecture is executable and source-verifiable:

- `LPCISession.chat()` renders `SessionState` and sends the main model a two-message payload: one system scaffold and the current user message.
- `LPCISession.history` is updated for the user interface after the call; it is not read to build the main-model payload.
- `extract_state_delta()` receives the current scaffold plus the latest user/assistant exchange and asks the state model for a JSON delta.
- `apply_delta()` updates the typed dataclass, and `show_state()`, `save_state()`, and `load_state()` expose the resulting state.

This supports: **the repository implements a no-transcript main-model path with typed, refreshed, inspectable state.** It does not by itself establish that the state is complete, faithful, fixed-size, or better than a summary.

### Committed run sizes

The repository contains three experiment artifacts:

| Artifact | Committed size | Scope |
|---|---:|---|
| `results/lpci_ab_test.jsonl` | 40 rows | one 20-turn `naked` trace and one 20-turn `compressed` trace |
| `results/lpci_rigorous_summary.jsonl` | 74 rows | completed-session summaries from the five-condition continuity run |
| `results/full_run_v1.jsonl` | 720 rows | separate single-turn scaffold-amplification matrix |

The rigorous runner defines 20 turns per session. Its 74 completed-session summaries therefore describe a 1,480-turn run size. The raw 1,480-row turn table is intentionally not committed in this checkout, so the current repository can inspect the session summaries but cannot independently recount every underlying turn or response.

The matrix manifest correctly declares 720 planned trials (4 models × 5 conditions × 12 tasks × 3 runs), the committed file has 720 rows, and `analyze_results.py` now reports that row count in its heading.

## Continuity run

### Design

`lpci_rigorous.py` defines:

- topics: `cooking`, `renovation`, and `startup`;
- main model: `qwen3.5:9b`;
- state/summary model: `qwen3.5:4b`;
- 20 scripted turns per session;
- five planned replications per topic/condition cell; and
- five context conditions.

The conditions are:

| Condition | Main-model context |
|---|---|
| `raw` | current user message only |
| `naive` | an under-200-word freeform summary of the latest 10 messages, plus the current user message |
| `naked` | the typed scaffold without the extra contrastive constraints/style |
| `compressed` | the typed scaffold with contrastive IS/NOT instructions |
| `clamped` | the contrastive scaffold after an additional approximately 500-word trimming routine |

The run completed 74 of 75 planned sessions. The absent cell is `startup` / `compressed` / replication 4; `compressed` therefore has n=14 while each other condition has n=15.

### Reported harness outputs

Recounting the committed summary produces:

| Condition | Completed sessions | Mean probe score | Mean final state words |
|---|---:|---:|---:|
| `naked` | 15 | 0.846 | 975 |
| `compressed` | 14 | 0.831 | 1,026 |
| `naive` | 15 | 0.792 | 109 |
| `clamped` | 15 | 0.759 | 490 |
| `raw` | 15 | 0.000 | 0 |

The 0.846 and 0.000 entries have n=15 completed sessions per arm. The number 74 is the whole-run completed-session count, not the sample size for that two-arm table contrast.

These are **harness outputs, not a licensed model-recall contrast**. The metric is not evaluated uniformly across conditions:

1. For LPCI conditions, `eval_probe()` searches the response for keywords drawn from the state extractor's current `decisions` list.
2. For `naive`, the runner constructs a synthetic evaluation state whose “decisions” are truncated prior assistant responses.
3. For `raw`, the runner supplies an empty `SessionState`. The evaluator consequently reports zero decision recall regardless of the response text.

The raw result is therefore an instrumentation floor. It cannot show that the model itself recalled nothing. The naive result should be reported normally as the observed 0.792 harness score—it is competitive with the typed-scaffold scores—but it is not an apples-to-apples ground-truth comparison.

The smallest corrective evaluation is a scorer built from one frozen, condition-independent answer key for every probe, followed by an independent rerun of the existing five conditions. The scorer should evaluate saved responses without consulting condition-generated state. That rerun is future work; it was not performed for this documentation change.

## State-size evidence

`SessionState.to_scaffold()` accepts a `token_budget`, but it estimates one token as four characters and mutates selected fields before re-rendering. It does not use the model tokenizer or assert the final encoded length. The default path should therefore be described as an approximate budget, not a hard fixed-token guarantee.

The `clamped` experiment adds a word-regex loop targeting 500 words. Its fallback can stop while retaining more state than requested, so it too should be treated as an experimental clamp rather than a general bounded-state proof.

The committed single-trace A/B file does show that the refreshed state remains inspectable across 20 turns. It ends at 517 counted words for `naked` and 789 for `compressed`. Because this is one trace per condition and both grow over the run, it does not establish constant-size behavior.

## Transfer-entropy history

Transfer entropy was explored twice and neither output is valid for claim use.

### Single-trace scalar pilot

`analyze_results.py` discretizes scaffold and response entropy values from the one A/B trace per condition. It has no session-level replication, and its scalar summaries are not a validated measure of conversational state sufficiency. Preserve it as exploratory analysis only.

### Rigorous-run estimator failure

The rigorous path is mechanically non-discriminating:

1. `run_session()` does not store a `scaffold_snapshot` field in each result row.
2. `compute_te_from_embeddings()` requests that missing field and falls back to the response text.
3. It therefore embeds the response as both the scaffold-side and response-side input.
4. The resulting similarities collapse the discretization, producing the same historical estimator output across every condition.

The committed summary retains the historical `te` field so the artifact is not silently rewritten. That field is **retracted and non-citable**. It is not evidence that the scaffold is a sufficient Markov state, and it should not appear in abstracts, badges, package metadata, or result headlines.

A corrected information-flow study would need distinct persisted scaffold/response representations, a preflight showing that the estimator separates positive and negative controls, session-level replication, and a frozen analysis before interpreting any condition contrast. This is separate from the shared-ground-truth recall rerun above.

## Additional limitations

- The study uses English scripted planning conversations and one Qwen model family.
- Sessions stop at 20 turns.
- The state extractor paraphrases free text; there is no schema validator, provenance link to source spans, or fidelity score.
- Probe scoring is lexical and can reward partial keyword overlap without semantic correctness.
- The naive summarizer sees the current user message while producing its summary, after which that same message is also sent as the user turn.
- The raw turn-level continuity data are absent from the committed repository, limiting independent audit to the 74 session summaries.
- Temperature is nonzero, and the current summary artifact does not carry a model digest, Ollama version, hardware record, or random seed.

## Inspect the committed artifacts without a model run

Count rows:

```bash
wc -l results/lpci_ab_test.jsonl \
  results/lpci_rigorous_summary.jsonl \
  results/full_run_v1.jsonl
```

Recompute the continuity table:

```bash
jq -s '
  group_by(.condition)
  | map({
      condition: .[0].condition,
      completed_sessions: length,
      mean_probe_score: (map(.mean_recall) | add / length),
      mean_final_state_words: (map(.final_scaffold_tokens) | add / length)
    })
' results/lpci_rigorous_summary.jsonl
```

Confirm the one missing cell:

```bash
jq -s '
  map(select(.condition == "compressed"))
  | map([.topic, .replication])
' results/lpci_rigorous_summary.jsonl
```

Inspect the main-model boundary:

```bash
sed -n '247,335p' lpci.py
```

`python analyze_results.py` recomputes the existing matrix and single-trace analyses. Its transfer-entropy section is historical diagnostic output only and should not be promoted into a claim.

## Re-running model experiments

The runners require local Ollama models and overwrite result paths. Preserve existing artifacts before an intentional rerun.

```bash
ollama pull qwen3.5:9b
ollama pull qwen3.5:4b
python lpci_test.py
python lpci_rigorous.py
python run_experiment.py
```

For a claim-bearing rerun, first fix and freeze the shared-ground-truth scorer, add a run manifest with exact model/runtime identifiers and seeds, and arrange independent execution. Do not rerun the existing scorer merely to produce another table with the same instrumentation problem.
