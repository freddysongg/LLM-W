# YAML Paste + Version History + Rollback Design

**Date:** 2026-04-20
**Branch:** `feat/training-observability` (landing on same branch as observability work)
**Status:** Draft — pending user review

## Goal

Let users paste or edit raw YAML to create a new config version, see the last 20 versions of their project config, and restore any prior version into the editor for review/edit before committing.

## Motivation

Copying a teammate's YAML or rolling back a bad change currently requires rebuilding the config through the form one field at a time. The backend already has full version history (`ConfigVersion` rows, paginated list endpoint, diff helpers, auto-activation on save) — only the UI is missing.

## Goals

1. Paste or type raw YAML into a dialog, validate it, save as a new auto-activated `ConfigVersion`.
2. After save, `useActiveConfig` invalidates and all form tabs re-hydrate from the new YAML.
3. A version history panel shows the last 20 versions with metadata and change summary.
4. "Restore" loads an older version's YAML into the editor for review + edit; a normal Save commits it as a new version tagged `rollback`.
5. Schema validation (via existing `POST /configs/{id}/validate`) catches bad types and missing fields inline before save.

## Non-goals

- Live (as-you-type) schema validation.
- Monaco/CodeMirror editor — plain `<textarea>` in monospace.
- Search/filter/pagination beyond 20.
- Inline diff viewer between arbitrary version pairs.
- Auto-save / draft recovery.
- Any backend schema changes. All endpoints already exist.

## Architecture

Single entry point: the existing "YAML" button on the training page opens `YamlPreviewDialog`, which is rewritten to be bimodal:

- **View mode** (default on open): current active YAML rendered as read-only `<CodeBlock>` — preserves existing UX.
- **Edit mode** (via toggle): `<textarea>` populated with the current YAML; Save button validates and posts.
- **History panel** (collapsible below editor): lists last 20 versions with Restore buttons.

Restore → editor switches to edit mode, textarea populated with the selected version's YAML, `source_tag` pre-populated to `"rollback"` with `source_detail="from_v<N>"`. User can tweak or Save as-is.

Dirty-state guard (reuses existing `AlertDialog`) fires on Restore click, dialog close, or mode flip from edit → view.

## Data flow

### Save from paste/edit

```
textarea → client yaml.parse()
  ↳ syntax error → red banner with line/message, abort
  ↳ ok → POST /configs/{active_id}/validate { yamlContent }
     ↳ errors[] returned → per-path list rendered below textarea, abort
     ↳ clean → PUT /configs { yamlContent, sourceTag, sourceDetail }
        ↳ backend create_config_version sets active pointer
        ↳ client: queryClient.invalidateQueries(["projects", projectId, "active-config"])
        ↳ toast: "Saved as version v<N>"
        ↳ dialog flips back to view mode
```

### Restore from history

```
click Restore(v3) [dirty state confirm if unsaved edits]
  → GET /configs/v3/yaml
  → editor mode = edit, textarea = v3.yaml_blob
  → source tag metadata = { tag: "rollback", detail: "from_v3" }
  → user reviews, optionally edits, clicks Save → same save path above
```

## Files

### Create

| File | Purpose |
|---|---|
| `frontend/src/types/config-version.ts` | `ConfigVersionSummary` `{id, versionNumber, createdAt, yamlHash, sourceTag, sourceDetail, diffFromPrev}` |
| `frontend/src/api/config-versions.ts` | `fetchConfigVersions({projectId, limit, offset})`, `fetchConfigYamlByVersion({projectId, versionId})`, `validateConfigYaml({projectId, versionId, yamlContent})` |
| `frontend/src/hooks/useConfigVersions.ts` | TanStack Query hook over the list endpoint |
| `frontend/src/components/config/config-versions-panel.tsx` | History list — 20 rows with metadata + Restore button |
| `frontend/src/components/config/yaml-editor-pane.tsx` | Textarea + parse-error banner + schema-error list; emits `onSave` with yaml string + source metadata |
| `frontend/src/lib/yaml-parse.ts` | Thin wrapper returning `{ok: true, value} | {ok: false, line, message}` for client-side syntax check |

### Modify

| File | Change |
|---|---|
| `frontend/src/pages/training-page.tsx` | Rewrite `YamlPreviewDialog` body to host view/edit toggle + versions panel; wire `useConfigVersions`, `useSaveConfig` |

No backend changes.

## Error handling

| Case | Surface |
|---|---|
| Invalid YAML syntax | Red banner above textarea: `line N: <message>`. Save disabled. |
| Schema validation returns errors | Per-path list below textarea (`training.learning_rate: expected number, got str`). Save re-enabled after any edit. |
| Network failure on save | Toast with retry callback |
| Network failure on version list | History panel shows "Failed to load history" + manual retry button |
| Restore target version YAML missing | Toast "Version v<N> not available"; editor state unchanged |

## Source tag vocabulary

| Value | Meaning |
|---|---|
| `form_edit` | Existing in-form save (unchanged behavior) |
| `yaml_paste` | New: user saved via paste/edit dialog without invoking Restore |
| `rollback` | New: save that started from a Restore action (`source_detail` = `"from_v<N>"`) |

Existing `source_tag` column is free-form text; new tags added by convention only.

## Testing

**Backend:** no changes. Existing `test_configs.py` covers the three endpoints we consume.

**Frontend:** no test suite established. Manual verification:
1. Open dialog → view mode shows current YAML
2. Toggle edit → paste modified YAML with a type error (e.g. `learning_rate: "fast"`) → Save → schema errors render inline
3. Fix → Save → toast, forms re-hydrate, new version in history with `yaml_paste` pill
4. Click Restore on older version → editor loads it in edit mode → Save → new version with `rollback` pill
5. With unsaved edits, click Restore → confirm dialog, cancel preserves edits, confirm discards
6. Close dialog with unsaved edits → confirm dialog

## Out of scope (future)

- Diff viewer between arbitrary version pairs
- Export/import of YAML files
- Version pinning (preventing rollback past a checkpoint)
- Inline field-level YAML editing from form tabs
- Live validation on keystroke
