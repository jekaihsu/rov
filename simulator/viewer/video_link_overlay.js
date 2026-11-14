// Onboard-video effects of the simulated vehicle link: the last frame held while the link freezes,
// and blocky compression artefacts while it is degraded. Only the onboard (first-person) camera is a
// video feed; other views show the link state through the HUD alone. Nothing here sends commands.

const ARTEFACT_COLUMNS = 64;
const ARTEFACT_ROWS = 36;
const ARTEFACT_REFRESH_MS = 120;

function layer(viewport, className) {
  const canvas = document.createElement('canvas');
  canvas.className = className;
  canvas.hidden = true;
  canvas.setAttribute('aria-hidden', 'true');
  Object.assign(canvas.style, {
    position: 'absolute', inset: '0', width: '100%', height: '100%', pointerEvents: 'none',
    zIndex: 'var(--z-scene-mark)',
  });
  viewport.append(canvas);
  return canvas;
}

function drawArtefacts(canvas, strength) {
  const ctx = canvas.getContext('2d');
  const image = ctx.createImageData(ARTEFACT_COLUMNS, ARTEFACT_ROWS);
  const chance = 0.04 + 0.22 * strength;
  for (let i = 0; i < ARTEFACT_COLUMNS * ARTEFACT_ROWS; i++) {
    if (Math.random() > chance) continue;
    const tone = Math.random() < 0.5 ? 20 : 150;
    image.data[i * 4] = tone * 0.6;
    image.data[i * 4 + 1] = tone;
    image.data[i * 4 + 2] = tone * 0.8;
    image.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);
}

export function installVideoLinkOverlay(viewport) {
  const frozen = layer(viewport, 'video-link-frozen');
  const blocks = layer(viewport, 'video-link-artefact');
  blocks.width = ARTEFACT_COLUMNS;
  blocks.height = ARTEFACT_ROWS;
  blocks.style.imageRendering = 'pixelated';
  let captured = false;
  let refreshedAt = 0;
  function capture(source) {
    frozen.width = source.width;
    frozen.height = source.height;
    frozen.getContext('2d').drawImage(source, 0, 0);
    captured = true;
  }
  // Call right after the scene is drawn, so the captured frame is the one the pilot was looking at.
  function update(effect, cameraMode, source) {
    const onboard = cameraMode === 'onboard';
    viewport.dataset.videoLink = !effect ? 'live' : effect.frozen ? 'frozen'
      : effect.extraDelay > 0 ? 'lagging' : 'degraded';
    const hold = !!effect?.frozen && onboard;
    if (hold && !captured && source) capture(source);
    if (!hold) captured = false;
    frozen.hidden = !hold;
    const strength = onboard && effect ? effect.artefact : 0;
    blocks.hidden = strength <= 0;
    if (strength <= 0) return;
    blocks.style.opacity = String(0.12 + 0.3 * strength);
    const now = performance.now();
    if (!hold && now - refreshedAt < ARTEFACT_REFRESH_MS) return;
    if (hold && refreshedAt) return;
    refreshedAt = now;
    drawArtefacts(blocks, strength);
  }
  return {update};
}
