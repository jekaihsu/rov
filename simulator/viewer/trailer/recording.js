// Trailer recording presentation: hide debug chrome, pin quality and seed, drive camera paths.
// Activated by ?trailer=1 (optionally with ?capture for fixed-step __advance). Does not change physics.

import {evaluateCameraPath} from './camera_path.js';

const STRINGS = {
  recording: '錄影模式',
};

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
  storage = globalThis.localStorage,
}) {
  const enabled = params.has('trailer') || params.get('trailer') === '1';
  if (!enabled) {
    return {
      enabled: false,
      frame() {},
      setPath() {},
      setHud() {},
      time() {
        return 0;
      },
    };
  }

  doc.body.classList.add('trailer', 'movie');
  doc.body.classList.add('hud-hidden');
  try {
    storage?.setItem('rov.quality', 'ultra');
  } catch {
    /* private mode */
  }
  const fidelity = getFidelity?.();
  if (fidelity) {
    try {
      fidelity.set('thirdPerson', true);
    } catch {
      /* ignored */
    }
  }

  let path = null;
  let clock = 0;
  let hudVisible = true;
  let active = true;

  function applyHud(visible) {
    hudVisible = !!visible;
    doc.body.classList.toggle('hud-hidden', !hudVisible);
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

  function applyPose(sample) {
    if (!sample || sample.mode === 'onboard' || !sample.position) {
      if (sample?.mode === 'onboard') setCam('onboard');
      return;
    }
    if (typeof setCam === 'function') {
      // Keep third-person allowed; the path owns the pose.
      try {
        setCam('chase');
      } catch {
        /* ignored */
      }
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

  const api = {
    enabled: true,
    label: STRINGS.recording,
    frame,
    time() {
      return clock;
    },
    setTime(value) {
      clock = Math.max(0, Number(value) || 0);
    },
    setPath(next) {
      path = next || null;
      clock = 0;
      if (path?.mode === 'onboard') setCam('onboard');
    },
    setHud: applyHud,
    hudVisible() {
      return hudVisible;
    },
    evaluate(t) {
      return evaluateCameraPath(path, t, rovPose());
    },
    stop() {
      active = false;
      doc.body.classList.remove('trailer', 'movie', 'hud-hidden');
    },
  };

  if (typeof globalThis !== 'undefined') {
    globalThis.__trailer = api;
  }
  return api;
}
