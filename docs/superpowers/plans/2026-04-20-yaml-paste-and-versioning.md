# YAML Paste + Version History Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development.

**Goal:** Bimodal YAML dialog (view/edit) + last-20 version history panel with Restore, landing on `feat/training-observability` branch.

**Architecture:** Evolve `YamlPreviewDialog` (currently read-only) into a dialog with edit mode, schema validation before save, and a collapsible history panel that loads older versions into the editor for review + save as a new version.

**Tech Stack:** React 19, TanStack Query v5, shadcn Dialog/AlertDialog/Collapsible, TypeScript strict. One small backend addition: `POST /configs/validate-inline` taking raw YAML body.

**Spec:** `docs/superpowers/specs/2026-04-20-yaml-paste-and-versioning-design.md`.

---

## Key facts from recon

`ConfigVersionCreate.source_tag` is `Literal["user", "ai_suggestion", "system"]` — constrained. Use **`sourceTag="user"`** for both paste and rollback; distinguish via `sourceDetail`:
- paste → `sourceDetail="yaml_paste"`
- rollback → `sourceDetail="rollback_from_v<N>"`

Existing form-editor saves already use `sourceTag="user"`.

The existing validate endpoint `POST /configs/{version_id}/validate` takes **no body** — it validates the already-stored YAML for that version id. We need a new endpoint that validates *pasted* YAML before it's saved. Task 1 adds it.

---

## File structure

### Create

**Backend:**
- `backend/tests/test_config_validate_inline.py`

**Frontend:**
- `frontend/src/types/config-version.ts`
- `frontend/src/api/config-versions.ts`
- `frontend/src/hooks/useConfigVersions.ts`
- `frontend/src/lib/yaml-parse.ts`
- `frontend/src/components/config/yaml-editor-pane.tsx`
- `frontend/src/components/config/config-versions-panel.tsx`

### Modify

**Backend:**
- `backend/app/api/routes/configs.py` — add `POST /configs/validate-inline`
- `backend/app/schemas/config_version.py` — add `ConfigValidateInlineRequest` (just `{yaml_content: str}`)

**Frontend:**
- `frontend/src/components/training/yaml-preview-dialog.tsx` — rewrite for bimodal + history

---

## Conventions
- Plain `<textarea>` in monospace for editor — no Monaco/CodeMirror.
- Dialog width widens from 520px → 720px (pass `className="max-w-[720px]"` to `DialogContent`).
- Use existing `useSaveConfig` mutation.
- TDD where meaningful (yaml-parse helper has a pure test); frontend has no component test suite — manual verification per the spec.
- Commits follow project git-commit rules: lowercase, imperative, no AI attribution.

---

## Task 1 — Backend: `POST /configs/validate-inline` endpoint

**Files:**
- Modify: `backend/app/schemas/config_version.py`
- Modify: `backend/app/api/routes/configs.py`
- Test: `backend/tests/test_config_validate_inline.py`

### 1.1 Request schema

Add to `backend/app/schemas/config_version.py`:

```python
class ConfigValidateInlineRequest(BaseModel):
    yaml_content: str
```

### 1.2 Failing test

Create `backend/tests/test_config_validate_inline.py`:

```python
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app


_GOOD_YAML = """\
project:
  name: p
  mode: single_user_local
"""


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(db_session):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_validate_inline_accepts_valid_yaml(client: AsyncClient) -> None:
    project = (
        await client.post("/api/v1/projects", json={"name": "v", "description": ""})
    ).json()
    resp = await client.post(
        f"/api/v1/projects/{project['id']}/configs/validate-inline",
        json={"yaml_content": _GOOD_YAML},
    )
    assert resp.status_code == 200
    assert resp.json()["is_valid"] is True


async def test_validate_inline_rejects_non_mapping(client: AsyncClient) -> None:
    project = (
        await client.post("/api/v1/projects", json={"name": "vi", "description": ""})
    ).json()
    resp = await client.post(
        f"/api/v1/projects/{project['id']}/configs/validate-inline",
        json={"yaml_content": "- 1\n- 2\n"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is False
    assert len(body["errors"]) > 0


async def test_validate_inline_rejects_bad_yaml_syntax(client: AsyncClient) -> None:
    project = (
        await client.post("/api/v1/projects", json={"name": "vs", "description": ""})
    ).json()
    resp = await client.post(
        f"/api/v1/projects/{project['id']}/configs/validate-inline",
        json={"yaml_content": ": :: : bad"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is False
    assert len(body["errors"]) > 0
```

