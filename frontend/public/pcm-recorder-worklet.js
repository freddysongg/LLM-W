/**
 * AudioWorklet that captures mic input and emits 16-bit PCM ArrayBuffers
 * to the main thread. The browser-side audio context must be created with
 * { sampleRate: 16000 } so no resampling is required here.
 */
class PCMRecorderProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channel = input[0];
    if (!channel) return true;

    const pcm16 = new Int16Array(channel.length);
    for (let i = 0; i < channel.length; i += 1) {
      const sample = Math.max(-1, Math.min(1, channel[i]));
      pcm16[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }

    const buffer = pcm16.buffer;
    this.port.postMessage(buffer, [buffer]);
    return true;
  }
}

registerProcessor("pcm-recorder", PCMRecorderProcessor);
