// Camera springs, virtual gimbal, physical photo pose and timed shot transitions.
import * as THREE from 'three';
const STRINGS = {chase: '追蹤', orbit: '環繞', top: '俯視', onboard: '機載', cine: '電影'};
const MODES = ['chase', 'orbit', 'top', 'onboard'];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export function spring(value, velocity, goal, omega, dt) {
  const error = value - goal;
  const c = velocity + omega * error;
  const decay = Math.exp(-omega * dt);
  return [goal + (error + c * dt) * decay, (velocity - omega * c * dt) * decay];
}
export function createCameraRig({camera, controls, rovG, renderer, params, getAnchor, getObstacles, onMode}) {
  const FLIP = new THREE.Quaternion(0, 1, 0, 0);
  let mode = MODES.includes(params.get('cam')) ? params.get('cam') : 'chase';
  let ready = false, transition = 1, yaw = 0, height = 22, zoom = 22;
  let gimbal = params.get('gimbal') !== '0', pitch = 0, pitchGoal = 0;
  const cine = {a: .6, w: .14, r: 4.6, h: 1.5};
  const velocity = new THREE.Vector3(), previous = new THREE.Vector3();
  const angularVelocity = new THREE.Vector3();
  const from = camera.clone(), goal = camera.clone(), ray = new THREE.Raycaster();
  controls.object = goal;
  controls.enableDamping = false;
  renderer.domElement.addEventListener('wheel', wheel, {passive: false});
  window.addEventListener('keydown', keydown);
  function wheel(e) {
    if (mode !== 'top') return;
    zoom = clamp(zoom * Math.exp(e.deltaY * .001), 4, 150);
    e.preventDefault();
  }
  function keydown(e) {
    if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    if (e.code === 'KeyG') gimbal = !gimbal;
    if (e.code === 'BracketLeft') pitchGoal = clamp(pitchGoal - .08, -.65, .65);
    if (e.code === 'BracketRight') pitchGoal = clamp(pitchGoal + .08, -.65, .65);
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
    goal.fov = mode === 'onboard' ? 70 : 55;
    if (mode === 'chase') {
      goal.position.copy(p).addScaledVector(direction, -2.6 - Math.min(1, speed * .3));
      goal.position.y += .85;
      goal.lookAt(p.clone().addScaledVector(direction, 1.5));
      goal.fov += Math.min(8, speed * 2);
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
    if (mode === 'onboard' || !ready) camera.position.copy(goal.position);
    else for (const axis of ['x', 'y', 'z']) {
      [camera.position[axis], velocity[axis]] = spring(camera.position[axis], velocity[axis],
        goal.position[axis], mode === 'cine' ? 4 : 12, dt);
    }
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
    if (mode === 'onboard' && !gimbal) camera.quaternion.copy(goal.quaternion);
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
    return function restore() { camera.copy(saved); };
  }
  return {get mode() { return mode; }, cine, setMode, update, physicalCapture,
    cycle() { setMode(MODES[(MODES.indexOf(mode) + 1) % MODES.length]); }};
}