### 1.3 Run failing test

```
cd backend && pytest tests/test_config_validate_inline.py -v
```

Expected: 404.

### 1.4 Add route

In `backend/app/api/routes/configs.py`, add next to the existing validate route. The existing `validate_config` service function (non-async) at `config_service.py` already takes a `yaml_content: str` and returns `ConfigValidationResponse`. Reuse it.

```python
from app.schemas.config_version import ConfigValidateInlineRequest


@router.post(
    "/{project_id}/configs/validate-inline",
    response_model=ConfigValidationResponse,
)
async def validate_inline_config(
    project_id: str,
    payload: ConfigValidateInlineRequest,
    session: DbSession,
) -> ConfigValidationResponse:
    # project_id is accepted for API consistency but not used — validation is
    # independent of project context. Call existing sync validator.
    return config_service.validate_config(payload.yaml_content)
```

**Verify** the exact import of `config_service` in the route file — grep first. If `ConfigValidationResponse` isn't imported there already, add it.

### 1.5 Run tests + commit

```
cd backend && pytest tests/test_config_validate_inline.py -v
cd backend && ruff check app/api/routes/configs.py app/schemas/config_version.py tests/test_config_validate_inline.py
```

```
git add backend/app/schemas/config_version.py backend/app/api/routes/configs.py backend/tests/test_config_validate_inline.py
git commit -m "add: validate-inline endpoint accepting raw yaml body returning validation errors"
```

---

## Task 2 — Types, API clients, and version list hook

**Files:**
- Create: `frontend/src/types/config-version.ts`
- Create: `frontend/src/api/config-versions.ts`
- Create: `frontend/src/hooks/useConfigVersions.ts`

### 2.1 Types

`frontend/src/types/config-version.ts`:

```typescript
export interface ConfigVersionSummary {
  readonly id: string;
  readonly projectId: string;
  readonly versionNumber: number;
  readonly yamlHash: string;
  readonly diffFromPrev: unknown | null;
  readonly sourceTag: string;
  readonly sourceDetail: string | null;
  readonly createdAt: string;
}

export interface ConfigVersionList {
  readonly items: ReadonlyArray<ConfigVersionSummary>;
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

export interface ConfigValidationResult {
  readonly isValid: boolean;
  readonly errors: ReadonlyArray<string>;
}
```

### 2.2 API client

`frontend/src/api/config-versions.ts`:

