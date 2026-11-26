// Synthesised UI ticks (no audio files). The AudioContext is created only after sounds are enabled.
export type SoundKind = 'move' | 'select' | 'back' | 'success' | 'error';

let ctx: AudioContext | null = null;
let enabled = false;
let volume = 0.6;

export function configureSound(on: boolean, vol: number) {
  enabled = on;
  volume = Math.max(0, Math.min(1, vol / 100));
  if (!on && ctx) { void ctx.close(); ctx = null; }
}

const shapes: Record<SoundKind, Array<[number, number, number]>> = {
  move: [[880, 0, 0.035]],
  select: [[660, 0, 0.05], [990, 0.045, 0.06]],
  back: [[520, 0, 0.05], [390, 0.04, 0.06]],
  success: [[660, 0, 0.06], [880, 0.06, 0.06], [1320, 0.12, 0.09]],
  error: [[240, 0, 0.09], [200, 0.08, 0.12]],
};

export function playSound(kind: SoundKind) {
  if (!enabled || volume === 0) return;
  try {
    ctx ??= new AudioContext();
    const now = ctx.currentTime;
    for (const [freq, at, len] of shapes[kind]) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, now + at);
      gain.gain.setValueAtTime(0, now + at);
      gain.gain.linearRampToValueAtTime(0.08 * volume, now + at + 0.008);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + at + len);
      osc.connect(gain).connect(ctx.destination);
      osc.start(now + at);
      osc.stop(now + at + len + 0.02);
    }
  } catch { /* audio unavailable: silent */ }
}
