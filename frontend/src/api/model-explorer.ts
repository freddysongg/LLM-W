import type {
  ModelArchitectureResponse,
  LayerDetailResponse,
  ActivationCaptureRequest,
  ActivationSnapshotResponse,
  FullTensorRequest,
  FullTensorResponse,
} from "@/types/model";
import { fetchApi } from "./client";

export async function fetchModelArchitecture({
  projectId,
}: {
  projectId: string;
}): Promise<ModelArchitectureResponse> {
  return fetchApi<ModelArchitectureResponse>({
    path: `/projects/${projectId}/models/architecture`,
  });
}

export async function fetchLayerDetail({
  projectId,
  layerName,
}: {
  projectId: string;
  layerName: string;
}): Promise<LayerDetailResponse> {
  return fetchApi<LayerDetailResponse>({
    path: `/projects/${projectId}/models/layers/${layerName}`,
  });
}

export async function captureActivations({
  projectId,
  request,
}: {
  projectId: string;
  request: ActivationCaptureRequest;
}): Promise<ActivationSnapshotResponse> {
  return fetchApi<ActivationSnapshotResponse>({
    path: `/projects/${projectId}/models/activations`,
    method: "POST",
    body: request,
  });
}

export async function fetchActivationSnapshot({
  projectId,
  snapshotId,
}: {
  projectId: string;
  snapshotId: string;
}): Promise<ActivationSnapshotResponse> {
  return fetchApi<ActivationSnapshotResponse>({
    path: `/projects/${projectId}/models/activations/${snapshotId}`,
  });
}

export async function requestFullTensor({
  projectId,
  snapshotId,
  request,
}: {
  projectId: string;
  snapshotId: string;
  request: FullTensorRequest;
}): Promise<FullTensorResponse> {
  return fetchApi<FullTensorResponse>({
    path: `/projects/${projectId}/models/activations/${snapshotId}/full`,
    method: "POST",
    body: request,
  });
}