```typescript
import type {
  ConfigValidationResult,
  ConfigVersionList,
  ConfigVersionSummary,
} from "@/types/config-version";
import { fetchApi } from "./client";

interface RawSummary {
  readonly id: string;
  readonly project_id: string;
  readonly version_number: number;
  readonly yaml_hash: string;
  readonly diff_from_prev: unknown | null;
  readonly source_tag: string;
  readonly source_detail: string | null;
  readonly created_at: string;
}

interface RawList {
  readonly items: ReadonlyArray<RawSummary>;
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

function toSummary(raw: RawSummary): ConfigVersionSummary {
  return {
    id: raw.id,
    projectId: raw.project_id,
    versionNumber: raw.version_number,
    yamlHash: raw.yaml_hash,
    diffFromPrev: raw.diff_from_prev,
    sourceTag: raw.source_tag,
    sourceDetail: raw.source_detail,
    createdAt: raw.created_at,
  };
}

export async function fetchConfigVersions({
  projectId,
  limit = 20,
  offset = 0,
}: {
  projectId: string;
  limit?: number;
  offset?: number;
}): Promise<ConfigVersionList> {
  const raw = await fetchApi<RawList>({
    path: `/projects/${projectId}/configs?limit=${limit}&offset=${offset}`,
  });
  return {
    items: raw.items.map(toSummary),
    total: raw.total,
    limit: raw.limit,
    offset: raw.offset,
  };
}

export async function fetchConfigYamlByVersion({
  projectId,
  versionId,
}: {
  projectId: string;
  versionId: string;
}): Promise<string> {
  return fetchApi<string>({
    path: `/projects/${projectId}/configs/${versionId}/yaml`,
    raw: true,
  });
}

interface RawValidation {
  readonly is_valid: boolean;
  readonly errors: ReadonlyArray<string>;
}

export async function validateYamlInline({
  projectId,
  yamlContent,
}: {
  projectId: string;
  yamlContent: string;
}): Promise<ConfigValidationResult> {
  const raw = await fetchApi<RawValidation>({
    path: `/projects/${projectId}/configs/validate-inline`,
    method: "POST",
    body: { yaml_content: yamlContent },
  });
  return { isValid: raw.is_valid, errors: raw.errors };
}
```

**Verify** `fetchApi` supports `{ raw: true }` for plain-text responses or `{ method: "POST" }`. If its signature differs, adapt. Run `sed -n '1,60p' frontend/src/api/client.ts` first.

### 2.3 Hook

`frontend/src/hooks/useConfigVersions.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";

import { fetchConfigVersions } from "@/api/config-versions";
import type { ConfigVersionList } from "@/types/config-version";

export const CONFIG_VERSIONS_KEY = (projectId: string) =>
  ["projects", projectId, "config-versions"] as const;

export function useConfigVersions({
  projectId,
  limit = 20,
}: {
  projectId: string;
  limit?: number;
}) {
  return useQuery<ConfigVersionList>({
    queryKey: CONFIG_VERSIONS_KEY(projectId),
    queryFn: () => fetchConfigVersions({ projectId, limit }),
    enabled: Boolean(projectId),
  });
}
```

### 2.4 Verify + commit

```
cd frontend && npx tsc --noEmit
cd frontend && npx prettier --write src/types/config-version.ts src/api/config-versions.ts src/hooks/useConfigVersions.ts
cd frontend && ./node_modules/.bin/eslint src/types/config-version.ts src/api/config-versions.ts src/hooks/useConfigVersions.ts
```

```
git add frontend/src/types/config-version.ts frontend/src/api/config-versions.ts frontend/src/hooks/useConfigVersions.ts
git commit -m "add: config version types api client and tanstack hook for history list yaml fetch and validation"
```

---

## Task 3 — YAML parse helper

**Files:**
- Create: `frontend/src/lib/yaml-parse.ts`
- Test: `frontend/src/__tests__/yaml-parse.test.ts` — **only if vitest is already configured in the project**; check first with `test -f frontend/vitest.config.ts && echo YES || echo NO`. If NO, skip the test file; add a brief JSDoc instead.

### 3.1 Helper

`frontend/src/lib/yaml-parse.ts`:

```typescript
import yaml from "js-yaml";

export type YamlParseResult =
  | { readonly ok: true; readonly value: unknown }
  | { readonly ok: false; readonly line: number | null; readonly message: string };

export function tryParseYaml(source: string): YamlParseResult {
  try {
    const value = yaml.load(source);
    return { ok: true, value };
  } catch (err) {
    if (err instanceof yaml.YAMLException) {
      return {
        ok: false,
        line: err.mark?.line !== undefined ? err.mark.line + 1 : null,
        message: err.reason ?? err.message,
      };
    }
    return {
      ok: false,
      line: null,
      message: err instanceof Error ? err.message : String(err),
    };
  }
}
```

