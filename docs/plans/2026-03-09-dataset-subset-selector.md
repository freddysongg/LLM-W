# Dataset Subset Selector Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the free-text Python filter expression with structured split and sample controls on the datasets page.

**Architecture:** New `DatasetSubsetSelector` component exposes split name inputs and a three-mode sample limit control. State lives in `DatasetFormState` in the Zustand store. The backend gains a `max_samples` field on `DatasetResolveRequest` and applies slicing before profiling. `filter_expression` is removed from both backend config schema and frontend state.

**Tech Stack:** React, TypeScript, Zustand, shadcn/ui (Label, Input, Button, Slider), FastAPI/Pydantic, Python

---

### Task 1: Update DatasetFormState in the Zustand store

**Files:**
- Modify: `frontend/src/stores/app-store.ts`

**Step 1: Update the `DatasetFormState` interface**

Replace the `filterExpression` field with the four new fields:

```ts
export type SampleMode = "all" | "percentage" | "rows";

export interface DatasetFormState {
  readonly source: DatasetSource;
  readonly datasetId: string;
  readonly format: DatasetFormat;
  readonly formatMapping: Record<string, string>;
  readonly trainSplit: string;
  readonly evalSplit: string | null;
  readonly sampleMode: SampleMode;
  readonly maxSamples: number | null;
}
```

Note: `SampleMode` must be exported — it will be imported by the new component.

**Step 2: Update `DEFAULT_DATASET_FORM`**

```ts
const DEFAULT_DATASET_FORM: DatasetFormState = {
  source: "huggingface",
  datasetId: "",
  format: "default",
  formatMapping: {},
  trainSplit: "train",
  evalSplit: "validation",
  sampleMode: "all",
  maxSamples: null,
};
```

**Step 3: Run the TypeScript compiler to catch any callers of `filterExpression`**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -40
```

Expected: errors in `datasets-page.tsx` referencing `filterExpression`. These will be fixed in Task 4.

**Step 4: Commit**

```bash
git add frontend/src/stores/app-store.ts
git commit -m "update DatasetFormState: replace filterExpression with split and sample fields"
```

---

### Task 2: Update the TypeScript dataset types and API client

**Files:**
- Modify: `frontend/src/types/dataset.ts`
- Modify: `frontend/src/api/datasets.ts`

**Step 1: Add `maxSamples` to `DatasetResolveRequest` in `types/dataset.ts`**

Change the interface at line 50:

```ts
export interface DatasetResolveRequest {
  readonly source: DatasetSource;
  readonly datasetId: string;
  readonly subset: string | null;
  readonly trainSplit: string;
  readonly evalSplit: string | null;
  readonly format: DatasetFormat;
  readonly formatMapping: Record<string, string> | null;
  readonly maxSamples: number | null;
}
```

**Step 2: Pass `max_samples` in `resolveDataset` in `api/datasets.ts`**

In the `body` object of `resolveDataset` (lines 76-84), add:

```ts
body: {
  source: request.source,
  dataset_id: request.datasetId,
  subset: request.subset,
  train_split: request.trainSplit,
  eval_split: request.evalSplit,
  format: request.format,
  format_mapping: request.formatMapping,
  max_samples: request.maxSamples,
},
```

**Step 3: Run type check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -40
```

Expected: same errors as before (in datasets-page.tsx), no new errors.

**Step 4: Commit**

```bash
git add frontend/src/types/dataset.ts frontend/src/api/datasets.ts
git commit -m "add maxSamples to DatasetResolveRequest type and api client"
```

---

### Task 3: Backend — add max_samples to resolve request and apply slicing

**Files:**
- Modify: `backend/app/schemas/dataset.py`
- Modify: `backend/app/schemas/workbench_config.py`
- Modify: `backend/app/services/dataset_service.py`

**Step 1: Add `max_samples` to `DatasetResolveRequest` in `backend/app/schemas/dataset.py`**

Add the field after `eval_split`:

