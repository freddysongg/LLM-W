import * as React from "react";
import { useAppStore } from "@/stores/app-store";
import { useModelProfile, useModelArchitecture, useResolveModel } from "@/hooks/useModelProfile";
import { ModelSourceSelector } from "@/components/model/model-source-selector";
import { ModelIdInput } from "@/components/model/model-id-input";
import { ModelResolveButton } from "@/components/model/model-resolve-button";
import { ModelProfileCard } from "@/components/model/model-profile-card";
import { TokenizerInfo } from "@/components/model/tokenizer-info";
import { CapabilityBadges } from "@/components/model/capability-badges";
import { ResourceEstimateCard } from "@/components/model/resource-estimate-card";
import { LayerSummaryTable } from "@/components/model/layer-summary-table";
import { Card, CardContent } from "@/components/ui/card";
import { CopyForAI } from "@/components/shared/copy-for-ai";
import { buildModelPrompt } from "@/lib/ai-copy-prompts";
import type { ModelSource } from "@/types/model";

export default function ModelsPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const projectId = activeProjectId ?? "";

  const { data: profile, isLoading: isLoadingProfile } = useModelProfile({ projectId });
  const { data: architecture } = useModelArchitecture({ projectId });
  const resolveModel = useResolveModel();

  const [source, setSource] = React.useState<ModelSource>("huggingface");
  const [modelId, setModelId] = React.useState("");

  const handleResolve = (): void => {
    if (!projectId || !modelId.trim()) return;
    resolveModel.mutate({ projectId, request: { source, model_id: modelId.trim() } });
  };

  const canResolve = Boolean(projectId) && modelId.trim().length > 0;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between h-14 px-6 border-b">
        <h1 className="text-xl font-semibold">Models</h1>
        {profile && architecture && (
          <CopyForAI buildPrompt={() => buildModelPrompt({ profile, architecture })} />
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {!activeProjectId && (
          <div className="text-sm text-muted-foreground">Select a project to resolve a model.</div>
        )}

        {activeProjectId && (
          <>
            <Card>
              <CardContent className="pt-6 space-y-4">
                <div className="space-y-1.5">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Source
                  </p>
                  <ModelSourceSelector source={source} onChange={setSource} />
                </div>
                <div className="space-y-1.5">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Model ID
                  </p>
                  <ModelIdInput
                    source={source}
                    value={modelId}
                    onChange={setModelId}
                    isDisabled={resolveModel.isPending}
                  />
                </div>
                <div className="flex items-center gap-3">
                  <ModelResolveButton
                    onResolve={handleResolve}
                    isResolving={resolveModel.isPending}
                    isDisabled={!canResolve}
                  />
                  {resolveModel.isError && (
                    <span className="text-sm text-destructive">
                      {resolveModel.error instanceof Error
                        ? resolveModel.error.message
                        : "Resolution failed"}
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>

            {isLoadingProfile && (
              <div className="text-sm text-muted-foreground py-4">Loading model profile...</div>
            )}

            {profile && (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <ModelProfileCard profile={profile} />
                  <TokenizerInfo profile={profile} />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <ResourceEstimateCard estimate={profile.resource_estimate} />
                  <Card>
                    <CardContent className="pt-6">
                      <CapabilityBadges profile={profile} />
                    </CardContent>
                  </Card>
                </div>

                {architecture && <LayerSummaryTable architecture={architecture} />}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