**Verify** the project uses `js-yaml` (recon should show `yaml.parse()` — grep for the import: `grep -rn "from \"js-yaml\"\|from \"yaml\"" frontend/src/lib/ frontend/src/pages/ | head -5`). If it uses the `yaml` package (different API, default export `yaml.parse`), adapt the import + `yaml.load` call and the error class check.

### 5.2 Verify + commit

```
cd frontend && npx tsc --noEmit
cd frontend && ./node_modules/.bin/eslint src/lib/yaml-parse.ts
```

```
git add frontend/src/lib/yaml-parse.ts
git commit -m "add: tryParseYaml helper returning discriminated union with line number on syntax error"
```

---

## Task 4 — `YamlEditorPane` component

**Files:**
- Create: `frontend/src/components/config/yaml-editor-pane.tsx`

### 5.1 Component

`frontend/src/components/config/yaml-editor-pane.tsx`:

```tsx
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { tryParseYaml } from "@/lib/yaml-parse";
import type { ConfigValidationResult } from "@/types/config-version";

interface YamlEditorPaneProps {
  readonly initialYaml: string;
  readonly isSaving: boolean;
  readonly schemaErrors: ReadonlyArray<string>;
  readonly onDirtyChange: (isDirty: boolean) => void;
  readonly onSave: (yamlContent: string) => void;
  readonly onCancel: () => void;
}

export function YamlEditorPane({
  initialYaml,
  isSaving,
  schemaErrors,
  onDirtyChange,
  onSave,
  onCancel,
}: YamlEditorPaneProps): React.JSX.Element {
  const [value, setValue] = React.useState(initialYaml);
  const [parseError, setParseError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setValue(initialYaml);
  }, [initialYaml]);

  const isDirty = value !== initialYaml;
  React.useEffect(() => {
    onDirtyChange(isDirty);
  }, [isDirty, onDirtyChange]);

  const handleSave = (): void => {
    const parsed = tryParseYaml(value);
    if (!parsed.ok) {
      const linePrefix = parsed.line !== null ? `line ${parsed.line}: ` : "";
      setParseError(`${linePrefix}${parsed.message}`);
      return;
    }
    setParseError(null);
    onSave(value);
  };

  return (
    <div className="flex flex-col gap-2">
      {parseError !== null ? (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-[11px] font-mono text-red-700">
          {parseError}
        </div>
      ) : null}

      <Textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        spellCheck={false}
        className="min-h-[360px] font-mono text-[11px] leading-relaxed"
      />

      {schemaErrors.length > 0 ? (
        <div className="flex flex-col gap-1 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2">
          <div className="font-mono text-[10px] uppercase tracking-wider text-amber-800">
            schema errors
          </div>
          {schemaErrors.map((error, idx) => (
            <div key={`err-${idx}`} className="font-mono text-[11px] text-amber-900">
              {error}
            </div>
          ))}
        </div>
      ) : null}

      <div className="flex justify-end gap-2 pt-1">
        <Button variant="outline" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button variant="primary" onClick={handleSave} disabled={isSaving}>
          {isSaving ? "Saving…" : "Save as new version"}
        </Button>
      </div>
    </div>
  );
}
```

**Verify** `Textarea` exists at `@/components/ui/textarea`. If it doesn't, fall back to a styled `<textarea className="..." />`. Run: `test -f frontend/src/components/ui/textarea.tsx && echo YES || echo NO`.

### 5.2 Verify + commit

```
cd frontend && npx tsc --noEmit
cd frontend && npx prettier --write src/components/config/yaml-editor-pane.tsx
cd frontend && ./node_modules/.bin/eslint src/components/config/yaml-editor-pane.tsx
```

```
git add frontend/src/components/config/yaml-editor-pane.tsx
git commit -m "add: yaml editor pane with syntax error banner and schema error list"
```

