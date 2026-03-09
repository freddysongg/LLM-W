# Dataset Subset Selector — Design

**Date:** 2026-03-09
**Replaces:** `FilterExpressionInput` (free-text Python expression)

## Problem

The existing filter expression input requires users to write Python expressions (e.g. `len(row['response']) > 50`) to subset their dataset. This is unclear, error-prone, and not aligned with how users actually think about dataset selection (splits, sample sizes).

## Solution

Replace the filter expression with two structured controls:

1. **Split selector** — toggle pills for each available split with row counts
2. **Sample size control** — three-mode control (All / Percentage / Row limit)

## Controls

### Split Selector

- Shown after dataset resolves; falls back to text inputs before resolution
- Available splits (train / validation / test) displayed as labeled toggle pills with row counts from the resolved profile
- Selected splits map to existing `train_split` / `eval_split` config fields
- If user selects only train: `eval_split` becomes null
- If user selects validation as eval: that split name is stored as `eval_split`

### Sample Size

Three modes toggled via radio-style buttons:

| Mode | Behavior | Stored as |
|------|----------|-----------|
| All | No limit | `max_samples: null` |
| Percentage | Slider 10–100%, converts to row count using resolved total | `max_samples: Math.floor(pct * totalRows)` |
| Row limit | Direct integer input | `max_samples: N` |

Percentage mode is disabled until the dataset is resolved (total row count must be known).

## Scope

### Frontend

- Delete `components/dataset/filter-expression-input.tsx`
- Create `components/dataset/dataset-subset-selector.tsx`
- Update `DatasetFormState` in `app-store.ts`:
  - Remove: `filterExpression: string`
  - Add: `trainSplit: string`, `evalSplit: string | null`, `maxSamples: number | null`, `sampleMode: "all" | "percentage" | "rows"`
- Update `datasets-page.tsx` to wire new component, remove old one
- Update `api/datasets.ts` to pass `train_split`, `eval_split`, `max_samples` in resolve request

### Backend

- Remove `filter_expression` from `DatasetResolveRequest` schema and `DatasetConfig`
- Verify `max_samples` slicing is applied during dataset loading in `dataset_service.py`
- No new endpoints

## Out of Scope

- Field-value condition builder
- Stratified sampling
- Random seed control
- Changes to HuggingFace split loading mechanism
