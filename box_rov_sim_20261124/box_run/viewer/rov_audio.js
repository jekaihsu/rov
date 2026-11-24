/**
 * ROV-01 Asset-Free Procedural Underwater Web Audio Synthesizer (Wave 3)
 * Synthesizes 5 real-time physical audio cues using Web Audio API:
 *   1. Thruster RPM low-frequency vortex rumble (continuous sawtooth/triangle + LPF)
 *   2. Collision metallic hull thud (transient FM impact + lowpass resonance)
 *   3. Sonar ping pulse (1.85 kHz -> 1.25 kHz exponential chirp + underwater reverb tail)
 *   4. UT coupling lock chime (dual-tone harmonic confirmation 880 Hz -> 1320 Hz)
 *   5. Emergency alarm buzzer (alternating 640 Hz / 920 Hz tactical warning)
 */

export class RovProceduralAudio {
  constructor() {
    this.ctx = null;
    this.enabled = false;
    this.thrusterOsc = null;
    this.thrusterSubOsc = null;
    this.thrusterFilter = null;
    this.thrusterGain = null;
    this.lastRpmNorm = 0;
    this.lastCollisionCount = 0;
    this.lastUtState = 'ut_searching';
    this.lastAlarmAt = 0;
    this.eventCounts = {
      thrusterUpdates: 0,
      collisionThuds: 0,
      sonarPings: 0,
      utLockChimes: 0,
      emergencyAlarms: 0,
    };
  }

  init() {
    if (this.ctx) {
      if (this.ctx.state === 'suspended') {
        this.ctx.resume().catch(() => {});
      }
      this.enabled = true;
      return true;
    }
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return false;
    try {
      this.ctx = new AudioCtx();
      this.thrusterOsc = this.ctx.createOscillator();
      this.thrusterSubOsc = this.ctx.createOscillator();
      this.thrusterFilter = this.ctx.createBiquadFilter();
      this.thrusterGain = this.ctx.createGain();

      this.thrusterOsc.type = 'sawtooth';
      this.thrusterOsc.frequency.value = 48;
      this.thrusterSubOsc.type = 'triangle';
      this.thrusterSubOsc.frequency.value = 24;

      this.thrusterFilter.type = 'lowpass';
      this.thrusterFilter.frequency.value = 130;
      this.thrusterFilter.Q.value = 2.4;

      this.thrusterGain.gain.value = 0.0;

      this.thrusterOsc.connect(this.thrusterFilter);
      this.thrusterSubOsc.connect(this.thrusterFilter);
      this.thrusterFilter.connect(this.thrusterGain);
      this.thrusterGain.connect(this.ctx.destination);

      this.thrusterOsc.start();
      this.thrusterSubOsc.start();
      this.enabled = true;
      return true;
    } catch (_) {
      return false;
    }
  }

  updateThrusterRumble(thrustArray = [0, 0, 0, 0, 0, 0], healthArray = [1, 1, 1, 1, 1, 1]) {
    if (!this.enabled && !this.init()) return;
    const active = thrustArray.map((t, i) => Math.abs(Number(t) || 0) * ((healthArray[i] ?? 1) > 0.15 ? 1 : 0));
    const meanThrust = active.reduce((a, b) => a + b, 0) / Math.max(1, active.length);
    const peakThrust = Math.max(0, ...active);
    const rpmNorm = Math.min(1, 0.65 * peakThrust + 0.35 * meanThrust);
    this.lastRpmNorm = Number(rpmNorm.toFixed(3));
    this.eventCounts.thrusterUpdates += 1;

    if (this.ctx && this.thrusterOsc && this.thrusterGain) {
      const now = this.ctx.currentTime;
      const baseFreq = 42 + rpmNorm * 96;
      this.thrusterOsc.frequency.setTargetAtTime(baseFreq, now, 0.05);
      this.thrusterSubOsc.frequency.setTargetAtTime(baseFreq * 0.5, now, 0.05);
      this.thrusterFilter.frequency.setTargetAtTime(110 + rpmNorm * 260, now, 0.06);
      this.thrusterGain.gain.setTargetAtTime(rpmNorm * 0.08, now, 0.06);
    }
  }

  playCollisionThud(speedMps = 0.85) {
    if (!this.enabled && !this.init()) return;
    this.eventCounts.collisionThuds += 1;
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const filter = this.ctx.createBiquadFilter();
    const gain = this.ctx.createGain();

    const intensity = Math.min(1.5, Math.max(0.25, Number(speedMps) || 0.85));
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(135 * intensity, now);
    osc.frequency.exponentialRampToValueAtTime(28, now + 0.32);

    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(280, now);
    filter.Q.setValueAtTime(4.5, now);

    gain.gain.setValueAtTime(Math.min(0.25, 0.14 * intensity), now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.34);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(now);
    osc.stop(now + 0.35);
  }

  playSonarPing() {
    if (!this.enabled && !this.init()) return;
    this.eventCounts.sonarPings += 1;
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(1850, now);
    osc.frequency.exponentialRampToValueAtTime(1280, now + 0.18);

    gain.gain.setValueAtTime(0.08, now);
    gain.gain.exponentialRampToValueAtTime(0.0008, now + 0.42);

    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(now);
    osc.stop(now + 0.44);
  }

  playUtCouplingChime() {
    if (!this.enabled && !this.init()) return;
    this.eventCounts.utLockChimes += 1;
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    [880, 1320].forEach((freq, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      const t0 = now + idx * 0.09;
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, t0);
      gain.gain.setValueAtTime(0.09, t0);
      gain.gain.exponentialRampToValueAtTime(0.001, t0 + 0.24);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(t0);
      osc.stop(t0 + 0.25);
    });
  }

  playEmergencyAlarm() {
    if (!this.enabled && !this.init()) return;
    this.eventCounts.emergencyAlarms += 1;
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    [640, 920].forEach((freq, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      const t0 = now + idx * 0.11;
      osc.type = 'square';
      osc.frequency.setValueAtTime(freq, t0);
      gain.gain.setValueAtTime(0.06, t0);
      gain.gain.exponentialRampToValueAtTime(0.001, t0 + 0.10);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(t0);
      osc.stop(t0 + 0.11);
    });
  }

  syncWithTelemetry(s) {
    if (!s) return;
    this.updateThrusterRumble(s.thrust || [0, 0, 0, 0, 0, 0], s.health || [1, 1, 1, 1, 1, 1]);
    const w1 = s.wave1;
    if (!w1) return;
    const colCount = w1.hazards?.collision_count || 0;
    if (colCount > this.lastCollisionCount) {
      this.lastCollisionCount = colCount;
      this.playCollisionThud(0.95);
    }
    const utState = w1.wave3?.ut_state || 'ut_searching';
    if (utState === 'ut_coupled_lock' && this.lastUtState !== 'ut_coupled_lock') {
      this.playUtCouplingChime();
    }
    this.lastUtState = utState;

    const mode = w1.mode_state || 'normal';
    const nowMs = performance.now();
    if (mode !== 'normal' && nowMs - this.lastAlarmAt > 2800) {
      this.lastAlarmAt = nowMs;
      this.playEmergencyAlarm();
    }
  }

  getStatus() {
    return {
      enabled: this.enabled,
      contextState: this.ctx ? this.ctx.state : 'uninitialized',
      lastRpmNorm: this.lastRpmNorm,
      eventCounts: { ...this.eventCounts },
    };
  }
}

export const rovAudio = new RovProceduralAudio();
if (typeof window !== 'undefined') {
  window.rovAudio = rovAudio;
  window.ROVAudio = rovAudio;
}