---

## Task 5 — `ConfigVersionsPanel` component

**Files:**
- Create: `frontend/src/components/config/config-versions-panel.tsx`

### 5.1 Component

`frontend/src/components/config/config-versions-panel.tsx`:

```tsx
import * as React from "react";
import { ChevronDown, ChevronRight, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useConfigVersions } from "@/hooks/useConfigVersions";
import type { ConfigVersionSummary } from "@/types/config-version";

interface ConfigVersionsPanelProps {
  readonly projectId: string;
  readonly activeVersionId: string | null;
  readonly onRestore: (version: ConfigVersionSummary) => void;
}

export function ConfigVersionsPanel({
  projectId,
  activeVersionId,
  onRestore,
}: ConfigVersionsPanelProps): React.JSX.Element {
  const [isOpen, setIsOpen] = React.useState(false);
  const { data, isLoading, error } = useConfigVersions({ projectId });

  const items = data?.items ?? [];

  return (
    <div className="rounded-md border border-hairline bg-surface-2">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-[11px] font-mono uppercase tracking-wider text-ink-3 hover:text-ink-1"
      >
        {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        History ({items.length})
      </button>

      {isOpen ? (
        <div className="divide-y divide-hairline">
          {isLoading ? (
            <div className="px-3 py-2 text-[11px] text-ink-3">Loading…</div>
          ) : error !== null ? (
            <div className="px-3 py-2 text-[11px] text-red-600">
              Failed to load history
            </div>
          ) : items.length === 0 ? (
            <div className="px-3 py-2 text-[11px] text-ink-3">No versions yet.</div>
          ) : (
            items.map((version) => (
              <VersionRow
                key={version.id}
                version={version}
                isActive={version.id === activeVersionId}
                onRestore={() => onRestore(version)}
              />
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}

interface VersionRowProps {
  readonly version: ConfigVersionSummary;
  readonly isActive: boolean;
  readonly onRestore: () => void;
}

function VersionRow({ version, isActive, onRestore }: VersionRowProps): React.JSX.Element {
  const changeSummary = summarizeDiff(version.diffFromPrev);
  const detailLabel = version.sourceDetail ?? version.sourceTag;

  return (
    <div className="grid grid-cols-[80px_1fr_120px_auto] items-center gap-3 px-3 py-2">
      <span className="font-mono text-xs text-ink-1">v{version.versionNumber}</span>
      <div className="flex items-center gap-2 text-[11px] text-ink-3">
        <span className="font-mono">{formatRelative(version.createdAt)}</span>
        <Badge variant="secondary" className="text-[10px]">
          {detailLabel}
        </Badge>
        {isActive ? (
          <Badge variant="secondary" className="bg-emerald-600/20 text-emerald-700">
            active
          </Badge>
        ) : null}
      </div>
      <span className="font-mono text-[11px] text-ink-3">{changeSummary}</span>
      <Button
        variant="ghost"
        size="sm"
        onClick={onRestore}
        disabled={isActive}
        className="gap-1"
      >
        <RotateCcw className="h-3 w-3" />
        Restore
      </Button>
    </div>
  );
}

function summarizeDiff(diff: unknown): string {
  if (
    diff === null ||
    typeof diff !== "object" ||
    !("changed" in diff) ||
    !("added" in diff) ||
    !("removed" in diff)
  ) {
    return "—";
  }
  const typed = diff as {
    changed: Record<string, unknown>;
    added: Record<string, unknown>;
    removed: Record<string, unknown>;
  };
  const c = Object.keys(typed.changed ?? {}).length;
  const a = Object.keys(typed.added ?? {}).length;
  const r = Object.keys(typed.removed ?? {}).length;
  if (c + a + r === 0) return "no diff";
  const parts: string[] = [];
  if (c > 0) parts.push(`${c} changed`);
  if (a > 0) parts.push(`${a} added`);
  if (r > 0) parts.push(`${r} removed`);
  return parts.join(", ");
}

function formatRelative(isoString: string): string {
  const delta = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(delta / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
```

