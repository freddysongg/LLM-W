import { useMutation } from "@tanstack/react-query";
import { captureActivations, requestFullTensor } from "@/api/model-explorer";

export function useCaptureActivations({ projectId }: { projectId: string }) {
  return useMutation({
    mutationFn: ({
      layerNames,
      sampleInput,
    }: {
      layerNames: ReadonlyArray<string>;
      sampleInput: string;
    }) =>
      captureActivations({
        projectId,
        request: { layer_names: layerNames, sample_input: sampleInput },
      }),
  });
}

export function useRequestFullTensor({ projectId }: { projectId: string }) {
  return useMutation({
    mutationFn: ({
      snapshotId,
      layerNames,
    }: {
      snapshotId: string;
      layerNames: ReadonlyArray<string> | null;
    }) =>
      requestFullTensor({
        projectId,
        snapshotId,
        request: { layer_names: layerNames },
      }),
  });
}
