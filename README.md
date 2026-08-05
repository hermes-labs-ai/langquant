<p align="center">
  <a href="https://github.com/hermes-labs-ai/langquant"><img src="https://img.shields.io/github/stars/hermes-labs-ai/langquant" alt="GitHub stars"></a>
  <a href="https://pypi.org/project/langquant/"><img src="https://img.shields.io/pypi/v/langquant?color=blue" alt="PyPI"></a>
  <a href="https://github.com/hermes-labs-ai/langquant/blob/main/LICENSE"><img src="https://img.shields.io/github/license/hermes-labs-ai/langquant" alt="License"></a>
  <a href="https://github.com/hermes-labs-ai/langquant/actions/workflows/ci.yml"><img src="https://github.com/hermes-labs-ai/langquant/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

# langquant

> Run a multi-turn conversation against a local language model that never sees any prior messages. Each turn it reads a small, typed, refreshing scaffold of the session state plus the current user message. The rendered scaffold text is the state.

`langquant` is a research prototype from [Hermes Labs](https://hermes-labs.ai). It shows that a stateless local model can hold a 20-turn conversation while receiving zero conversation history, by relying on a 12-field structured scaffold that a smaller model rewrites after every turn. The repo ships the runnable system, the experiments, and the JSONL result files.

## What problem this solves

Standard LLM chat sends the model a growing transcript:

```
Turn 1:  [system prompt] + [message 1]
Turn 2:  [system prompt] + [message 1] + [response 1] + [message 2]
Turn N:  [system prompt] + [entire history so far] + [message N]   (grows without bound)
```

Context grows linearly with turn count. Two problems follow.

1. **Lost in the middle.** Long contexts degrade recall and attention placement, even when the relevant span fits in the window ([Liu et al. 2023](https://arxiv.org/abs/2307.03172)).
2. **Context rot.** Empirically, accuracy on long contexts decays well before the nominal token limit, across frontier models ([Chroma, 2025](https://research.trychroma.com/context-rot)).

The default fix is a bigger context window (128k, 200k, 1M). That moves the ceiling without changing the shape of the problem. Effective practice has shifted toward **context engineering**: deciding what to put in the window at each step rather than letting the transcript accumulate ([Karpathy, 2025](https://x.com/karpathy/status/1937902205765607626); [Anthropic, 2025](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)). The model is also stateless across calls anyway ([Atlan, 2026](https://atlan.com/know/are-llms-stateless/)); the transcript is being re-fed to a fresh process each turn.

`langquant` is a narrow instance of context engineering: send the model no history at all, and put the entire non-message context into a fixed-shape, typed scaffold that a smaller model rewrites after every turn.

```
Every turn:  [scaffold: K tokens, refreshed] + [current message]
```

The scaffold does not accumulate a transcript. It is re-derived from the prior scaffold and the latest exchange. Turn 2 and turn 20 are structurally identical from the model's point of view.

## What this repo demonstrates

In a rigorous run across 3 unrelated topics (cooking, renovation, startup), 5 conditions, and 5 replications per cell (74 sessions, 1,480 turns), a stateless `qwen3.5:9b` reading only the 12-field scaffold and the current user message held a mean probe recall of **0.83** at 20 turns, against **0.00** for the no-scaffold control. Data: [`results/lpci_rigorous_summary.jsonl`](results/lpci_rigorous_summary.jsonl).

Per-condition mean recall at turn 20:

| Condition | n | Mean recall | What it is |
|---|---|---|---|
| `naked` | 15 | 0.846 | Empty constraint/style; full 12-field scaffold |
| `compressed` | 14 | 0.831 | Contrastive IS/NOT markers in constraints/style |
| `naive` | 15 | 0.792 | Last-N message summary (baseline; not LPCI) |
| `clamped` | 15 | 0.759 | Hard fixed token budget on scaffold |
| `raw` | 15 | 0.000 | No scaffold, no history (falsifiability anchor) |

The `raw` condition is the floor: a stateless model with no scaffold and no history cannot answer probes about prior turns. The four scaffolded conditions all hold recall in the 0.76 to 0.85 band. The naive last-N summary baseline (0.79) is competitive with the LPCI scaffolds on this metric; we address this directly below.

## Mechanism

```
   User message
        |
        v
[scaffold: K tokens] + [current message]      <- the only thing the main model sees
        |
        v
   Main model (qwen3.5:9b, stateless)
        |
        v
   Response
        |
        v
   State extractor (qwen3.5:4b)  reads [scaffold + user message + response]
        |
        v
   JSON delta -> apply to typed SessionState -> re-render scaffold for next turn
```

The main model is a pure function. The scaffold is the program. The output of one pass feeds the construction of the next.

### Scaffold schema

`SessionState` is a typed dataclass with one section per field:

| Field | Meaning |
|---|---|
| `role` | who the model is in this session |
| `style` | communication constraints |
| `goal` / `subgoals` | current objective and active sub-tasks |
| `decisions` | things decided (treated as irreversible) |
| `facts` | established truths for the session |
| `artifacts` | things produced (files, code, results) |
| `constraints` | hard boundaries, rendered as NOTs |
| `open_threads` | unresolved questions |
| `uncertainties` | things flagged as unsure |
| `vocabulary` | domain terms (term to meaning) |
| `turn` | counter |

## The combination has a name: LPCI

The specific combination shown above (no conversation history sent + a 12-field typed scaffold + a smaller model rewriting the scaffold each turn) is what we call **LPCI**.

> **LPCI (Linguistically Persistent Cognitive Interface)** is a way to give a stateless language model continuity without feeding it conversation history. Each turn, the model sees only a fixed-budget, typed scaffold of the session state (role, style, goals, decisions, facts, constraints, vocabulary, open questions) plus the current message. A smaller model rewrites the scaffold after every turn. The conversation history never reaches the model: the rendered scaffold text is the state. LPCI was formulated by Rolando Bosch at Hermes Labs in 2025.

LPCI is a flag on the *combination*, not on context engineering, summarization-based memory, or externalized state. Each of those is well-established prior art. What is distinctive is sending the model **no transcript at all** plus a **typed, inspectable scaffold** with stable field semantics.

## How LPCI relates to other work

This is a crowded space. The table below is a structural comparison, not a benchmark.

| System | History sent to model | Schema | Persistent store | Fine-tune required | Retrieval required |
|---|---|---|---|---|---|
| Naive transcript | full transcript | none | no | no | no |
| Naive last-N summary | summary + last N | freeform text | no | no | no |
| Context engineering ([Karpathy 2025](https://x.com/karpathy/status/1937902205765607626); [Anthropic 2025](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)) | curated subset | unconstrained | optional | no | optional |
| MemGPT / Letta ([Packer 2023](https://arxiv.org/abs/2310.08560)) | recent buffer + retrieved memories | tiered (working / archival) | yes | no | yes |
| Gist tokens ([Mu 2023](https://arxiv.org/abs/2304.08467)) | gist embedding | learned latent | no | yes (model fine-tune) | no |
| AutoCompressors ([Chevalier 2023](https://arxiv.org/abs/2305.14788)) | summary vectors | learned latent | no | yes (model fine-tune) | no |
| Memori ([2026](https://arxiv.org/abs/2603.19935)) | retrieved memories | structured records | yes | no | yes |
| **LPCI (this repo)** | **none** | **typed 12-field scaffold** | **no** | **no** | **no** |

Honest overlaps:

- Like MemGPT, LPCI separates working state from a transcript, and refreshes that state with a model.
- Like context engineering broadly, LPCI decides what goes in the window each turn; LPCI is one narrow choice inside that practice (zero history, typed schema, smaller model rewrites).
- Unlike gist tokens or AutoCompressors, LPCI requires no model fine-tuning and operates at the language level (inspectable text), not in learned latent space.
- Unlike retrieval-augmented memory, LPCI does not maintain a persistent store or run a retriever; the state is the current scaffold.

## Install

```bash
pip install langquant
```

`langquant` runs against a local [Ollama](https://ollama.com) instance. Pull the two models used by default:

```bash
ollama pull qwen3.5:9b   # main reasoning model
ollama pull qwen3.5:4b   # state-extractor model
```

## Usage

Interactive session from the command line:

```bash
python lpci.py
```

Commands inside the session: `/state` (show the scaffold the model sees), `/history` (show the user-facing transcript), `/save <path>`, `/quit`.

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

# Model sees ONLY the rendered scaffold + this message. No transcript.
reply = session.chat("We decided to use a token bucket. Constraint: no Redis.")
print(reply)

# Inspect what the model actually saw this turn:
print(session.show_state())

# Persist / restore the entire session state as JSON:
session.save_state("state.json")
session.load_state("state.json")
```

After each `chat()` call, the state-extractor model emits a JSON delta (new decisions, facts, constraints, vocabulary, resolved threads) that updates the `SessionState`, which re-renders to the scaffold for the next turn.

## Reproducibility

```bash
python lpci_test.py        # 20-turn A/B continuity test -> results/lpci_ab_test.jsonl
python analyze_results.py  # information-theoretic analysis (MI, KL, transfer entropy)
python lpci_rigorous.py    # 3 topics x 5 conditions x 5 replications -> results/lpci_rigorous_summary.jsonl
python postprocess_te.py   # batch transfer-entropy computation over the rigorous run
```

Result files committed to the repo:

| File | Description |
|---|---|
| `results/lpci_ab_test.jsonl` | 20-turn A/B: full scaffold snapshots, delta traces, probe evaluations |
| `results/lpci_rigorous_summary.jsonl` | 74-session rigorous-run summaries (the lead claim) |
| `results/full_run_v1.jsonl` | 619-trial scaffold-amplification matrix (companion experiment) |

## Demonstrated findings

1. **Zero history sent to the model.** Structural property of the code; verifiable by inspecting `LPCISession.chat()` in `lpci.py`.
2. **Recall holds across 20 turns.** Mean recall 0.83 (compressed, n=14) vs 0.00 (no-scaffold control, n=15) — see the per-condition table above. 74 is the total session count across all 5 conditions and 3 topics in the full study, not the paired n for this specific contrast.
3. **Recall parity with a naive last-N summary baseline.** Naive summary scored 0.79, within the same band as the LPCI conditions. The contribution here is the **structural property** (zero history, typed inspectable state, auditable field semantics), not a recall ceiling above naive summarization.
4. **Compression curve in the 20-turn A/B.** Scaffold grew at ~23 tokens/turn against conversation at ~97 tokens/turn; at turn 20, scaffold was 789 tokens against 1,945 tokens of equivalent conversation. Note: the `compressed` condition was *not* held to a hard fixed budget. See caveats.

## What this does NOT claim

These are the things we explicitly are not claiming, so they cannot be mis-cited.

- **Not** that the scaffold is a complete Markov state for the conversation. The information-theoretic question (does knowing prior scaffolds add information beyond the current one?) is the motivation for the work, not a settled result. See the methodology section below.
- **Not** that LPCI beats naive last-N summarization on recall. In the rigorous run, Mann-Whitney between `naked` and `compressed` gave p = 1.0 (no separation); the `clamped` LPCI variant scored 0.759 against the naive summary baseline at 0.792, at roughly 1/4 the tokens. Naive summary is competitive on recall. The brand of the contribution is the structural property, not a recall ceiling.
- **Not** fixed-budget operation in the headline run. The `compressed` scaffold grew from 343 tokens at turn 1 to 789 tokens at turn 20; only the `clamped` condition holds a hard ceiling.
- **Not** validated beyond 20 turns. The longest tested session is 20 turns.
- **Not** validated across models. Only `qwen3.5` family was tested (4b extractor, 9b main). Cross-model transfer is open work.
- **Not** production-ready. This is a research prototype; the state extractor paraphrases rather than copying verbatim, and classification drift was observed across conditions (see methodology).

## Methodology and open questions

### The TE estimator collapsed; that is not evidence of Markov state

Two transfer-entropy measurements live in this repo:

1. **Single A/B run, scalar Shannon estimator** (`analyze_results.py`, n=1 per condition, 20 turns). Reported TE = 0.608 bits for `naked` and **0.085 bits for `compressed`** [LINT:RETRACTED-HISTORICAL] — retracted, non-citable single small-N pilot. Taken alone, that is suggestive but n=1.

2. **Rigorous run, embedding-cosine binning estimator** (`postprocess_te.py`, 74 sessions). Reported **TE = 0.0 for every condition, including the raw baseline** [LINT:RETRACTED-HISTORICAL] — retracted and withdrawn as non-informative, non-citable. Mann-Whitney `naked` vs `compressed` p = 1.0.

The second number is **estimator failure, not evidence of Markov state**. Inspecting `lpci_rigorous.py:556-561`, the cosine similarity between consecutive scaffolds had near-zero standard deviation, which caused the discretization step to collapse to a single bin. An estimator that returns 0 on the raw zero-context control (which is non-Markov by construction) is not discriminating between conditions. It is degenerate.

We are not claiming the scaffold is a Markov state. The Markov-state framing is the **research target**: the next experiment is to build a discriminating estimator that cleanly separates the no-scaffold baseline from the scaffold conditions. A V-information style estimator may be a cleaner formulation ([ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/file/a9b0e4e205bdf232da9f74bfb9469539-Paper-Conference.pdf)), since it does not require histogram discretization on near-collinear vectors.

### Naive-summary parity is a finding, not a problem

The rigorous run surfaced something brand-aligned with how Hermes Labs publishes: the naive last-N summary baseline (0.792) was within noise of the LPCI conditions (0.831 compressed, 0.846 naked, 0.759 clamped) on recall. We report this directly. The reason this does not retract LPCI is that the contribution claimed here is structural, not recall-relative:

- The model receives **zero conversation history** (auditable in code).
- The state is a **typed, inspectable 12-field object**, not a freeform paragraph.
- Field semantics are stable across turns (`decisions` always means "treated as irreversible"; `constraints` always renders as NOT clauses).
- The compression curve widens with turn count; the recall-band parity with naive summary is established at 20 turns and may not extend.

We treat this null-result as part of the work, in line with our public stance on null-result honesty ([why-your-ai-lies](https://hermes-labs.ai/archive/why-your-ai-lies-when-the-data-is)).

### Classification drift in the state extractor

Across A/B conditions, the same conversation produced 71 facts and 4 decisions under one framing, and 3 facts and 23 decisions under another. The total information captured is similar; the bucket assignment is not. This is the state extractor paraphrasing and reclassifying. The likely fix is an **index-based extractor** that emits integer pointers into verbatim turn segments rather than generated text; this is the same fidelity pattern Hermes Labs uses in [cogito-ergo](https://github.com/roli-lpci/cogito-ergo).

### Open questions

- Hard-clamped budget at scale: exactly K tokens at every turn through 100+ turns.
- A discriminating TE (or V-information) estimator that separates `raw` from `compressed`.
- Cross-model scaffold transfer: does a scaffold built by one model work injected into another?
- Cross-language scaffolds: only English tested.

## Companion experiment: scaffold amplification (619 trials)

Separate from LPCI, `run_experiment.py` ran a single-shot study of 5 scaffold conditions across 4 model sizes (`qwen3.5` 0.8b/2b/4b/9b) on 12 tasks (`results/full_run_v1.jsonl`):

- Scaffold condition significantly affects score (Kruskal-Wallis p = 0.0007), but **only for small models** (0.8b p = 0.0008, 2b p = 0.005, 4b p = 0.92, 9b p = 0.94).
- Condition explained 4.2% of score variation; model size explained 4.7%.
- Dense compressed-grammar scaffolds *break* small models (0.8b dropped 0.78 to 0.40), consistent with a "model needs capacity to decompress a dense scaffold" threshold.

This is a separate measurement from LPCI continuity and is reported separately in the result file.

## FAQ

**What does LPCI stand for?**
Linguistically Persistent Cognitive Interface. Linguistically: the medium is language, not tensors. Persistent: it survives across the stateless inference boundary. Cognitive: it steers attention and reshapes behavior, not just stores text. Interface: it sits between the session and the stateless model.

**Does the model really see no conversation history?**
Yes. Each turn the main model receives a system message containing the rendered scaffold and a user message containing the current input, and nothing else. The transcript is kept only for the human-facing UI (`show_history()`), never sent to the model. Auditable in `lpci.py`.

**Is TE = 0 proven?** [LINT:RETRACTED-HISTORICAL] — withdrawn, non-citable claim.
No. Two estimators were run. The n=1 scalar estimator gave 0.085 bits for the compressed condition [LINT:RETRACTED-HISTORICAL] — retracted, non-citable single small-N pilot. The rigorous embedding-cosine estimator collapsed to TE = 0 for every condition including the raw no-context baseline [LINT:RETRACTED-HISTORICAL] — retracted, non-citable, degenerate and non-discriminating, which is non-Markov by construction; that result is degenerate, not informative. The Markov-state framing is a research target, not a result.

**Does LPCI beat naive summarisation?**
Not on recall, in this run. In the rigorous 74-session experiment, a naive last-N summary baseline scored 0.792, within noise of LPCI conditions (0.831 compressed; 0.759 clamped at ~1/4 the tokens). The contribution claimed here is structural (zero history, typed inspectable state, auditable field semantics), not a recall ceiling above naive summarization.

**Can I use this as a production memory layer?**
Not as-is. This is a research prototype. The state extractor paraphrases, classification drift was observed, scale beyond 20 turns is untested, and only one model family was tested.

**Who created LPCI?**
Rolando Bosch at Hermes Labs, formulated in 2025. Hermes Labs is the AI audit infrastructure company that maintains this repo.

## Citations

```bibtex
@misc{langquant2026,
  author = {Bosch, Rolando},
  title  = {langquant: the Linguistically Persistent Cognitive Interface (LPCI) reference implementation},
  year   = {2026},
  url    = {https://github.com/hermes-labs-ai/langquant},
  note   = {Hermes Labs}
}
```

A `CITATION.cff` file is included in the repo root for citation tooling.

External work referenced above:

- Liu, N. F. et al. (2023). *Lost in the Middle: How Language Models Use Long Contexts.* https://arxiv.org/abs/2307.03172
- Chroma Research (2025). *Context Rot.* https://research.trychroma.com/context-rot
- Karpathy, A. (2025). On context engineering. https://x.com/karpathy/status/1937902205765607626
- Anthropic (2025). *Effective context engineering for AI agents.* https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Atlan (2026). *Are LLMs Stateless?* https://atlan.com/know/are-llms-stateless/
- Packer, C. et al. (2023). *MemGPT: Towards LLMs as Operating Systems.* https://arxiv.org/abs/2310.08560
- Mu, J. et al. (2023). *Learning to Compress Prompts with Gist Tokens.* https://arxiv.org/abs/2304.08467
- Chevalier, A. et al. (2023). *Adapting Language Models to Compress Contexts (AutoCompressors).* https://arxiv.org/abs/2305.14788
- Memori / StructMemEval (2026). https://arxiv.org/abs/2603.19935
- V-information for LLMs (ICLR 2025). https://proceedings.iclr.cc/paper_files/paper/2025/file/a9b0e4e205bdf232da9f74bfb9469539-Paper-Conference.pdf

Hermes Labs methodology lineage:

- *Taxonomy of Epistemic Failure Modes in LLMs.* https://doi.org/10.5281/zenodo.19042469
- *The Asymmetric Burden of Proof in AI Evaluation.* https://doi.org/10.5281/zenodo.18867694
- *Why your AI lies when the data is honest.* https://hermes-labs.ai/archive/why-your-ai-lies-when-the-data-is

## About Hermes Labs

[Hermes Labs](https://hermes-labs.ai) is the AI audit infrastructure company behind langquant. We build EU AI Act compliance tooling, ISO 42001 evidence bundles, and agent-level risk testing for teams shipping AI into regulated environments. Everything we release here is Apache-2.0, free, no SaaS tier. The thesis behind this stance is laid out in [tools-are-the-byproduct](https://hermes-labs.ai/archive/tools-are-the-byproduct-why-hermes): we sell audit work; the tools we open-source are the ones we already use internally. The longer-horizon framing is in [ambient-assurance](https://hermes-labs.ai/archive/ambient-assurance).

- Site: https://hermes-labs.ai
- Contact: roli@hermes-labs.ai
- Writing: https://rolibosch.substack.com
- Video: https://youtube.com/@rolifromhermes
- Full OSS stack: https://github.com/hermes-labs-ai

If `langquant` is useful to you, [star the repo](https://github.com/hermes-labs-ai/langquant) so other people can find it.

## License

Apache 2.0.

---

*Hermes Labs, 2026.*
