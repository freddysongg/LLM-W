# References

This file is the canonical bibliography for LLM-W. Every design decision in the codebase traces back to a named source listed here. R-IDs are stable identifiers referenced from README, EVAL.md, BENCHMARKS.md, rubric YAMLs, and inline code comments. When adding a new research basis to a rubric or design doc, extend the table below — never introduce an R-ID that isn't defined here.

R2 is intentionally absent: it previously referred to Verga et al. (PoLL, cross-family panel judging), which was dropped in the v4 plan.

## R-ID index

| ID | Source | Used for |
|---|---|---|
| R1 | Liu et al. 2023 — G-Eval | Chain-of-thought scoring in Tier 2 judge |
| R3 | Hamel Husain — Critique Shadowing | Binary pass/fail labeling; TPR/TNR calibration |
| R4 | Friel & Sanyal 2023 — ChainPoll | N-call majority vote for hallucination detection |
| R5 | Sirdeshmukh et al. 2025 — MultiChallenge | Binary rubric questions achieve ~93% alignment with human eval |
| R6 | Bai et al. 2022 — Constitutional AI | Safety rubric dimension design |
| R7 | OpenAI Structured Outputs + `instructor` | Pydantic-validated judge outputs; reasoning-before-score ordering |
| R8 | Confident AI — DeepEval | Reference for 60+ metric patterns |
| R9 | Promptfoo docs | CI/CD patterns; `llm-rubric` assertion; PR gate workflow |
| R10 | Langfuse docs | Production trace → dataset → regression flywheel |
| R11 | Amazon AGI 2025 — Nova technical report | Additive-binary rubric criteria improve evaluation |
| R12 | OpenAI Moderation (`omni-moderation-latest`) | Tier-1 safety prescreen |
| R13 | PDF-1 reference architecture (internal) | Two-tier structure (adapted; Tier 3 panel dropped) |

## Citations

### R1 — G-Eval

**Citation:** Liu, Y., Iter, D., Xu, Y., Wang, S., Xu, R., & Zhu, C. (2023). *G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment*. EMNLP 2023.

**URL:** https://arxiv.org/abs/2303.16634

**Used in LLM-W:** Tier-2 judge prompt construction in `backend/app/services/eval/geval.py` (auto-generated eval steps from rubric criteria, chain-of-thought reasoning ordered before the verdict token). Referenced by `rubrics/faithfulness.yaml` and `rubrics/instruction_following.yaml` via `research_basis: [R1, ...]`.

**Key limitation / caveat:** G-Eval's reported 0.514 Spearman correlation vs human was measured on summarization tasks with Likert-scale outputs; LLM-W uses binary pass/fail, so the Spearman number does not transfer directly. We rely on the CoT-step generation methodology, not the reported alignment figure.

### R3 — Critique Shadowing

**Citation:** Husain, H. (2024). *Creating a LLM-as-a-Judge That Drives Business Results*.

**URL:** https://hamel.dev/blog/posts/llm-judge/

**Used in LLM-W:** Calibration methodology in `EVAL.md` (§ Calibration Methodology) and `eval/calibration/` tooling — 100 hand-labeled pass/fail examples with one-line critiques, deterministic hash-split into 50 few-shot and 50 held-out, TPR/TNR thresholding. Referenced by `rubrics/faithfulness.yaml` and `rubrics/instruction_following.yaml`.

**Key limitation / caveat:** Critique Shadowing is a practitioner blog post, not peer-reviewed. The n=50 held-out split is small; the 95% Clopper–Pearson CI on TPR=0.90 at n=50 is roughly [0.78, 0.97]. Every claim downstream avoids quoting precise percentages.

### R4 — ChainPoll

**Citation:** Friel, R., & Sanyal, A. (2023). *Chainpoll: A High Efficacy Method for LLM Hallucination Detection*. Galileo AI.

**URL:** https://arxiv.org/abs/2310.18344

**Note on attribution:** The v4 plan attributes R4 to "DataDog — ChainPoll". The primary source is the Galileo AI paper by Friel & Sanyal; DataDog engineering material later popularized the same majority-vote pattern under the ChainPoll name. Both trace to the same technique.

**Used in LLM-W:** `backend/app/services/eval/chainpoll.py` — wraps an `OpenAIJudge` and fires N=3 calls at temperature 0.3, majority-votes the verdict, preserves all reasoning traces. Used exclusively by `rubrics/hallucination.yaml`.

**Key limitation / caveat:** ChainPoll's reported gains are specific to hallucination detection with a single judge model sampled at nonzero temperature. The technique is not a substitute for cross-family panel judging (which LLM-W explicitly declines to ship).

### R5 — MultiChallenge

**Citation:** Sirdeshmukh, V., Deshpande, K., Mols, J., et al. (2025). *MultiChallenge: A Realistic Multi-Turn Conversation Evaluation Benchmark Challenging to Frontier LLMs*. ACL 2025.

**URL:** https://arxiv.org/abs/2501.17399

**Used in LLM-W:** Justifies the binary-rubric design in `rubrics/instruction_following.yaml` (R5 is listed in its `research_basis`). The ~93% binary-question alignment with human evaluation is cited in `EVAL.md` as the empirical basis for preferring binary pass/fail over Likert.

**Key limitation / caveat:** MultiChallenge's alignment figure is measured on a multi-turn instruction-following benchmark with frontier LLMs as judges. LLM-W's judge is `gpt-4o-mini` by default, so absolute alignment will be lower than the paper's frontier-model numbers.

