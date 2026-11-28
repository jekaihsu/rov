// Trailer recording presentation: hide debug chrome, pin quality and seed, drive camera paths.
// Activated by ?trailer=1 (optionally with ?capture for fixed-step __advance). Does not change physics.
// Session-only: never writes rov.quality or rov.fidelity.v1; quality comes from the URL (?quality=ultra).

import {evaluateCameraPath} from './camera_path.js';

import {localize} from '../i18n/core.js';

const STRINGS = localize('trailer.recording', {
  recording: '錄影模式',
});

/** HUD parts a storyboard may keep on screen. Tools / cards / target aids stay off. */
export const TRAILER_HUD_PARTS = Object.freeze([
  'depth', 'heading', 'attitude', 'map', 'status', 'mission', 'telemetry', 'warning',
]);

const FULL_HUD = Object.freeze([...TRAILER_HUD_PARTS]);
const MINIMAL_HUD = Object.freeze(['depth', 'heading']);

/**
 * True only for explicit on values. `?trailer=0` / `?trailer=false` stay off
 * (unlike URLSearchParams.has, which is true whenever the key is present).
 */
export function trailerParamEnabled(params) {
  if (!params || typeof params.get !== 'function') return false;
  if (!params.has('trailer')) return false;
  const value = params.get('trailer');
  if (value === null || value === undefined) return false;
  const normalized = String(value).trim().toLowerCase();
  if (normalized === '' || normalized === '1' || normalized === 'true' || normalized === 'on' || normalized === 'yes') {
    return true;
  }
  return false;
}

/** Normalize storyboard `hud` into a list of part ids (may be empty). */
export function normalizeTrailerHud(spec) {
  if (spec === false || spec === 'off' || spec == null) return [];
  if (spec === true || spec === 'full') return [...FULL_HUD];
  if (spec === 'minimal') return [...MINIMAL_HUD];
  if (Array.isArray(spec)) {
    const allowed = new Set(TRAILER_HUD_PARTS);
    const parts = [];
    for (const item of spec) {
      const id = String(item || '').trim();
      if (allowed.has(id) && !parts.includes(id)) parts.push(id);
    }
    return parts;
  }
  if (typeof spec === 'object') {
    const parts = [];
    for (const id of TRAILER_HUD_PARTS) {
      if (spec[id]) parts.push(id);
    }
    return parts;
  }
  return [];
}

/**
 * Install trailer recording mode. Call `frame(dt)` after the normal camera rig update so the path
 * can override the lens. Exposes `window.__trailer` for the Playwright capture tool.
 */
export function installTrailerRecording({
  params,
  camera,
  rovG,
  setCam,
  getFidelity,
  document: doc = document,
}) {
  const enabled = trailerParamEnabled(params);
  if (!enabled) {
    return {
      enabled: false,
      frame() {},
      setPath() {},
      setHud() {},
      suppressAids() {},
      time() {
        return 0;
      },
      hideTargets() {
        return false;
      },
    };
  }

  doc.body.classList.add('trailer', 'movie');
  doc.body.classList.add('hud-hidden');
  doc.body.dataset.trailerHud = 'off';

  // Allow chase/follow poses in-memory only; do not persist into rov.fidelity.v1.
  const fidelity = getFidelity?.();
  if (fidelity?.setSession) {
    try {
      fidelity.setSession('thirdPerson', true);
    } catch {
      /* ignored */
    }
  }

  let path = null;
  let clock = 0;
  let hudParts = [];
  let active = true;

  function applyHud(spec) {
    hudParts = normalizeTrailerHud(spec);
    const show = hudParts.length > 0;
    doc.body.classList.toggle('hud-hidden', !show);
    doc.body.dataset.trailerHud = show ? hudParts.join(' ') : 'off';
  }

  function rovPose() {
    const forward = {x: 0, y: 0, z: 1};
    const q = rovG.quaternion;
    // Rotate (0,0,1) by quaternion.
    const x = forward.x;
    const y = forward.y;
    const z = forward.z;
    const qx = q.x;
    const qy = q.y;
    const qz = q.z;
    const qw = q.w;
    const ix = qw * x + qy * z - qz * y;
    const iy = qw * y + qz * x - qx * z;
    const iz = qw * z + qx * y - qy * x;
    const iw = -qx * x - qy * y - qz * z;
    const fx = ix * qw + iw * -qx + iy * -qz - iz * -qy;
    const fz = iz * qw + iw * -qz + ix * -qy - iy * -qx;
    return {
      position: [rovG.position.x, rovG.position.y, rovG.position.z],
      heading: Math.atan2(fx, fz),
    };
  }

  // setMode always restarts the 0.25 s blend; only call it when the path mode changes.
  let appliedCam = null;

  function applyPose(sample) {
    if (!sample || sample.mode === 'onboard' || !sample.position) {
      return;
    }
    if (appliedCam !== 'path' && typeof setCam === 'function') {
      // One chase switch so the hull is visible; the path owns the pose afterwards.
      try {
        setCam('chase');
      } catch {
        /* ignored */
      }
      appliedCam = 'path';
    }
    camera.position.set(sample.position[0], sample.position[1], sample.position[2]);
    if (sample.lookAt) {
      camera.lookAt(sample.lookAt[0], sample.lookAt[1], sample.lookAt[2]);
    }
    if (sample.fov != null) {
      camera.fov = sample.fov;
      camera.updateProjectionMatrix();
    }
  }

  function frame(dt) {
    if (!active) return;
    clock += Math.max(0, dt);
    if (!path) return;
    const sample = evaluateCameraPath(path, clock, rovPose());
    applyPose(sample);
  }

  /** Hide wireframe targets, guides and world labels each frame (app.js re-enables some of them). */
  function suppressAids({objG, navTarget, guide, routeLine, labelsCheckbox} = {}) {
    if (objG) objG.visible = false;
    if (navTarget) navTarget.visible = false;
    if (guide) guide.visible = false;
    if (routeLine) routeLine.visible = false;
    if (labelsCheckbox) labelsCheckbox.checked = false;
  }

  // Drop labels at install so the first painted frame is already clean.
  try {
    const labels = doc.getElementById?.('optLabels');
    if (labels) labels.checked = false;
  } catch {
    /* ignored */
  }

  const api = {
    enabled: true,
    get label() {
      return STRINGS.recording;
    },
    frame,
    suppressAids,
    hideTargets() {
      return true;
    },
    time() {
      return clock;
    },
    setTime(value) {
      clock = Math.max(0, Number(value) || 0);
    },
    setPath(next) {
      path = next || null;
      clock = 0;
      appliedCam = null;
      if (path?.mode === 'onboard') {
        setCam('onboard');
        appliedCam = 'onboard';
      }
    },
    setHud: applyHud,
    hudParts() {
      return [...hudParts];
    },
    hudVisible() {
      return hudParts.length > 0;
    },
    evaluate(t) {
      return evaluateCameraPath(path, t, rovPose());
    },
    stop() {
      active = false;
      doc.body.classList.remove('trailer', 'movie', 'hud-hidden');
      delete doc.body.dataset.trailerHud;
    },
  };

  if (typeof globalThis !== 'undefined') {
    globalThis.__trailer = api;
  }
  return api;
}
