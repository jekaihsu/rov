// Shared documentary stage and establishing camera for directed dives.
const ESTABLISH_ARC = Object.freeze({from: 1.3, to: 2.85, radiusFrom: 5.5, radiusTo: 2.4, liftFrom: -0.2,
  liftTo: 0.75});
const CINE_FOV = 46;

export function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export function createBeatStage(id, location, stampText) {
  const body = document.body;
  body.classList.add('cold-open', 'cold-open-cinematic');
  const style = document.createElement('link');
  style.rel = 'stylesheet';
  style.href = new URL('./cold_open.css', import.meta.url).href;
  document.head.append(style);
  const root = element('div', 'cold-open-layer');
  root.id = id;
  const black = element('div', 'cold-open-black');
  const bars = element('div', 'cold-open-bars');
  bars.append(element('i'), element('i'));
  const superCard = element('div', 'cold-open-super');
  superCard.append(element('strong', '', location[0]), element('span', '', location[1]));
  const radio = element('div', 'cold-open-radio');
  radio.setAttribute('role', 'status');
  radio.setAttribute('aria-live', 'polite');
  const speaker = element('small', 'cold-open-speaker');
  const words = element('p', 'cold-open-words');
  radio.append(speaker, words);
  const hint = element('div', 'cold-open-hint');
  hint.id = id + 'Hint';
  const stamp = element('div', 'cold-open-stamp', stampText);
  const tension = element('div', 'cold-open-tension');
  tension.id = id + 'Tension';
  root.append(black, bars, superCard, radio, hint, stamp, tension);
  body.append(root);
  black.style.opacity = '1';

  return {body, root, black, bars, superCard, radio, speaker, words, hint, stamp, tension, style};
}

export function establishingShot(camera, rovG, k) {
  const forward = camera.position.clone().set(0, 0, 1).applyQuaternion(rovG.quaternion);
  forward.y = 0;
  forward.normalize();
  const right = forward.clone().set(-forward.z, 0, forward.x);
  const angle = ESTABLISH_ARC.from + (ESTABLISH_ARC.to - ESTABLISH_ARC.from) * k;
  const radius = ESTABLISH_ARC.radiusFrom + (ESTABLISH_ARC.radiusTo - ESTABLISH_ARC.radiusFrom) * k;
  const lift = ESTABLISH_ARC.liftFrom + (ESTABLISH_ARC.liftTo - ESTABLISH_ARC.liftFrom) * k;
  const offset = forward.clone().multiplyScalar(Math.cos(angle) * radius)
    .add(right.clone().multiplyScalar(Math.sin(angle) * radius));
  camera.position.copy(rovG.position).add(offset);
  camera.position.y += lift;
  const look = rovG.position.clone().add(forward.clone().multiplyScalar(1.9 + 3.6 * k));
  look.y += 0.2 * (1 - k);
  camera.up.set(0, 1, 0);
  camera.lookAt(look);
  camera.fov = CINE_FOV;
  camera.updateProjectionMatrix();
}

// The same reveal selectors drive both watches. The caller can hold the HUD dark across a camera cut.
export function presentStage(stage, {black, letterbox, cinematic, location, reveal}) {
  stage.black.style.opacity = String(black);
  stage.root.classList.toggle('letterbox', letterbox);
  stage.body.classList.toggle('cold-open-cinematic', cinematic);
  stage.superCard.classList.toggle('visible', location);
  stage.body.dataset.coldReveal = reveal.join(' ');
}

// Hold the measured peak for three seconds so the operator can read short-lived loads.
export function createTensionMeter(element, label, warning) {
  const samples = [];
  return function read(time, newtons) {
    samples.push([time, newtons]);
    while (time - samples[0][0] > 3) samples.shift();
    const value = Math.round(samples.reduce((peak, sample) => Math.max(peak, sample[1]), 0));
    const text = label + ' ' + value + ' N';
    if (element.textContent !== text) element.textContent = text;
    element.dataset.tone = value >= warning ? 'warn' : '';
    return value;
  };
}