### R6 — Constitutional AI

**Citation:** Bai, Y., Kadavath, S., Kundu, S., et al. (2022). *Constitutional AI: Harmlessness from AI Feedback*. Anthropic.

**URL:** https://arxiv.org/abs/2212.08073

**Used in LLM-W:** Three safety dimensions (helpful, honest, harmless) encoded as binary criteria in `rubrics/safety.yaml` Tier-2 section. Referenced via `research_basis: [R6, R12]`.

**Key limitation / caveat:** Constitutional AI is an RLHF training methodology; LLM-W only adopts its dimensional taxonomy for evaluation, not the training loop itself.

### R7 — OpenAI Structured Outputs + `instructor`

**Citation:** OpenAI (2024). *Structured Outputs* (platform feature, August 2024 release). Liu, J. et al. *instructor* Python library (Pydantic-validated LLM function calling).

**URLs:**
- https://platform.openai.com/docs/guides/structured-outputs
- https://github.com/567-labs/instructor

**Used in LLM-W:** `backend/app/services/eval/openai_judge.py` uses `instructor` to parse judge responses into the `Score` Pydantic model from `backend/app/schemas/eval.py`. The schema orders `reasoning` before `verdict` so chain-of-thought tokens are generated first (per both R1 and Critique Shadowing).

**Key limitation / caveat:** Structured Outputs is OpenAI-specific; switching to a non-OpenAI judge would require either a `response_format` shim or dropping schema enforcement. The two OpenAI platform docs URLs above may 403 automated fetches — they are canonical and resolve normally in a browser.

### R8 — DeepEval

**Citation:** Confident AI. *DeepEval* — open-source LLM evaluation framework.

**URL:** https://github.com/confident-ai/deepeval

**Used in LLM-W:** Reference implementation surveyed during rubric design (not a runtime dependency). Patterns for metric definition, multi-criteria scoring, and test-case structuring informed `backend/app/schemas/rubric.py` and the YAML rubric layout under `rubrics/`.

**Key limitation / caveat:** LLM-W does not import or run DeepEval at runtime. Copying their metric surface wholesale would expand scope beyond v4.

### R9 — Promptfoo

**Citation:** Promptfoo. *Promptfoo documentation* — LLM evaluation CLI and CI integration.

**URL:** https://www.promptfoo.dev/docs/

**Used in LLM-W:** CI gate design for `.github/workflows/eval-gate.yml` (planned) and the `llmw eval` CLI entry point documented in `EVAL.md` § CI Integration. The `llm-rubric` assertion pattern and PR-gate threshold model are adapted from Promptfoo.

**Key limitation / caveat:** Promptfoo is a separate tool with its own config format; LLM-W reimplements the gate logic against its own SQLite-backed eval history rather than delegating to Promptfoo.

### R10 — Langfuse

**Citation:** Langfuse. *Langfuse documentation* — LLM observability and dataset management.

**URL:** https://langfuse.com/docs

**Used in LLM-W:** Feedback-loop design in `EVAL.md` (failing case → dataset → regression suite). The production-trace-to-dataset flywheel shape is adapted to LLM-W's append-only `eval_calls` table.

**Key limitation / caveat:** Langfuse is not a runtime dependency. LLM-W's event bus and SQLite eval tables play the role their hosted platform plays; fidelity is lower (no distributed tracing, no hosted UI).

### R11 — Amazon Nova

**Citation:** Amazon AGI (2025). *The Amazon Nova Family of Models: Technical Report and Model Card*.

**URL:** https://arxiv.org/abs/2506.12103

**Used in LLM-W:** Additive-binary rubric design in `backend/app/schemas/rubric.py` (`Criterion` class docstring cites R11) and every rubric under `rubrics/` — each criterion is an atomic binary check contributing additive points, no Likert scales, no holistic ratings.

**Key limitation / caveat:** The Nova technical report covers a broad family of models; the specific claim that additive-binary rubrics outperform holistic Likert by ~49% appears in Amazon's evaluation section and is not a general result. LLM-W adopts the rubric shape, not the magnitude claim.

### R12 — OpenAI Moderation

**Citation:** OpenAI. *Moderation API* (`omni-moderation-latest`).

**URL:** https://platform.openai.com/docs/guides/moderation

**Used in LLM-W:** Tier-1 safety prescreen in the safety rubric — any case flagged by Moderation short-circuits to `fail` without invoking the Tier-2 judge. Referenced by `rubrics/safety.yaml` via `research_basis: [R6, R12]`.

**Key limitation / caveat:** The Moderation API is OpenAI-hosted and subject to their classifier drift. LLM-W pins to `omni-moderation-latest` knowingly accepting drift over time; the eval-replay mechanism's `response_hash` will detect behavior changes across historical runs. The platform-docs URL may 403 automated fetches but resolves in a browser.

### R13 — PDF-1 reference architecture

**Citation:** Internal reference architecture document (LLM-W design predecessor). Not publicly citable.

**URL:** n/a — source-of-truth lives in the project's private `docs/` material and in-team discussion.

**Used in LLM-W:** The two-tier deterministic-then-judge structure (with a third panel tier present in PDF-1 and dropped in v4) is the scaffolding on which `EVAL.md` § Architecture is built.

**Key limitation / caveat:** No external URL; future contributors cannot verify this citation independently. When R13 influences a new design decision, prefer citing the adapted public source (R1, R4, R11) over R13 alone.
