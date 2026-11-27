// Synthesized topside and underwater buses with gesture-safe browser lifecycle.
// Topside (reel, deck, App cues) is always available; underwater thrusters and impacts follow fidelity.
import {
  clamp, motorPan, freshContacts, impactEnvelope, motorParameters, depthCutoff,
  detectEvents, resolveCue, reelParameters, topsideAmbience, takeContactHit
} from './mapping.js';
import {lineLoad} from '../tether/feel.js';
import {getFidelity} from '../fidelity.js';
import '../story/feel_settings.js';
import {underwaterAudioEnabled} from './fidelity.js';
import { audioStore } from '../saves/registry.js';

const STRINGS = {
  title: '音效',
  master: '主音量',
  vehicle: '載具',
  environment: '環境',
  ui: '介面',
  warning: '警告',
  music: '音樂',
  voice: '語音',
  mute: '靜音'
};
const DEFAULTS = {
  master: 0.65, vehicle: 0.7, environment: 0.5, ui: 0.55, warning: 0.65, music: 0.5, voice: 0.8, mute: false
};

const KEY = 'rov.audio';
let sharedEngine;

export function installAudio(options = {}) {
  if (!sharedEngine) sharedEngine = new AudioEngine(options);
  Object.assign(sharedEngine.options, options);
  return sharedEngine;
}

class AudioEngine {
  constructor(options) {
    this.options = options;
    this.settings = { ...DEFAULTS };
    const loaded = audioStore.load();
    if (!loaded.recovered && loaded.reason !== 'empty') {
      for (const key of Object.keys(DEFAULTS)) {
        if (typeof loaded.value?.[key] === typeof DEFAULTS[key]) this.settings[key] = loaded.value[key];
      }
    }
    this.forcedMute = new URLSearchParams(location.search).has('mute');
    this.controls = [];
    this.cueListeners = [];
    this.motors = [];
    this.peers = new Map();
    this.nextLife = 0;
    document.addEventListener('pointerdown', () => this.start());
    document.addEventListener('keydown', () => this.start());
    document.addEventListener('visibilitychange', () => this.mix());
    document.addEventListener('focusin', event => {
      if (event.target.matches('button,select,input,summary')) this.cue('move');
    });
    document.addEventListener('click', event => {
      if (event.target.closest('button,summary')) {
        this.start();
        this.cue('confirm');
      }
    });
    document.addEventListener('keydown', event => {
      if (event.code === 'Escape') this.cue('back');
    });
  }

  set(key, value) {
    this.settings[key] = key === 'mute' ? !!value : clamp(value);
    audioStore.save(this.settings);
    for (const control of this.controls) {
      control.input.value = this.settings[control.key];
      control.input.checked = this.settings.mute;
    }
    this.mix();
  }

  start() {
    if (this.forcedMute) return;
    try {
      if (!this.ctx) this.build();
      if (this.ctx?.state === 'suspended') this.ctx.resume().catch(() => {});
    } catch {
      // Audio is optional on unsupported browsers and offline renderers.
    }
  }

  smooth(param, value, seconds = 0.12) {
    param.setTargetAtTime(value, this.ctx.currentTime, seconds);
  }

  build() {
    const Context = globalThis.AudioContext || globalThis.webkitAudioContext;
    if (!Context) return;
    this.ctx = new Context();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0;
    const limiter = this.ctx.createDynamicsCompressor();
    this.master.connect(limiter).connect(this.ctx.destination);
    this.buses = {};
    for (const key of ['vehicle', 'environment', 'ui', 'warning', 'music', 'voice']) {
      const bus = this.ctx.createGain();
      bus.connect(this.master);
      this.buses[key] = bus;
    }
    this.noise = this.ctx.createBuffer(1, this.ctx.sampleRate * 2, this.ctx.sampleRate);
    const samples = this.noise.getChannelData(0);
    let brown = 0;
    for (let i = 0; i < samples.length; i++) {
      brown = (brown + (Math.random() * 2 - 1) * 0.02) / 1.02;
      samples[i] = brown * 3.5;
    }
    this.strain = this.noiseLayer(0, 720, this.buses.vehicle);
    this.water = this.noiseLayer(0, 1000);
    this.waves = this.noiseLayer(0, 1800);
    this.flow = this.noiseLayer(0, 450);
    this.fan = this.noiseLayer(0.03, 900);
    this.deck = this.noiseLayer(0.04, 280);
    this.reelMotor = this.motor(this.buses.vehicle);
    this.brake = this.noiseLayer(0, 520, this.buses.vehicle);
    this.fairlead = this.noiseLayer(0, 1400, this.buses.vehicle);
    this.mix();
  }