**Verify** `Badge` exists at `@/components/ui/badge`, `Button` at `@/components/ui/button`. Both already exist from prior tasks.

### 5.2 Verify + commit

```
cd frontend && npx tsc --noEmit
cd frontend && npx prettier --write src/components/config/config-versions-panel.tsx
cd frontend && ./node_modules/.bin/eslint src/components/config/config-versions-panel.tsx
```

```
git add frontend/src/components/config/config-versions-panel.tsx
git commit -m "add: config versions panel showing last 20 with restore button source detail pill and diff summary"
```

---

## Task 6 — Rewrite `YamlPreviewDialog` as bimodal view/edit + history

**Files:**
- Modify: `frontend/src/components/training/yaml-preview-dialog.tsx`
- Modify: `frontend/src/pages/training-page.tsx` — pass `projectId` + `activeVersionId` into the dialog

### 6.1 Read current implementation

```
cat frontend/src/components/training/yaml-preview-dialog.tsx
grep -n "YamlPreviewDialog\|isYamlDialogOpen" frontend/src/pages/training-page.tsx | head -10
```

Confirm the props interface, how it reads `yamlContent`, and how `training-page.tsx` constructs the preview.

### 6.2 Rewrite

Full replacement for `frontend/src/components/training/yaml-preview-dialog.tsx`:

