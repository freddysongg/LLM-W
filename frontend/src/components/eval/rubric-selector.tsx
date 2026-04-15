import * as React from "react";
import { Check } from "lucide-react";
import type { Rubric, RubricVersion } from "@/types/eval";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface RubricSelectorProps {
  readonly rubrics: ReadonlyArray<Rubric>;
  readonly selectedVersionIds: ReadonlyArray<string>;
  readonly onToggleVersion: (rubricVersionId: string) => void;
  readonly showUncalibrated: boolean;
  readonly onToggleShowUncalibrated: (showUncalibrated: boolean) => void;
}

interface SelectableVersion {
  readonly rubric: Rubric;
  readonly version: RubricVersion;
  readonly isLatest: boolean;
}

function buildLatestVersionsByRubric(
  rubrics: ReadonlyArray<Rubric>,
): ReadonlyArray<SelectableVersion> {
  const selectable: SelectableVersion[] = [];
  for (const rubric of rubrics) {
    if (rubric.versions.length === 0) continue;
    const latest = rubric.versions.reduce<RubricVersion>(
      (accumulated, candidate) =>
        candidate.versionNumber > accumulated.versionNumber ? candidate : accumulated,
      rubric.versions[0],
    );
    for (const version of rubric.versions) {
      selectable.push({
        rubric,
        version,
        isLatest: version.id === latest.id,
      });
    }
  }
  return selectable;
}

function filterVersions({
  selectable,
  showUncalibrated,
}: {
  selectable: ReadonlyArray<SelectableVersion>;
  showUncalibrated: boolean;
}): ReadonlyArray<SelectableVersion> {
  return selectable.filter((candidate) => {
    if (!candidate.isLatest) return false;
    if (showUncalibrated) return true;
    return candidate.version.calibrationStatus === "calibrated";
  });
}

export function RubricSelector({
  rubrics,
  selectedVersionIds,
  onToggleVersion,
  showUncalibrated,
  onToggleShowUncalibrated,
}: RubricSelectorProps): React.JSX.Element {
  const selectable = React.useMemo(() => buildLatestVersionsByRubric(rubrics), [rubrics]);
  const visible = React.useMemo(
    () => filterVersions({ selectable, showUncalibrated }),
    [selectable, showUncalibrated],
  );
  const selectedSet = React.useMemo(() => new Set(selectedVersionIds), [selectedVersionIds]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">Rubrics</div>
        <button
          type="button"
          className="text-xs text-muted-foreground hover:text-foreground"
          onClick={() => onToggleShowUncalibrated(!showUncalibrated)}
        >
          {showUncalibrated ? "Hide uncalibrated" : "Show uncalibrated"}
        </button>
      </div>
      {visible.length === 0 ? (
        <div className="text-xs text-muted-foreground">
          {showUncalibrated
            ? "No rubrics available."
            : "No calibrated rubrics. Toggle to show uncalibrated versions."}
        </div>
      ) : (
        <ul className="space-y-1.5">
          {visible.map(({ rubric, version }) => {
            const isSelected = selectedSet.has(version.id);
            return (
              <li key={version.id}>
                <button
                  type="button"
                  onClick={() => onToggleVersion(version.id)}
                  className={cn(
                    "w-full flex items-start gap-3 rounded-md border px-3 py-2 text-left transition-colors",
                    isSelected ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40",
                  )}
                >
                  <div
                    className={cn(
                      "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                      isSelected ? "border-primary bg-primary" : "border-muted-foreground/40",
                    )}
                  >
                    {isSelected && <Check className="h-3 w-3 text-primary-foreground" />}
                  </div>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{rubric.name}</span>
                      <span className="text-xs text-muted-foreground">
                        v{version.versionNumber}
                      </span>
                      <Badge
                        variant={
                          version.calibrationStatus === "calibrated" ? "secondary" : "outline"
                        }
                      >
                        {version.calibrationStatus}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground line-clamp-2">
                      {rubric.description}
                    </div>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
