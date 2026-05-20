import type { VoiceSessionCreateRequest, VoiceSessionCreateResponse } from "@/types/voice";
import { fetchApi } from "./client";

export function createVoiceSession({
  request,
}: {
  request: VoiceSessionCreateRequest;
}): Promise<VoiceSessionCreateResponse> {
  return fetchApi<VoiceSessionCreateResponse>({
    path: `/voice/sessions`,
    method: "POST",
    body: request,
  });
}