```python
class DatasetResolveRequest(BaseModel):
    source: Literal["huggingface", "local_jsonl", "local_csv", "custom"]
    dataset_id: str
    subset: str | None = None
    train_split: str = "train"
    eval_split: str | None = "validation"
    format: Literal["default", "sharegpt", "openai", "alpaca", "custom"] = "default"
    format_mapping: dict[str, str] | None = None
    max_samples: int | None = None
```

**Step 2: Remove `filter_expression` from `DatasetConfig` in `backend/app/schemas/workbench_config.py`**

Delete the line:
```python
filter_expression: str | None = None
```

`max_samples` is already present — leave it.

**Step 3: Apply `max_samples` slicing in `resolve_dataset()` in `backend/app/services/dataset_service.py`**

After loading rows (after the `if request.source == "huggingface"` block, before format detection), add:

```python
if request.max_samples is not None and len(rows) > request.max_samples:
    rows = rows[: request.max_samples]
```

Also update `_write_resolved_dataset_to_config` to persist `train_split`, `eval_split`, and `max_samples` back to the YAML config. In the function body, after `dataset_section["source"] = profile.source`, add:

```python
dataset_section["train_split"] = request.train_split
if request.eval_split is not None:
    dataset_section["eval_split"] = request.eval_split
else:
    dataset_section.pop("eval_split", None)
if request.max_samples is not None:
    dataset_section["max_samples"] = request.max_samples
else:
    dataset_section.pop("max_samples", None)
dataset_section.pop("filter_expression", None)
```

Note: `_write_resolved_dataset_to_config` currently only receives `profile` — it needs to also receive `request` to write back the split names and max_samples. Update its signature:

```python
async def _write_resolved_dataset_to_config(
    *, session: AsyncSession, project_id: str, profile: DatasetProfile, request: DatasetResolveRequest
) -> None:
```

And update the call site in `resolve_dataset()`:

```python
await _write_resolved_dataset_to_config(
    session=session, project_id=project_id, profile=profile, request=request
)
```

**Step 4: Run ruff to catch any issues**

```bash
cd backend && ruff check app/schemas/dataset.py app/schemas/workbench_config.py app/services/dataset_service.py
```

Expected: no errors.

**Step 5: Commit**

```bash
git add backend/app/schemas/dataset.py backend/app/schemas/workbench_config.py backend/app/services/dataset_service.py
git commit -m "add max_samples to DatasetResolveRequest, apply slicing in resolve, remove filter_expression from config"
```

---

### Task 4: Create the DatasetSubsetSelector component

**Files:**
- Create: `frontend/src/components/dataset/dataset-subset-selector.tsx`

The component handles two sections: split configuration and sample size.

For sample size, it holds internal `percentageValue` state (10–100) that converts to `maxSamples` when `totalRows` is known.