```tsx
import * as React from "react";

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/shared/code-block";
import { YamlEditorPane } from "@/components/config/yaml-editor-pane";
import { ConfigVersionsPanel } from "@/components/config/config-versions-panel";
import { useSaveConfig } from "@/hooks/useConfigs";
import { useToast } from "@/hooks/use-toast";
import {
  fetchConfigYamlByVersion,
  validateYamlInline,
} from "@/api/config-versions";
import { useQueryClient } from "@tanstack/react-query";
import { CONFIG_VERSIONS_KEY } from "@/hooks/useConfigVersions";
import type { ConfigVersionSummary } from "@/types/config-version";

type Mode = "view" | "edit";

interface YamlPreviewDialogProps {
  readonly isOpen: boolean;
  readonly projectId: string;
  readonly activeVersionId: string | null;
  readonly yamlContent: string;
  readonly onClose: () => void;
}

export function YamlPreviewDialog({
  isOpen,
  projectId,
  activeVersionId,
  yamlContent,
  onClose,
}: YamlPreviewDialogProps): React.JSX.Element {
  const [mode, setMode] = React.useState<Mode>("view");
  const [editorYaml, setEditorYaml] = React.useState(yamlContent);
  const [schemaErrors, setSchemaErrors] = React.useState<ReadonlyArray<string>>([]);
  const [isDirty, setIsDirty] = React.useState(false);
  const [pendingAction, setPendingAction] = React.useState<
    | { readonly kind: "close" }
    | { readonly kind: "restore"; readonly version: ConfigVersionSummary }
    | null
  >(null);
  const [rollbackDetail, setRollbackDetail] = React.useState<string | null>(null);

  const { toast } = useToast();
  const queryClient = useQueryClient();
  const saveMutation = useSaveConfig({ projectId });

  React.useEffect(() => {
    if (isOpen) {
      setMode("view");
      setEditorYaml(yamlContent);
      setSchemaErrors([]);
      setIsDirty(false);
      setRollbackDetail(null);
    }
  }, [isOpen, yamlContent]);

  const handleCloseRequest = (): void => {
    if (mode === "edit" && isDirty) {
      setPendingAction({ kind: "close" });
      return;
    }
    onClose();
  };

  const handleRestoreRequest = (version: ConfigVersionSummary): void => {
    if (mode === "edit" && isDirty) {
      setPendingAction({ kind: "restore", version });
      return;
    }
    loadVersionIntoEditor(version);
  };

  const loadVersionIntoEditor = async (version: ConfigVersionSummary): Promise<void> => {
    try {
      const loadedYaml = await fetchConfigYamlByVersion({
        projectId,
        versionId: version.id,
      });
      setEditorYaml(loadedYaml);
      setRollbackDetail(`rollback_from_v${version.versionNumber}`);
      setSchemaErrors([]);
      setMode("edit");
    } catch (err) {
      toast({
        title: "Failed to load version",
        description: err instanceof Error ? err.message : "Unknown error",
      });
    }
  };

  const handleSave = async (yamlText: string): Promise<void> => {
    setSchemaErrors([]);
    try {
      const validation = await validateYamlInline({
        projectId,
        yamlContent: yamlText,
      });
      if (!validation.isValid) {
        setSchemaErrors(validation.errors);
        return;
      }
    } catch (err) {
      toast({
        title: "Validation failed",
        description: err instanceof Error ? err.message : "Unknown error",
      });
      return;
    }

    const sourceDetail = rollbackDetail ?? "yaml_paste";

    try {
      await saveMutation.mutateAsync({
        request: {
          yamlContent: yamlText,
          sourceTag: "user",
          sourceDetail,
        },
      });
      await queryClient.invalidateQueries({ queryKey: CONFIG_VERSIONS_KEY(projectId) });
      toast({ title: `Saved as new version (${sourceDetail})` });
      setMode("view");
      setRollbackDetail(null);
      setIsDirty(false);
    } catch (err) {
      toast({
        title: "Failed to save",
        description: err instanceof Error ? err.message : "Unknown error",
      });
    }
  };

  return (
    <>
      <Dialog
        open={isOpen}
        onOpenChange={(open) => {
          if (!open) handleCloseRequest();
        }}
      >
        <DialogContent className="max-w-[720px]">
          <DialogHeader>
            <DialogTitle>YAML config</DialogTitle>
            <div className="flex gap-1">
              <Button
                variant={mode === "view" ? "primary" : "outline"}
                size="sm"
                onClick={() => {
                  if (mode === "edit" && isDirty) {
                    setPendingAction({ kind: "close" });
                    return;
                  }
                  setMode("view");
                  setRollbackDetail(null);
                }}
              >
                View
              </Button>
              <Button
                variant={mode === "edit" ? "primary" : "outline"}
                size="sm"
                onClick={() => setMode("edit")}
              >
                Edit
              </Button>
            </div>
          </DialogHeader>

          <div className="flex flex-col gap-3 overflow-hidden px-6 py-5">
            {mode === "view" ? (
              <div className="max-h-[360px] overflow-auto">
                <CodeBlock language="yaml">{yamlContent}</CodeBlock>
              </div>
            ) : (
              <YamlEditorPane
                initialYaml={editorYaml}
                isSaving={saveMutation.isPending}
                schemaErrors={schemaErrors}
                onDirtyChange={setIsDirty}
                onSave={handleSave}
                onCancel={handleCloseRequest}
              />
            )}

            <ConfigVersionsPanel
              projectId={projectId}
              activeVersionId={activeVersionId}
              onRestore={handleRestoreRequest}
            />
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseRequest}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={pendingAction !== null}
        onOpenChange={(open) => {
          if (!open) setPendingAction(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard unsaved edits?</AlertDialogTitle>
            <AlertDialogDescription>
              Your current edits will be lost.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                const action = pendingAction;
                setPendingAction(null);
                if (action === null) return;
                if (action.kind === "close") {
                  onClose();
                } else {
                  void loadVersionIntoEditor(action.version);
                }
              }}
            >
              Discard
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
```

### 6.3 Update call site in `training-page.tsx`

Find the `<YamlPreviewDialog ... />` usage and add the two new props. The page likely already has `activeConfig` via `useActiveConfig` — pass `activeVersionId={activeConfig?.id ?? null}` and `projectId={projectId}`.