  noiseLayer(gain, cutoff, destination = this.buses.environment) {
    const source = this.ctx.createBufferSource();
    source.buffer = this.noise;
    source.loop = true;
    const filter = this.ctx.createBiquadFilter();
    filter.frequency.value = cutoff;
    const level = this.ctx.createGain();
    level.gain.value = gain;
    source.connect(filter).connect(level).connect(destination);
    source.start();
    return {source, filter, level};
  }

  motor(destination) {
    const oscillator = this.ctx.createOscillator();
    const filter = this.ctx.createBiquadFilter();
    filter.frequency.value = 650;
    const level = this.ctx.createGain();
    level.gain.value = 0;
    oscillator.connect(filter).connect(level).connect(destination);
    oscillator.start();
    const noise = this.noiseLayer(0, 700, destination);
    return {oscillator, level, noise};
  }

  drive(motor, output, scale = 1) {
    const parameters = motorParameters(output);
    motor.oscillator.type = parameters.type;
    this.smooth(motor.oscillator.frequency, parameters.frequency);
    this.smooth(motor.level.gain, parameters.gain * scale);
    this.smooth(motor.noise.level.gain, parameters.gain * scale * 0.7);
  }

  isPaused() {
    return !!(this.state?.paused || this.options.isPaused?.());
  }

  underwaterOn() {
    return underwaterAudioEnabled(this.options.fidelity);
  }

  mix() {
    if (!this.ctx) return;
    const silent = this.settings.mute || this.forcedMute || document.hidden || this.isPaused();
    const targets = {master: silent ? 0 : clamp(this.settings.master)};
    for (const key of Object.keys(this.buses)) targets[key] = clamp(this.settings[key]);
    for (const [key, value] of Object.entries(targets)) {
      if (this.mixTargets?.[key] === value) continue;
      const gain = key === 'master' ? this.master.gain : this.buses[key].gain;
      this.smooth(gain, value);
    }
    this.mixTargets = targets;
  }

  enabled(id) {
    return (this.options.fidelity || getFidelity()).get(id);
  }