```tsx
import * as React from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import type { SampleMode } from "@/stores/app-store";

interface DatasetSubsetSelectorProps {
  readonly trainSplit: string;
  readonly evalSplit: string | null;
  readonly sampleMode: SampleMode;
  readonly maxSamples: number | null;
  readonly totalRows: number | null;
  readonly onTrainSplitChange: (value: string) => void;
  readonly onEvalSplitChange: (value: string | null) => void;
  readonly onSampleModeChange: (mode: SampleMode) => void;
  readonly onMaxSamplesChange: (value: number | null) => void;
}

export function DatasetSubsetSelector({
  trainSplit,
  evalSplit,
  sampleMode,
  maxSamples,
  totalRows,
  onTrainSplitChange,
  onEvalSplitChange,
  onSampleModeChange,
  onMaxSamplesChange,
}: DatasetSubsetSelectorProps): React.JSX.Element {
  const [percentageValue, setPercentageValue] = React.useState<number>(100);

  const handleSampleModeChange = (mode: SampleMode): void => {
    onSampleModeChange(mode);
    if (mode === "all") {
      onMaxSamplesChange(null);
    } else if (mode === "percentage" && totalRows !== null) {
      onMaxSamplesChange(Math.floor((percentageValue / 100) * totalRows));
    } else if (mode === "rows" && maxSamples === null) {
      onMaxSamplesChange(1000);
    }
  };

  const handlePercentageChange = (pct: number): void => {
    setPercentageValue(pct);
    if (totalRows !== null) {
      onMaxSamplesChange(Math.floor((pct / 100) * totalRows));
    }
  };

  const handleRowLimitChange = (raw: string): void => {
    const parsed = parseInt(raw, 10);
    onMaxSamplesChange(Number.isNaN(parsed) || parsed < 1 ? null : parsed);
  };

  const computedRows =
    sampleMode === "percentage" && totalRows !== null
      ? Math.floor((percentageValue / 100) * totalRows)
      : null;

  return (
    <div className="space-y-4">
      {/* Split configuration */}
      <div className="space-y-2">
        <Label>Splits</Label>
        <div className="flex gap-3 items-center">
          <div className="flex-1 space-y-1">
            <p className="text-xs text-muted-foreground">Training split</p>
            <Input
              value={trainSplit}
              onChange={(e) => onTrainSplitChange(e.target.value)}
              placeholder="train"
            />
          </div>
          <div className="flex-1 space-y-1">
            <p className="text-xs text-muted-foreground">Eval split</p>
            <div className="flex gap-1">
              <Input
                value={evalSplit ?? ""}
                onChange={(e) => onEvalSplitChange(e.target.value || null)}
                placeholder="validation"
                disabled={evalSplit === null}
              />
              <Button
                type="button"
                variant={evalSplit === null ? "default" : "outline"}
                size="sm"
                className="shrink-0"
                onClick={() => onEvalSplitChange(evalSplit === null ? "validation" : null)}
              >
                {evalSplit === null ? "Add" : "None"}
              </Button>
            </div>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Named splits to load from the dataset. Use &quot;None&quot; to skip eval.
        </p>
      </div>

      {/* Sample size */}
      <div className="space-y-2">
        <Label>Sample size</Label>
        <div className="flex gap-1">
          {(["all", "percentage", "rows"] as const).map((mode) => (
            <Button
              key={mode}
              type="button"
              variant={sampleMode === mode ? "default" : "outline"}
              size="sm"
              disabled={mode === "percentage" && totalRows === null}
              onClick={() => handleSampleModeChange(mode)}
            >
              {mode === "all" ? "All" : mode === "percentage" ? "Percentage" : "Row limit"}
            </Button>
          ))}
        </div>

        {sampleMode === "percentage" && (
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <Slider
                min={10}
                max={100}
                step={5}
                value={[percentageValue]}
                onValueChange={([pct]) => handlePercentageChange(pct)}
                className="flex-1"
              />
              <span className="text-sm tabular-nums w-12 text-right">{percentageValue}%</span>
            </div>
            {computedRows !== null && (
              <p className="text-xs text-muted-foreground">
                ≈ {computedRows.toLocaleString()} rows
              </p>
            )}
          </div>
        )}

        {sampleMode === "rows" && (
          <Input
            type="number"
            min={1}
            value={maxSamples ?? ""}
            onChange={(e) => handleRowLimitChange(e.target.value)}
            placeholder="e.g. 5000"
          />
        )}

        <p className="text-xs text-muted-foreground">
          {sampleMode === "all" && "All rows from the selected splits will be used."}
          {sampleMode === "percentage" &&
            (totalRows === null
              ? "Resolve the dataset first to enable percentage sampling."
              : "Random slice of the dataset by percentage.")}
          {sampleMode === "rows" && "Maximum number of rows to load from the dataset."}
        </p>
      </div>
    </div>
  );
}
```

**Step 1: Verify shadcn Slider is available**

```bash
ls frontend/src/components/ui/slider.tsx 2>/dev/null && echo "exists" || echo "missing"
```

If missing, install it following the shadcn-manual-setup pattern (mx-ea45ae): install `@radix-ui/react-slider` and create `components/ui/slider.tsx` manually. The standard shadcn Slider component wraps `@radix-ui/react-slider` with the default class variants. If it already exists, skip this step.

**Step 2: Write the component file** using the code above.

