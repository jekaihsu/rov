// Radio dialogue voice clips: play an Opus file when a line appears, duck music via the existing
// radio UI hold, and fall back to text-only (plus ambient noise) when the clip is missing.
// Presentation layer only — not a fidelity item. Volume uses the engine `voice` bus.
// Why no fidelity item: the speakers are the boat crew (supervisor, tether hand, client) talking to the
// pilot over the deck radio, which a real pilot hears during a dive; it adds no capability the vehicle
// lacks. A voice that is not crew radio (narrator, AI co-pilot) would need registerFidelityItem().
import {createHash} from './voice_hash.js';

export const VOICE_BASE = new URL('./voice/', import.meta.url).href;

const STRINGS = {
  missing: 'voice clip missing',
};

let sharedVoice;
let indexCache = null;
let indexPromise = null;

export function lineId(language, speaker, text) {
  return createHash(`${language}\0${speaker}\0${text}`).slice(0, 20);
}

export function clipUrl(language, id, base = VOICE_BASE) {
  return `${base}${encodeURIComponent(language)}/${encodeURIComponent(id)}.opus`;
}

// Pure resolve: known ids from index.json win; unknown ids are treated as missing without fetching.
export function resolveClip(index, language, speaker, text) {
  if (!language || !speaker || !text) return null;
  const id = lineId(language, speaker, text);
  const list = index?.[language];
  if (!Array.isArray(list) || !list.includes(id)) {
    return {id, url: null, missing: true, reason: STRINGS.missing};
  }
  return {id, url: clipUrl(language, id), missing: false};
}

async function loadIndex(base) {
  if (indexCache) return indexCache;
  if (indexPromise) return indexPromise;
  indexPromise = fetch(new URL('index.json', base).href, {cache: 'no-cache'})
    .then(function parse(response) {
      if (!response.ok) return {};
      return response.json();
    })
    .catch(function empty() {
      return {};
    })
    .then(function store(data) {
      indexCache = data && typeof data === 'object' ? data : {};
      return indexCache;
    });
  return indexPromise;
}

function playStaticFallback(engine) {
  if (!engine?.ctx || engine.ctx.state !== 'running' || !engine.buses?.voice) return;
  const at = engine.ctx.currentTime;
  const source = engine.ctx.createBufferSource();
  const length = Math.floor(engine.ctx.sampleRate * 0.08);
  const buffer = engine.ctx.createBuffer(1, length, engine.ctx.sampleRate);
  const samples = buffer.getChannelData(0);
  for (let i = 0; i < length; i++) samples[i] = (Math.random() * 2 - 1) * (1 - i / length) * 0.2;
  source.buffer = buffer;
  const filter = engine.ctx.createBiquadFilter();
  filter.type = 'bandpass';
  filter.frequency.value = 1200;
  filter.Q.value = 0.7;
  const gain = engine.ctx.createGain();
  gain.gain.setValueAtTime(0.0001, at);
  gain.gain.linearRampToValueAtTime(0.12, at + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.08);
  source.connect(filter).connect(gain).connect(engine.buses.voice);
  source.start(at);
  source.stop(at + 0.1);
  source.onended = function disconnect() {
    source.disconnect();
    filter.disconnect();
    gain.disconnect();
  };
}

function createController() {
  let engine = null;
  let music = null;
  let base = VOICE_BASE;
  let element = null;
  let sourceNode = null;
  let gainNode = null;
  let currentKey = '';
  let revision = 0;
  let utterance = null;
  let muteWatch = null;

  function voiceLevel() {
    if (!engine?.ctx || engine.ctx.state !== 'running' || engine.settings.mute || engine.forcedMute ||
        document.hidden || engine.isPaused()) return 0;
    return engine.settings.master * engine.settings.voice;
  }

  function speakLocal(text, language, rate) {
    const synth = globalThis.speechSynthesis;
    const volume = voiceLevel();
    if (!volume || !synth || !globalThis.SpeechSynthesisUtterance) return false;
    const voices = synth.getVoices().filter(voice => voice.localService);
    const voice = voices.find(entry => entry.lang === language) ||
      voices.find(entry => entry.lang.split('-')[0] === language.split('-')[0]);
    if (!voice) return false;
    const line = new SpeechSynthesisUtterance(text);
    line.voice = voice;
    line.lang = language;
    line.rate = rate;
    line.volume = volume;
    utterance = line;
    function ended() {
      if (utterance !== line) return;
      clearInterval(muteWatch);
      utterance = null;
    }
    line.onend = ended;
    line.onerror = ended;
    muteWatch = setInterval(function checkMixer() {
      if (!voiceLevel()) stop();
    }, 100);
    synth.speak(line);
    return true;
  }


  function bind(options = {}) {
    if (options.engine) engine = options.engine;
    if (options.music) music = options.music;
    if (options.base) base = options.base;
  }

  function ensureGraph() {
    if (!engine?.ctx || !engine.buses?.voice) return null;
    if (element) return element;
    element = new Audio();
    element.preload = 'auto';
    sourceNode = engine.ctx.createMediaElementSource(element);
    gainNode = engine.ctx.createGain();
    gainNode.gain.value = 1;
    sourceNode.connect(gainNode).connect(engine.buses.voice);
    return element;
  }

  function stop() {
    revision++;
    if (utterance) {
      clearInterval(muteWatch);
      utterance = null;
      globalThis.speechSynthesis.cancel();
    }
    if (!element) {
      currentKey = '';
      return;
    }
    element.pause();
    element.removeAttribute('src');
    element.load();
    currentKey = '';
  }

  async function playLine({speaker, text, language = 'zh-TW', localRate = null} = {}) {
    const key = `${language}|${speaker}|${text}`;
    if (!speaker || !text) {
      stop();
      return {played: false, missing: true};
    }
    if (key === currentKey && element && !element.paused) {
      return {played: true, missing: false, reused: true};
    }
    const request = ++revision;
    const index = await loadIndex(base);
    if (request !== revision) return {played: false, superseded: true};
    const resolved = resolveClip(index, language, speaker, text);
    stop();
    currentKey = key;
    if (resolved.missing || !resolved.url) {
      if (localRate && speakLocal(text, language, localRate)) return {played: true, local: true};
      // With no clips generated at all the game stays as it was: text only, no static.
      if (Object.keys(index || {}).length) playStaticFallback(engine);
      return {played: false, missing: true, id: resolved?.id};
    }
    const audio = ensureGraph();
    if (!audio) {
      playStaticFallback(engine);
      return {played: false, missing: true, id: resolved.id, reason: 'no-audio-context'};
    }
    audio.src = resolved.url;
    music?.duck?.(4);
    try {
      await audio.play();
      return {played: true, missing: false, id: resolved.id};
    } catch {
      playStaticFallback(engine);
      return {played: false, missing: true, id: resolved.id};
    }
  }

  return {
    bind,
    playLine,
    stop,
    resolveClip,
    lineId,
    async debug() {
      const index = await loadIndex(base);
      return {
        currentKey,
        paused: !element || element.paused,
        languages: Object.keys(index),
        counts: Object.fromEntries(Object.entries(index).map(([lang, ids]) => [lang, ids.length])),
      };
    },
  };
}

// Safe to call before the audio engine exists; later calls bind engine/music onto the same singleton.
export function installVoice(options = {}) {
  if (!sharedVoice) sharedVoice = createController();
  sharedVoice.bind(options);
  return sharedVoice;
}

export function _resetVoiceForTests() {
  sharedVoice = undefined;
  indexCache = null;
  indexPromise = null;
}