  cue(kind, layer = 'topside', hit = null) {
    if (!this.ctx || this.ctx.state !== 'running' || document.hidden || this.isPaused()) return;
    if (layer === 'underwater' && !this.underwaterOn()) return;
    if (hit && !this.enabled('contactSound')) return;
    if (['switch', 'shutter'].includes(kind) && !this.enabled('switchSound')) return;
    for (const listener of this.cueListeners) listener(kind);
    if (hit) {
      this.impact(impactEnvelope(hit, this.options.getWorld?.()?.obstacles));
      return;
    }
    if (kind === 'switch') {
      this.impact({gain: 0.09, cutoff: 1800, decay: 0.045}, this.buses.ui);
      return;
    }
    if (kind === 'shutter') {
      this.shutter();
      return;
    }
    const severity = {touch: 1, hard: 2, severe: 3, warn: 2, broken: 3}[kind];
    const frequency = severity ? 320 - severity * 45
      : kind === 'move' ? 420
        : kind === 'back' ? 300
          : kind === 'photos' ? 900
            : kind === 'record' ? 720
              : 540;
    const notes = kind === 'life' ? [180 + Math.random() * 140]
      : kind === 'complete' ? [390, 490, 590]
        : kind === 'record' ? [frequency, frequency * 0.78]
          : [frequency];
    for (const [index, note] of notes.entries()) {
      const at = this.ctx.currentTime + index * 0.14;
      const oscillator = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      oscillator.frequency.value = note;
      oscillator.type = 'sine';
      gain.gain.setValueAtTime(0, at);
      gain.gain.linearRampToValueAtTime(severity ? 0.16 : 0.07, at + 0.008);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + (severity ? 0.32 : 0.09));
      const bus = kind === 'life' ? this.buses.environment : severity ? this.buses.warning : this.buses.ui;
      oscillator.connect(gain).connect(bus);
      if (kind === 'life') oscillator.frequency.exponentialRampToValueAtTime(note * 0.6, at + 0.3);
      oscillator.start(at);
      oscillator.stop(at + 0.4);
      oscillator.onended = function disconnect() {
        oscillator.disconnect();
        gain.disconnect();
      };
    }
  }

  // The topside App's camera shutter: two short filtered clicks. The viewer plays it when the photo is captured and
  // the simulator's photo counter echoes it a moment later, so a second request inside the window is dropped.
  shutter() {
    const at = this.ctx.currentTime;
    if (at - (this.lastShutter ?? -10) < 1.5) return;
    this.lastShutter = at;
    for (const offset of [0, 0.07]) {
      const click = this.noiseLayer(0, 5200, this.buses.ui);
      click.level.gain.setValueAtTime(0.0001, at + offset);
      click.level.gain.linearRampToValueAtTime(0.16, at + offset + 0.004);
      click.level.gain.exponentialRampToValueAtTime(0.0001, at + offset + 0.045);
      click.source.stop(at + offset + 0.1);
      click.source.onended = function disconnect() {
        click.source.disconnect();
        click.filter.disconnect();
        click.level.disconnect();
      };
    }
  }

  impact({gain, cutoff, decay}, bus = this.buses.vehicle) {
    const layerRef = this.noiseLayer(0, cutoff, bus);
    const at = this.ctx.currentTime;
    layerRef.level.gain.setValueAtTime(gain, at);
    layerRef.level.gain.exponentialRampToValueAtTime(0.0001, at + decay);
    layerRef.source.stop(at + 0.4);
    layerRef.source.onended = function disconnect() {
      layerRef.source.disconnect();
      layerRef.filter.disconnect();
      layerRef.level.disconnect();
    };
  }

  updateTopside(state) {
    const ambience = topsideAmbience();
    const reel = reelParameters(state.tether?.reel);
    this.smooth(this.fan.level.gain, ambience.fanGain);
    this.smooth(this.deck.level.gain, ambience.deckGain);
    this.reelMotor.oscillator.type = 'sawtooth';
    this.smooth(this.reelMotor.oscillator.frequency, reel.motorHz);
    this.smooth(this.reelMotor.level.gain, reel.motorGain);
    this.smooth(this.reelMotor.noise.level.gain, reel.motorGain * 0.55);
    this.smooth(this.brake.level.gain, reel.brakeGain);
    this.smooth(this.fairlead.level.gain, reel.fairleadGain);
    this.smooth(this.fairlead.filter.frequency, 900 + reel.speed * 1200);
  }

  updateUnderwater(state, scale) {
    const thrust = state.thrust || [];
    const world = this.options.getWorld?.();
    const vehicle = world?.vehicle_catalogue?.find(entry => entry.id === state.model_id);
    const mounts = vehicle?.thrusters || world?.thrusters;
    while (this.motors.length < thrust.length) {
      const pan = this.ctx.createStereoPanner();
      pan.connect(this.buses.vehicle);
      this.motors.push({...this.motor(pan), pan});
    }
    this.motors.forEach((motor, index) => {
      motor.pan.pan.value = motorPan(mounts?.[index]);
      const output = state.locked || !this.enabled('motorSound') || scale <= 0 ? 0 : thrust[index] || 0;
      this.drive(motor, output, scale / Math.sqrt(thrust.length || 1));
    });
    const depth = state.pos?.[2] || 0;
    const wet = scale > 0 && this.enabled('waterSound') ? 1 : 0;
    const tether = state.tether;
    const load = clamp(lineLoad(tether) / 120);
    const strain = this.enabled('strainSound') && !tether?.broken ? scale * clamp((load - 0.12) / 0.88) : 0;
    this.smooth(this.strain.level.gain, strain * 0.38, 0.06);
    this.smooth(this.strain.filter.frequency, 450 + load * 1950);
    this.smooth(this.water.filter.frequency, depthCutoff(depth));
    this.smooth(this.water.level.gain, 0.15 * (1 - Math.exp(-Math.max(0, depth) / 1.5)) * wet);
    this.smooth(this.waves.level.gain, 0.22 * Math.exp(-Math.max(0, depth) / 1.5) * wet);
    this.smooth(this.flow.level.gain, clamp(Math.hypot(...(state.current_here || [])) / 2) * 0.22 * wet);
    if (wet && this.ctx.currentTime > this.nextLife && !this.isPaused()) {
      this.nextLife = this.ctx.currentTime + 14 + Math.random() * 25;
      this.cue('life', 'underwater');
    }
  }

  update(state) {
    const hits = state ? freshContacts(this.previous, state) : [];
    const events = state ? detectEvents(this.previous, state, hits) : [];
    this.previous = state;
    this.state = state;
    if (!this.ctx || !state) return;
    const paused = this.isPaused();
    if (paused !== this.paused) {
      this.paused = paused;
      this.mix();
    }
    for (const event of events) {
      const resolved = resolveCue(event, state);
      const hit = takeContactHit(hits, event);
      const mechanical = event === 'light' || (event === 'locked' && !state.locked);
      this.cue(mechanical ? 'switch' : resolved.kind, resolved.layer, hit);
    }
    this.updateTopside(state);
    const onboard = this.options.getMode?.() === 'onboard';
    const underwater = this.underwaterOn();
    this.updateUnderwater(state, underwater ? (onboard ? 1 : 0.6) : 0);
    if (underwater && this.enabled('motorSound')) this.spatial(state);
    else this.clearPeers();
  }

  clearPeers() {
    for (const [, peer] of this.peers) {
      peer.motor.oscillator.stop();
      peer.motor.noise.source.stop();
      peer.motor.oscillator.disconnect();
      peer.motor.noise.source.disconnect();
      peer.motor.level.disconnect();
      peer.motor.noise.level.disconnect();
      peer.panner.disconnect();
    }
    this.peers.clear();
  }

  spatial(state) {
    const camera = this.options.getCamera?.();
    const listener = this.ctx.listener;
    if (camera && listener.positionX) {
      const matrix = camera.matrixWorld.elements;
      for (const [axis, index] of [['X', 0], ['Y', 1], ['Z', 2]]) {
        listener['position' + axis].value = camera.position[axis.toLowerCase()];
        listener['forward' + axis].value = -matrix[8 + index];
        listener['up' + axis].value = matrix[4 + index];
      }
    }
    const seen = new Set();
    for (const vehicle of state.vehicles || []) {
      if (vehicle.id === state.vehicle_id || vehicle.vehicle_id === state.vehicle_id) continue;
      const id = vehicle.id || vehicle.vehicle_id;
      seen.add(id);
      if (!this.peers.has(id)) {
        const panner = this.ctx.createPanner();
        panner.panningModel = 'HRTF';
        panner.refDistance = 2;
        panner.maxDistance = 100;
        panner.connect(this.buses.vehicle);
        this.peers.set(id, {panner, motor: this.motor(panner)});
      }
      const peer = this.peers.get(id);
      const [north, east, down] = vehicle.pos || [0, 0, 0];
      peer.panner.setPosition(-east, -down, north);
      const outputs = vehicle.thrust || [];
      this.drive(peer.motor, vehicle.locked ? 0 : Math.max(0, ...outputs.map(Math.abs)), 0.6);
    }
    for (const [id, peer] of this.peers) {
      if (seen.has(id)) continue;
      peer.motor.oscillator.stop();
      peer.motor.noise.source.stop();
      peer.motor.oscillator.disconnect();
      peer.motor.noise.source.disconnect();
      peer.motor.level.disconnect();
      peer.motor.noise.level.disconnect();
      peer.panner.disconnect();
      this.peers.delete(id);
    }
  }
}

export function installAudioSettings(engine, parent) {
  const section = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = STRINGS.title;
  section.append(summary);
  for (const key of ['master', 'vehicle', 'environment', 'ui', 'warning', 'music', 'voice', 'mute']) {
    const label = document.createElement('label');
    label.textContent = STRINGS[key];
    const input = document.createElement('input');
    input.type = key === 'mute' ? 'checkbox' : 'range';
    input.setAttribute('aria-label', STRINGS[key]);
    input.min = 0;
    input.max = 1;
    input.step = 0.01;
    input.value = engine.settings[key];
    input.checked = engine.settings.mute;
    input.addEventListener('input', function changeVolume() {
      engine.set(key, key === 'mute' ? input.checked : Number(input.value));
    });
    engine.controls.push({key, input});
    label.append(input);
    section.append(label);
  }
  parent.append(section);
}