**Step 3: Run type check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -40
```

Expected: errors remain only in `datasets-page.tsx`.

**Step 4: Commit**

```bash
git add frontend/src/components/dataset/dataset-subset-selector.tsx
git commit -m "add DatasetSubsetSelector component with split inputs and sample size control"
```

---

### Task 5: Wire DatasetSubsetSelector into datasets-page and remove old component

**Files:**
- Modify: `frontend/src/pages/datasets-page.tsx`
- Delete: `frontend/src/components/dataset/filter-expression-input.tsx`

**Step 1: Update `datasets-page.tsx`**

Remove the `FilterExpressionInput` import (line 12) and add the new import:

```ts
import { DatasetSubsetSelector } from "@/components/dataset/dataset-subset-selector";
```

Replace the `<FilterExpressionInput ... />` block (lines 122-125) with:

```tsx
<DatasetSubsetSelector
  trainSplit={datasetForm.trainSplit}
  evalSplit={datasetForm.evalSplit}
  sampleMode={datasetForm.sampleMode}
  maxSamples={datasetForm.maxSamples}
  totalRows={profile?.totalRows ?? null}
  onTrainSplitChange={(trainSplit) => setDatasetForm({ trainSplit })}
  onEvalSplitChange={(evalSplit) => setDatasetForm({ evalSplit })}
  onSampleModeChange={(sampleMode) => setDatasetForm({ sampleMode })}
  onMaxSamplesChange={(maxSamples) => setDatasetForm({ maxSamples })}
/>
```

Update `handleResolve` to use form state instead of hardcoded values:

```ts
const handleResolve = (): void => {
  const request: DatasetResolveRequest = {
    source: datasetForm.source,
    datasetId: datasetForm.datasetId,
    subset: null,
    trainSplit: datasetForm.trainSplit,
    evalSplit: datasetForm.evalSplit,
    format: datasetForm.format,
    formatMapping:
      Object.keys(datasetForm.formatMapping).length > 0 ? datasetForm.formatMapping : null,
    maxSamples: datasetForm.maxSamples,
  };
  resolveDataset.mutate(request);
};
```

Also update the `useEffect` that syncs profile back to form — it now needs to set `trainSplit` and `evalSplit` too. Since profile doesn't carry those values, remove that sync or limit it to only `source`/`datasetId`/`format` as before (leave split/sample fields as-is from the store).

**Step 2: Delete the old component**

```bash
rm frontend/src/components/dataset/filter-expression-input.tsx
```

**Step 3: Run full type check**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Expected: no errors.

**Step 4: Commit**

```bash
git add frontend/src/pages/datasets-page.tsx
git rm frontend/src/components/dataset/filter-expression-input.tsx
git commit -m "wire DatasetSubsetSelector into datasets page, remove filter expression input"
```

---

### Task 6: Manual smoke test

Start the dev server and verify:

```bash
cd frontend && npm run dev
```

Check:
1. Datasets page loads without errors
2. "Splits" section shows two inputs defaulting to "train" and "validation"
3. "None" button on eval split toggles eval split off/on
4. "Sample size" toggle shows All / Percentage / Row limit
5. Percentage mode is disabled before dataset is resolved
6. After resolving a dataset, Percentage mode activates and slider shows computed row count
7. Row limit mode shows a number input
8. Resolving the dataset sends correct `train_split`, `eval_split`, `max_samples` in the POST body (check Network tab)
9. No Python filter expression text field anywhere on the page

---

### Task 7: Check for filter_expression references and clean up

Ensure no stale references remain anywhere.

**Step 1:**

```bash
grep -r "filter_expression\|filterExpression" \
  frontend/src backend/app \
  --include="*.ts" --include="*.tsx" --include="*.py" \
  -l
```

Expected: zero matches (or only in migration files / YAML config files if any old configs exist on disk — those are fine since `_write_resolved_dataset_to_config` now actively removes the key).

**Step 2: If any matches, remove them**

**Step 3: Final commit if any cleanup was needed**

```bash
git add -p
git commit -m "remove remaining filter_expression references"
```
