import * as React from "react";
import { useAppStore } from "@/stores/app-store";
import { useDatasetProfile, useResolveDataset } from "@/hooks/useDatasetProfile";
import { useDatasetSamples, usePreviewTransform } from "@/hooks/useDatasetSamples";
import type { DatasetResolveRequest, PreviewTransformResponse } from "@/types/dataset";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { DatasetSourceSelector } from "@/components/dataset/dataset-source-selector";
import { DatasetIdInput } from "@/components/dataset/dataset-id-input";
import { FormatSelector } from "@/components/dataset/format-selector";
import { FieldMappingEditor } from "@/components/dataset/field-mapping-editor";
import { FilterExpressionInput } from "@/components/dataset/filter-expression-input";
import { DatasetResolveButton } from "@/components/dataset/dataset-resolve-button";
import { SplitInfoCards } from "@/components/dataset/split-info-cards";
import { SamplePreview } from "@/components/dataset/sample-preview";
import { TokenStatsChart } from "@/components/dataset/token-stats-chart";
import { QualityWarnings } from "@/components/dataset/quality-warnings";
import { PreprocessingPreview } from "@/components/dataset/preprocessing-preview";

export default function DatasetsPage(): React.JSX.Element {
  const { activeProjectId, datasetForm, setDatasetForm } = useAppStore();
  const [previewResponse, setPreviewResponse] = React.useState<PreviewTransformResponse | null>(
    null,
  );

  const projectId = activeProjectId ?? "";

  const {
    data: profile,
    isLoading: isProfileLoading,
    error: profileError,
  } = useDatasetProfile({
    projectId,
  });

  const resolveDataset = useResolveDataset({ projectId });

  const { data: samplesResponse, isLoading: isSamplesLoading } = useDatasetSamples({
    projectId,
    enabled: profile !== undefined,
  });

  const previewTransform = usePreviewTransform({ projectId });

  React.useEffect(() => {
    if (profile && !datasetForm.datasetId) {
      setDatasetForm({ source: profile.source, datasetId: profile.datasetId, format: profile.format });
    }
  }, [profile, datasetForm.datasetId, setDatasetForm]);

  const handleResolve = (): void => {
    const request: DatasetResolveRequest = {
      source: datasetForm.source,
      datasetId: datasetForm.datasetId,
      subset: null,
      trainSplit: "train",
      evalSplit: "validation",
      format: datasetForm.format,
      formatMapping:
        Object.keys(datasetForm.formatMapping).length > 0 ? datasetForm.formatMapping : null,
    };
    resolveDataset.mutate(request);
  };

  const handlePreviewTransform = (): void => {
    previewTransform.mutate(
      {
        format: datasetForm.format,
        formatMapping:
          Object.keys(datasetForm.formatMapping).length > 0 ? datasetForm.formatMapping : null,
        sampleCount: 5,
      },
      {
        onSuccess: (response) => setPreviewResponse(response),
      },
    );
  };

  const isResolveDisabled = !datasetForm.datasetId.trim();

  if (!activeProjectId) {
    return (
      <div className="p-6">
        <h1 className="text-xl font-semibold mb-2">Datasets</h1>
        <p className="text-sm text-muted-foreground">Select a project to configure datasets.</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <h1 className="text-xl font-semibold">Datasets</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Dataset Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <DatasetSourceSelector
            value={datasetForm.source}
            onChange={(source) => setDatasetForm({ source })}
          />

          <DatasetIdInput
            source={datasetForm.source}
            value={datasetForm.datasetId}
            onChange={(datasetId) => setDatasetForm({ datasetId })}
          />

          <FormatSelector
            value={datasetForm.format}
            onChange={(format) => setDatasetForm({ format })}
          />

          {(datasetForm.format === "custom" || datasetForm.format === "sharegpt") && (
            <FieldMappingEditor
              mapping={datasetForm.formatMapping}
              onChange={(formatMapping) => setDatasetForm({ formatMapping })}
            />
          )}

          <FilterExpressionInput
            value={datasetForm.filterExpression}
            onChange={(filterExpression) => setDatasetForm({ filterExpression })}
          />

          {resolveDataset.error instanceof Error && (
            <p className="text-sm text-destructive">{resolveDataset.error.message}</p>
          )}

          <DatasetResolveButton
            isPending={resolveDataset.isPending}
            isDisabled={isResolveDisabled}
            onResolve={handleResolve}
          />
        </CardContent>
      </Card>

      {isProfileLoading && (
        <p className="text-sm text-muted-foreground">Loading dataset profile…</p>
      )}

      {profileError !== null && !resolveDataset.isPending && (
        <p className="text-sm text-muted-foreground">No dataset resolved yet for this project.</p>
      )}

      {profile !== undefined && (
        <div className="space-y-4">
          <Separator />

          <div className="space-y-1">
            <h2 className="text-sm font-medium">Dataset Profile</h2>
            <p className="text-xs text-muted-foreground">
              {profile.datasetId} &middot; {profile.source} &middot; {profile.format}
            </p>
          </div>

          <SplitInfoCards splitCounts={profile.splitCounts} totalRows={profile.totalRows} />

          <QualityWarnings
            warnings={profile.qualityWarnings}
            duplicateCount={profile.duplicateCount}
            malformedCount={profile.malformedCount}
          />

          {profile.tokenStats !== null && <TokenStatsChart tokenStats={profile.tokenStats} />}

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Sample Preview</CardTitle>
            </CardHeader>
            <CardContent>
              {isSamplesLoading && (
                <p className="text-xs text-muted-foreground">Loading samples…</p>
              )}
              {samplesResponse !== undefined && (
                <SamplePreview
                  samples={samplesResponse.samples}
                  detectedFields={profile.detectedFields}
                />
              )}
            </CardContent>
          </Card>

          <PreprocessingPreview
            format={datasetForm.format}
            isPending={previewTransform.isPending}
            response={previewResponse}
            onPreview={handlePreviewTransform}
          />
        </div>
      )}
    </div>
  );
}