```
grep -n "YamlPreviewDialog\|useActiveConfig\|activeConfig\." frontend/src/pages/training-page.tsx | head -15
```

Example patch:

```tsx
<YamlPreviewDialog
  isOpen={isYamlDialogOpen}
  projectId={projectId}
  activeVersionId={activeConfig?.id ?? null}
  yamlContent={yamlPreview}
  onClose={() => setIsYamlDialogOpen(false)}
/>
```

### 6.4 Verify

```
cd frontend && npx tsc --noEmit
cd frontend && npx prettier --write src/components/training/yaml-preview-dialog.tsx src/pages/training-page.tsx
cd frontend && ./node_modules/.bin/eslint src/components/training/yaml-preview-dialog.tsx src/pages/training-page.tsx
```

### 6.5 Commit

```
git add frontend/src/components/training/yaml-preview-dialog.tsx frontend/src/pages/training-page.tsx
git commit -m "update: yaml preview dialog becomes bimodal editor with history panel rollback and schema validation"
```

---

## Task 7 — Final sweep + manual verification

### 7.1 Full checks

```
cd frontend && npx tsc --noEmit
cd frontend && ./node_modules/.bin/eslint src/
cd backend && pytest tests/test_configs.py -v
```

Expected: tsc + eslint clean on observability + yaml-paste files (pre-existing warnings on unrelated files are OK). Backend tests unchanged — they still pass.

### 7.2 Manual verification (request from user)

1. Open project → training page → click YAML button → dialog shows current YAML in view mode.
2. Click Edit → textarea populated. Change `training.learning_rate: 2e-4` to `training.learning_rate: "fast"` → Save → schema errors render below textarea.
3. Fix to a valid numeric value → Save → toast "Saved as new version (yaml_paste)", history panel shows a new row with `yaml_paste` pill, forms on the page reflect the new learning rate.
4. Expand History → click Restore on an older version. Editor switches to edit mode with that YAML. Click Save → toast "Saved as new version (rollback_from_v<N>)", history gains a `rollback_from_vN` row.
5. Edit the YAML without saving, click Restore → AlertDialog "Discard unsaved edits?" appears. Cancel preserves edits; Discard loads the version.
6. Edit without saving, click Close (X or Close button) → AlertDialog fires. Cancel keeps dialog open; Discard closes it.

### 7.3 Final commit (if any fixes needed)

```
git add <files>
git commit -m "fix: resolve lint and type findings from yaml paste sweep"
```

---

## Acceptance criteria

- Bimodal YAML dialog: View (current active) and Edit (bound to textarea).
- Schema errors from `validateYamlInline` render inline under the textarea; save is blocked when errors exist.
- YAML syntax errors render above the textarea with line number.
- Save creates a new `ConfigVersion` via `useSaveConfig` with `sourceTag="user"`, `sourceDetail="yaml_paste"` or `"rollback_from_v<N>"`.
- Active config invalidation propagates to all form tabs via TanStack Query.
- History panel shows last 20 versions with change summary, source detail pill, active badge, Restore button (disabled for active).
- Restore loads version YAML into editor; user must explicitly click Save to commit.
- Dirty-state guard fires on Restore, Close, and View-mode toggle.

## Risks

- `source_tag` literal on backend is `Literal["user", "ai_suggestion", "system"]`. If a future change tightens `source_detail` similarly, the convention breaks. Low probability.
- The validation endpoint added in Task 1 (`POST /configs/validate-inline`) ignores `project_id` — validation is project-independent. The path keeps `project_id` only for API consistency. If multi-tenant validation rules later differ per project, this signature stays compatible.
- If `useSaveConfig` does the active-config invalidation itself (it probably does), the extra `queryClient.invalidateQueries(CONFIG_VERSIONS_KEY)` ensures the history list also refreshes. Harmless duplication if it's already there.
