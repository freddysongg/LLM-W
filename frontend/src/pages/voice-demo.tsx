import * as React from "react";
import { useToast } from "@/hooks/use-toast";
import { useVoiceSession } from "@/hooks/use-voice-session";
import { VoiceSessionControls } from "@/components/voice/voice-session-controls";
import { VoiceTranscript } from "@/components/voice/voice-transcript";
import { VoiceToolTrace } from "@/components/voice/voice-tool-trace";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { describeApiError } from "@/lib/api-error";
import type { VoiceSessionCreateRequest } from "@/types/voice";

const DEFAULT_SYSTEM_PROMPT = `You are a helpful shopping assistant. Use the provided tools (search_products, get_product_detail, add_to_cart, handoff_checkout) to help the user find products and complete purchases. Always confirm cart changes before checkout.`;
const DEFAULT_VOICE_ID = "a0e99841-438c-4a64-b679-ae501e7d6091";
const DEFAULT_MODEL_ID = "gpt-4o-mini";

interface FormState {
  readonly systemPrompt: string;
  readonly voiceId: string;
  readonly modelId: string;
}

const INITIAL_FORM: FormState = {
  systemPrompt: DEFAULT_SYSTEM_PROMPT,
  voiceId: DEFAULT_VOICE_ID,
  modelId: DEFAULT_MODEL_ID,
};

export default function VoiceDemoPage(): React.JSX.Element {
  const [form, setForm] = React.useState<FormState>(INITIAL_FORM);
  const { status, transcript, toolTrace, session, lastError, start, stop } = useVoiceSession();
  const { toast } = useToast();

  const canStart = form.systemPrompt.trim().length > 0 && form.voiceId.trim().length > 0;

  React.useEffect(() => {
    if (lastError) {
      toast({
        title: "Voice session error",
        description: describeApiError({ cause: new Error(lastError), fallback: lastError }),
        variant: "destructive",
      });
    }
  }, [lastError, toast]);

  const handleStart = (): void => {
    const request: VoiceSessionCreateRequest = {
      system_prompt: form.systemPrompt,
      cartesia_voice_id: form.voiceId,
      openai_model_id: form.modelId,
    };
    void start(request);
  };

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
            Voice demo
          </h1>
          <p className="mt-1 font-mono text-[11px] text-ink-3">
            shopping assistant · pipecat pipeline · single browser session
          </p>
        </div>
        <VoiceSessionControls
          status={status}
          canStart={canStart}
          onStart={handleStart}
          onStop={stop}
        />
      </header>

      {session && (
        <div className="rounded border border-hairline bg-surface-1 px-3 py-2 font-mono text-[11px] text-ink-3">
          session: <span className="text-ink-1">{session.sessionId}</span> · artifact:{" "}
          <span className="text-ink-1">{session.artifactPath}</span>
        </div>
      )}

      <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[320px_1fr_320px]">
        <Card>
          <CardHeader>
            <CardTitle>Session config</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="voice-system-prompt">System prompt</Label>
              <Textarea
                id="voice-system-prompt"
                value={form.systemPrompt}
                onChange={(event) => setForm({ ...form, systemPrompt: event.target.value })}
                rows={8}
                className="font-mono text-[12px]"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="voice-voice-id">Cartesia voice id</Label>
              <Input
                id="voice-voice-id"
                value={form.voiceId}
                onChange={(event) => setForm({ ...form, voiceId: event.target.value })}
                className="font-mono text-[12px]"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="voice-model-id">OpenAI model id</Label>
              <Input
                id="voice-model-id"
                value={form.modelId}
                onChange={(event) => setForm({ ...form, modelId: event.target.value })}
                className="font-mono text-[12px]"
              />
            </div>
            <p className="pt-2 font-mono text-[10px] text-ink-3">
              Backend requires DEEPGRAM_API_KEY, CARTESIA_API_KEY, OPENAI_API_KEY env vars.
            </p>
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>Transcript</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-hidden">
            <VoiceTranscript entries={transcript} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Tool trace</CardTitle>
          </CardHeader>
          <CardContent>
            <VoiceToolTrace entries={toolTrace} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
