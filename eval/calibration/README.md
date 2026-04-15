# v1 Calibration Set -- Labeling Protocol

This directory holds the hand-labeled calibration corpus used to tune the v1
judge rubrics (faithfulness, instruction-following, safety, hallucination).
It is the ground-truth input to the Critique Shadowing workflow described in
R3 of the eval design notes.

## Goal

Calibrate each v1 rubric against human verdicts so the judge can be trusted
in automated evaluation. Release gate for the calibrated set:

- **TPR >= 0.90** (true positive rate) and **TNR >= 0.90** (true negative
  rate) measured on a held-out 50-example slice after labeling.

To make that measurable we need a balanced label distribution on the
labeling pool of 150 (the remaining 50 are reserved as the held-out
evaluator). Aim for **40-60 percent pass rate** across the labeled set. If
your first pass skews above 70 percent pass, you MUST deliberately perturb
outputs before continuing (see "Perturbation patterns" below).

## Inputs

- `v1_raw.jsonl` -- 200 candidate (prompt, output) pairs, stratified across
  10 Dolly domain buckets, sourced by
  `scripts/eval/source_calibration_set.py`.
- `v1_raw.hash` -- SHA256 of `v1_raw.jsonl`. Recompute with
  `sha256sum eval/calibration/v1_raw.jsonl` before you start labeling to
  confirm the file has not been modified in transit.

Each row has these fields:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `str` | `cal-<8-hex>`, derived from (prompt, output). Do not edit. |
| `prompt` | `str` | User instruction + optional Dolly context. |
| `output` | `str` | Candidate model output being judged. |
| `reference` | `str \| null` | Dolly's reference answer. |
| `domain` | `str` | Stratification bucket. |
| `source` | `object` | `{dataset, revision, row_index}`. Provenance only. |
| `metadata` | `object` | Empty; reserved for label-time annotations. |

## Process

1. Copy `v1_raw.jsonl` to `v1_labels.jsonl`.
2. For each row, append two fields:
   - `verdict`: `"pass"` or `"fail"` (string literal, no other values).
   - `critique`: one-sentence reason the judge could reproduce.
3. Save `v1_labels.jsonl` after each labeling session.
4. After both sessions are complete, recompute the hash:

   ```bash
   sha256sum eval/calibration/v1_labels.jsonl > eval/calibration/v1_labels.hash
   ```

   (A dedicated `scripts/eval/hash_labels.py` ships in a follow-up ticket.)

## Session discipline (per R-16)

Label in **two sessions across two calendar days**. Fatigue shifts the
threshold between pass and fail and is the largest source of self-noise.

- Session 1: first 100 rows.
- Session 2: the remaining 100, plus **5 re-labels drawn from session 1**
  at random. Compare the session-2 verdicts against your own prior labels
  on those 5.
- If disagreement on the re-labels exceeds 10 percent (more than 1 of 5
  flips) **stop labeling**. Reset: reread the rubric definitions, discard
  any rows labeled after the drift began, and start session 2 over.

## What NOT to label

- **Do not write chain-of-thought reasoning traces.** The judge generates
  its own CoT; your critique is a one-line sanity signal, not a training
  target.
- **Do not score per-criterion.** Rubric criteria are evaluated by the
  judge. Your verdict is a single binary pass/fail.
- **Do not edit `prompt`, `output`, `reference`, `domain`, `source`, or
  `id`.** These are frozen provenance. Perturbations to `output` are the
  one exception and follow the rules below.

## Perturbation patterns

Dolly reference responses are by definition correct. Labeling them as-is
will produce a pass-heavy set that cannot calibrate the `fail` side of
each rubric. Before the second session, perturb ~30-40 percent of the
outputs using one of the following patterns. Record which rows were
perturbed by putting `"perturbed": "<pattern-name>"` into the
`metadata` object on that row.

1. **Entity hallucination** -- replace a concrete entity in the output
   (person, place, date, figure) with a plausible-sounding but wrong one.
   Example: "Virgin Australia started in 2000" -> "Virgin Australia
   started in 2004".
2. **Fact contradiction** -- invert a claim the prompt established as
   true. Example: prompt says a company is headquartered in Seattle;
   output says Portland.
3. **Directed omission** -- remove a directly-asked element. Example: if
   the prompt says "list three causes and explain each", keep the three
   causes and drop the explanations.
4. **Format violation** -- output prose where the prompt requested a
   bulleted or numbered list, or a bare string where JSON was requested.
5. **Topic drift** -- start on-topic, then append one or two sentences
   that wander into an unrelated subject.

Aim for roughly even coverage across the five patterns. Labeling the
perturbed rows as `fail` gives the judge realistic, diverse failure
modes to calibrate against.

## Output schema (post-labeling)

`v1_labels.jsonl` is identical to `v1_raw.jsonl` plus two fields:

```json
{
  "id": "cal-abcd1234",
  "prompt": "...",
  "output": "...",
  "reference": "...",
  "domain": "open_qa_short",
  "source": {"dataset": "databricks/databricks-dolly-15k", "revision": "...", "row_index": 123},
  "metadata": {"perturbed": "entity-hallucination"},
  "verdict": "fail",
  "critique": "Claims the airline started in 2004; the correct year is 2000."
}
```

## Class-balance target

At labeling close, the distribution of `verdict` values must be at least
40 percent for each class. If either class falls below 40 percent, apply
additional perturbations and re-label until the threshold is met. Do not
label the held-out 50 until the remaining 150 hit the balance target.

## Sourcing provenance

- Dataset: `databricks/databricks-dolly-15k`
- Pinned revision:
  `bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a`
- Stratification: 10 domain buckets x 20 rows. Buckets: `brainstorming`,
  `classification`, `closed_qa`, `creative_writing`,
  `general_qa_long`, `general_qa_short`, `information_extraction`,
  `open_qa_long`, `open_qa_short`, `summarization`. The `_long` / `_short`
  split is by per-category median instruction length; the split gives 10
  buckets from Dolly's 8 native categories while preserving reproducibility.
- Per-bucket shuffle seed: `42`.
- Output sorted by `id` (stable across runs).

Regenerate with:

```bash
python3 scripts/eval/source_calibration_set.py --force
```
