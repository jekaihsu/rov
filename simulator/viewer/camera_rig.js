// Camera springs, virtual gimbal, physical photo pose and timed shot transitions.
import * as THREE from 'three';
const STRINGS = {
  chase: '追蹤', orbit: '環繞', top: '俯視', onboard: '機載', cine: '電影',
  gimbal: '雲台／硬連結', pitchUp: '雲台抬頭', pitchDown: '雲台低頭',
  orbitX: '環繞鏡頭水平', orbitY: '環繞鏡頭垂直'
};
const MODES = ['chase', 'orbit', 'top', 'onboard'];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export function spring(value, velocity, goal, omega, dt) {
  const error = value - goal;
  const c = velocity + omega * error;
  const decay = Math.exp(-omega * dt);
  return [goal + (error + c * dt) * decay, (velocity - omega * c * dt) * decay];
}
// Stand-in for harnesses that pass only URL parameters; the app always supplies the fidelity store.
// This module is loaded as a data URL by unit tests, so it cannot import fidelity.js itself.
function parameterFidelity(params) {
  const values = {cameraView: params?.get('cam'), gimbal: params?.get('gimbal') === '1', thirdPerson: true};
  const listeners = [];
  return {
    get(id) {
      return values[id];
    },
    set(id, value) {
      values[id] = value;
      for (const listener of listeners) listener();
    },
    subscribe(listener) {
      listeners.push(listener);
    }
  };
}
export function createCameraRig({camera, controls, rovG, renderer, params, getAnchor, getObstacles, onMode,
  fidelity = parameterFidelity(params)}) {
  const FLIP = new THREE.Quaternion(0, 1, 0, 0);
  // The fidelity profile owns the default view, third-person permission and gimbal; URL parameters feed it.
  let thirdPerson = fidelity.get('thirdPerson');
  let mode = MODES.includes(fidelity.get('cameraView')) ? fidelity.get('cameraView') : 'onboard';
  if (!thirdPerson) mode = 'onboard';
  let ready = false, transition = 1, yaw = 0, height = 22, zoom = 22;
  let gimbal = fidelity.get('gimbal'), pitch = 0, pitchGoal = 0;
  const cine = {a: .6, w: .14, r: 4.6, h: 1.5};
  const velocity = new THREE.Vector3(), previous = new THREE.Vector3();
  const angularVelocity = new THREE.Vector3();
  const from = camera.clone(), goal = camera.clone(), ray = new THREE.Raycaster();
  controls.object = goal;
  controls.enableDamping = false;
  renderer.domElement.addEventListener('wheel', wheel, {passive: false});
  function wheel(e) {
    if (mode !== 'top') return;
    zoom = clamp(zoom * Math.exp(e.deltaY * .001), 4, 150);
    e.preventDefault();
  }
  function bindInput(input) {
    function orbit(axis, value, dt) {
      const offset = goal.position.clone().sub(controls.target);
      const spherical = new THREE.Spherical().setFromVector3(offset);
      if (axis === 'x') spherical.theta -= value * dt * 1.6;
      else spherical.phi = clamp(spherical.phi + value * dt * 1.6, .15, Math.PI - .15);
      goal.position.copy(controls.target).add(offset.setFromSpherical(spherical));
    }
    // Keys, pad sources and contexts for these actions are declared in input/bindings.js.
    input.registerActions({
      cameraGimbal: {
        label: STRINGS.gimbal,
        run() {
          fidelity.set('gimbal', !gimbal);
        }
      },
      cameraPitchUp: {
        label: STRINGS.pitchUp,
        run() {
          pitchGoal = clamp(pitchGoal + .08, -.65, .65);
        }
      },
      cameraPitchDown: {
        label: STRINGS.pitchDown,
        run() {
          pitchGoal = clamp(pitchGoal - .08, -.65, .65);
        }
      },
      cameraOrbitX: {
        label: STRINGS.orbitX, continuous: true, consume: ['right_lr'],
        enabled: () => mode === 'orbit',
        run: (value, dt) => orbit('x', value, dt)
      },
      cameraOrbitY: {
        label: STRINGS.orbitY, continuous: true, consume: ['right_ud'],
        enabled: () => mode === 'orbit',
        run: (value, dt) => orbit('y', value, dt)
      }
    });
  }
  function setMode(next) {
    if (!Object.hasOwn(STRINGS, next)) return;
    from.copy(camera);
    transition = ready ? 0 : 1;
    mode = next;
    controls.enabled = mode === 'orbit';
    camera.up.set(0, 1, 0);
    if (mode === 'orbit') {
      goal.position.copy(rovG.position).add(new THREE.Vector3(1.2, 1.6, -3.5));
      controls.target.copy(rovG.position);
      controls.update();
    }
    onMode(mode, STRINGS[mode]);
  }
  function allowedModes() {
    return thirdPerson ? MODES : ['onboard'];
  }
  function applyFidelity() {
    gimbal = fidelity.get('gimbal');
    thirdPerson = fidelity.get('thirdPerson');
    if (!thirdPerson && MODES.includes(mode) && mode !== 'onboard') setMode('onboard');
  }
  fidelity.subscribe(applyFidelity);
  function update(dt) {
    const p = rovG.position;
    const forward = new THREE.Vector3(0, 0, 1).applyQuaternion(rovG.quaternion);
    const heading = Math.atan2(forward.x, forward.z);
    if (!ready) {
      yaw = heading;
      previous.copy(p);
    }
    const speed = p.distanceTo(previous) / Math.max(.001, dt);
    previous.copy(p);
    const delta = Math.atan2(Math.sin(heading - yaw), Math.cos(heading - yaw));
    yaw += clamp(delta * (1 - Math.exp(-dt * 2)), -dt * .8, dt * .8);
    const direction = new THREE.Vector3(Math.sin(yaw), 0, Math.cos(yaw));
    goal.up.set(0, 1, 0);
    // External cameras follow the player's FOV preference; the onboard camera keeps the real lens.
    const comfort = !!fidelity.get('motionComfort');
    goal.fov = mode === 'onboard' ? 70 : fidelity.get('externalFov') ?? 55;
    if (mode === 'chase') {
      const pull = comfort ? 0 : Math.min(1, speed * .3);
      goal.position.copy(p).addScaledVector(direction, -2.6 - pull);
      goal.position.y += .85;
      goal.lookAt(p.clone().addScaledVector(direction, 1.5));
      if (!comfort) goal.fov += Math.min(8, speed * 2);
    } else if (mode === 'orbit') {
      goal.position.add(p.clone().sub(controls.target));
      controls.target.copy(p);
      controls.update();
    } else if (mode === 'top') {
      height += (zoom - height) * (1 - Math.exp(-dt * 8));
      goal.up.set(0, 0, 1);
      goal.position.copy(p).add(new THREE.Vector3(0, height, 0));
      goal.lookAt(p);
    } else if (mode === 'cine') {
      cine.a += dt * cine.w;
      goal.position.set(Math.cos(cine.a) * cine.r, cine.h, Math.sin(cine.a) * cine.r).add(p);
      goal.position.y = Math.min(-.6, goal.position.y);
      goal.lookAt(p);
    } else {
      goal.position.copy(getAnchor()).applyQuaternion(rovG.quaternion).add(p);
      pitch += (pitchGoal - pitch) * (1 - Math.exp(-dt * 8));
      if (gimbal) goal.quaternion.setFromEuler(new THREE.Euler(pitch, heading + Math.PI, 0, 'YXZ'));
      else goal.quaternion.copy(rovG.quaternion).multiply(FLIP);
    }
    if (mode !== 'onboard') {
      const offset = goal.position.clone().sub(p);
      ray.set(p, offset.clone().normalize());
      ray.far = offset.length();
      const hit = ray.intersectObjects(getObstacles(), true)[0];
      if (hit) goal.position.copy(p).addScaledVector(ray.ray.direction, Math.max(.15, hit.distance - .2));
    }
    // Motion comfort snaps the chase / orbit / top cameras instead of springing, so the view does not bob.
    if (mode === 'onboard' || !ready || comfort) {
      camera.position.copy(goal.position);
      velocity.set(0, 0, 0);
    } else for (const axis of ['x', 'y', 'z']) {
      [camera.position[axis], velocity[axis]] = spring(camera.position[axis], velocity[axis],
        goal.position[axis], mode === 'cine' ? 4 : 12, dt);
    }
    if (comfort || (mode === 'onboard' && !gimbal)) {
      camera.quaternion.copy(goal.quaternion);
      angularVelocity.set(0, 0, 0);
    } else {
      const errorQ = camera.quaternion.clone().multiply(goal.quaternion.clone().invert());
      if (errorQ.w < 0) errorQ.set(-errorQ.x, -errorQ.y, -errorQ.z, -errorQ.w);
      const angle = 2 * Math.acos(clamp(errorQ.w, -1, 1));
      const error = new THREE.Vector3(errorQ.x, errorQ.y, errorQ.z);
      if (error.lengthSq() > 1e-12) error.normalize().multiplyScalar(angle);
      for (const axis of ['x', 'y', 'z']) {
        [error[axis], angularVelocity[axis]] = spring(error[axis], angularVelocity[axis], 0,
          mode === 'onboard' ? 45 : 14, dt);
      }
      const remaining = error.length();
      camera.quaternion.setFromAxisAngle(remaining > 1e-9 ? error.divideScalar(remaining) :
        new THREE.Vector3(0, 1, 0), remaining).multiply(goal.quaternion);
    }
    camera.fov += (goal.fov - camera.fov) * (1 - Math.exp(-dt * 8));
    if (transition < 1) {
      transition = Math.min(1, transition + dt / .25);
      const k = transition * transition * (3 - 2 * transition);
      camera.position.lerpVectors(from.position, goal.position, k);
      camera.quaternion.slerpQuaternions(from.quaternion, goal.quaternion, k);
    }
    if (mode !== 'onboard') {
      const offset = camera.position.clone().sub(p);
      ray.set(p, offset.clone().normalize());
      ray.far = offset.length();
      const hit = ray.intersectObjects(getObstacles(), true)[0];
      if (hit) camera.position.copy(p).addScaledVector(ray.ray.direction, Math.max(.15, hit.distance - .2));
    }
    camera.updateProjectionMatrix();
    ready = true;
  }
  function physicalCapture(state) {
    const saved = camera.clone();
    if (mode === 'onboard') {
      const q = new THREE.Quaternion(-state.q[2], -state.q[3], state.q[1], state.q[0]);
      camera.position.copy(getAnchor()).applyQuaternion(q);
      camera.position.add(new THREE.Vector3(-state.pos[1], -state.pos[2], state.pos[0]));
      camera.quaternion.copy(q).multiply(FLIP);
      camera.fov = 70;
      camera.updateProjectionMatrix();
    }
    return function restore() {
      camera.copy(saved);
    };
  }
  return {
    get mode() {
      return mode;
    },
    get topH() {
      return height;
    },
    cine,
    setMode,
    update,
    physicalCapture,
    bindInput,
    cycle() {
      const modes = allowedModes();
      setMode(modes[(modes.indexOf(mode) + 1) % modes.length]);
    }
  };
}
