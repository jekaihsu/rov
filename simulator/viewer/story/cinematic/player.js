// Modal, presentation-only storyboard player. One clock owns picture, captions and sound.
import {createCinematicLook} from '../cutscene_look.js';
import {installAudio} from '../../audio/engine.js';
import {installMusic} from '../../audio/music.js';
import {createFrameGate} from '../../prefs/display.js';
import {createDevices} from '../../input/devices.js';
import {drawFrame} from './frame.js';
import {STRINGS} from './copy.js';

export async function loadBoard(id, signal) {
  if (!/^[a-z][a-z0-9_-]*$/.test(id)) throw new Error('Invalid storyboard ID');
  const response = await fetch(new URL(id + '.json', import.meta.url), {signal});
  if (!response.ok) throw new Error('Missing storyboard: ' + id);
  const board = await response.json();
  if (!Array.isArray(board.shots) || !board.shots.length || !board.shots.every(shot =>
    Number.isFinite(shot.duration) && shot.duration > 0 && shot.camera?.path?.length)) {
    throw new Error('Invalid shots: ' + id);
  }
  return board;
}

export function playBoard(id, {onEnd, signal, menu = false} = {}) {
  const abort = new AbortController();
  const dialog = document.createElement('dialog');
  dialog.id = 'cinematicPlayer';
  dialog.setAttribute('aria-label', STRINGS[id] || STRINGS.narrator);
  dialog.style.cssText = 'position:fixed;inset:0;margin:0;padding:0;width:100vw;height:100vh;max-width:none;'
    + 'max-height:none;border:0;background:#07121b;color:white;overflow:hidden;';
  const canvas = document.createElement('canvas');
  canvas.width = 1600;
  canvas.height = 900;
  canvas.setAttribute('role', 'img');
  canvas.style.cssText = 'width:100%;height:100%;object-fit:contain;display:block';
  const controls = document.createElement('div');
  controls.style.cssText = 'position:absolute;bottom:1%;right:4%;display:flex;gap:1em';
  const pause = document.createElement('button');
  const skip = document.createElement('button');
  pause.textContent = STRINGS.pause;
  skip.textContent = STRINGS.skip;
  controls.append(pause, skip);
  dialog.append(canvas, controls);
  document.body.append(dialog);
  dialog.showModal();
  const look = createCinematicLook();
  look.set(true);
  const engine = installAudio();
  const devices = createDevices({});
  const skipFrame = createFrameGate();
  const music = installMusic({engine});
  let ambience;
  let frame;
  let paused = false;
  let elapsed = 0;
  let previous;
  let holdStart = null;
  let current;
  let board;
  let duration;
  function sound(shot) {
    if (ambience) {
      ambience.source.stop();
      for (const node of Object.values(ambience)) node.disconnect();
      ambience = null;
    }
    music.cue(shot?.cue);
    if (!shot?.cue) music.setScreen(null);
    if (shot?.ambient && engine.buses?.environment) ambience = engine.noiseLayer(.045, shot.ambient);
  }
  function finish() {
    if (abort.signal.aborted) return;
    abort.abort();
    cancelAnimationFrame(frame);
    look.release();
    sound(null);
    music.pauseCue(false);
    if (menu) music.setScreen('training');
    dialog.close();
    dialog.remove();
    onEnd?.();
  }
  function toggle() {
    paused = !paused;
    previous = performance.now();
    pause.textContent = paused ? STRINGS.resume : STRINGS.pause;
    music.pauseCue(paused);
    if (ambience) ambience.level.gain.value = paused ? 0 : .045;
  }
  function tick(now) {
    try {
      advance(now);
    } catch (error) {
      console.error(error);
      finish();
    }
  }
  function advance(now) {
    const dt = (now - (previous ?? now)) / 1000;
    previous = now;
    const circle = devices.poll().snapshot?.buttons[1] > .5;
    holdStart = circle ? (holdStart ?? now) : null;
    if (!paused) elapsed += dt;
    if ((circle && now - holdStart >= 800) || elapsed >= duration) return finish();
    if ((!paused && !skipFrame(now)) || !current) {
      const shot = drawFrame(canvas.getContext('2d'), board, elapsed);
      if (current !== shot) {
        dialog.dataset.shot = String(board.shots.indexOf(shot));
        const labels = [shot.location, shot.date, ...(shot.subtitle || []), ...(shot.news || [])];
        canvas.setAttribute('aria-label', labels.filter(Boolean).map(key => STRINGS[key]).join(' · '));
        sound(shot);
        if (paused && ambience) ambience.level.gain.value = 0;
      }
      current = shot;
    }
    frame = requestAnimationFrame(tick);
  }
  skip.onclick = finish;
  pause.onclick = toggle;
  dialog.oncancel = function cancel(event) {
    event.preventDefault();
    finish();
  };
  window.addEventListener('keydown', function key(event) {
    if (!['Escape', 'Space'].includes(event.code)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (event.repeat) return;
    if (event.code === 'Escape') finish();
    else toggle();
  }, {capture: true, signal: abort.signal});
  signal?.addEventListener('abort', finish, {once: true, signal: abort.signal});
  window.addEventListener('pagehide', finish, {once: true, signal: abort.signal});
  loadBoard(id, abort.signal).then(function start(data) {
    if (abort.signal.aborted) return;
    board = data;
    duration = board.shots.reduce((sum, shot) => sum + shot.duration, 0);
    frame = requestAnimationFrame(tick);
  }).catch(function unavailable(error) {
    if (!abort.signal.aborted) console.error(error);
    finish();
  });
  return finish;
}
