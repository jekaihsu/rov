// Private photographic camera. Aperture samples converge on the vehicle's focus plane.
import * as THREE from 'three';
import {getFidelity} from './fidelity.js';
import {downloadCollectionFile} from './collection_store.js';
import {STRINGS} from './photo_settings.js';

export function installPhotoMode(options) {
  const {scene, camera, renderer, vehicle, obstacles, world, onPhoto, resume, model, pad, aids} = options;
  const dialog = document.createElement('dialog');
  dialog.id = 'photoStudio';
  const canvas = document.createElement('canvas');
  const panel = document.createElement('section');
  const heading = document.createElement('strong');
  heading.textContent = STRINGS.photoMode;
  panel.append(heading);
  const fields = [];
  function field(key, control) {
    const label = document.createElement('label');
    label.append(STRINGS[key], control);
    panel.append(label);
    fields.push(control);
    control.oninput = () => dirty = true;
    return control;
  }
  function range(key, min, max, step, value) {
    const control = document.createElement('input');
    Object.assign(control, {type:'range', min, max, step, value});
    field(key, control);
    const output = document.createElement('output');
    control.after(output);
    const update = () => output.value = control.value;
    control.addEventListener('input', update);
    update();
    return control;
  }
  const lens = range('lens', 15, 100, 1, 35);
  const aperture = range('aperture', 0, 12, 1, 0);
  const exposure = range('exposure', -2, 2, .25, 0);
  const tone = field('tone', document.createElement('select'));
  for (const key of ['doc','clear','night']) tone.add(new Option(STRINGS[key], key));
  function button(key, handler) {
    const node = document.createElement('button');
    node.textContent = STRINGS[key];
    node.onclick = handler;
    panel.append(node);
    return node;
  }
  const shutter = button('save', save);
  button('hud', toggle);
  button('close', close);
  const hint = document.createElement('small');
  hint.textContent = STRINGS.hint;
  panel.append(hint);
  dialog.append(canvas, panel);
  document.body.append(dialog);
  const ctx = canvas.getContext('2d');
  const view = camera.clone();
  const anchor = new THREE.Vector3();
  const ray = new THREE.Raycaster();
  const keys = new Set();
  let dirty = true;
  let previous = [];
  let selected = 0;
  let solids = [];
  function open() {
    if (!getFidelity().get('photoMode') || dialog.open) return;
    vehicle.getWorldPosition(anchor);
    solids = obstacles();
    view.copy(camera, false);
    view.rotation.reorder('YXZ');
    view.position.copy(anchor);
    view.position.y = THREE.MathUtils.clamp(view.position.y, -world().seabed_depth + .1, -.1);
    move(new THREE.Vector3(0, .6, 2).applyQuaternion(view.quaternion));
    view.lookAt(anchor);
    view.aspect = renderer.domElement.width / renderer.domElement.height;
    canvas.width = renderer.domElement.width;
    canvas.height = renderer.domElement.height;
    previous = pad()?.buttons.map(value => value > .5) || [];
    panel.style.display = 'flex';
    dialog.showModal();
    selected = 0;
    hint.textContent = STRINGS.hint;
    fields[0].focus();
    dirty = true;
  }
  function close() {
    if (!dialog.open) return;
    dialog.close();
    keys.clear();
    resume();
  }
  function toggle() {
    panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
  }
  dialog.oncancel = event => { event.preventDefault(); close(); };
  dialog.ondblclick = toggle;
  function key(event) {
    if (!dialog.open) return;
    if (event.type === 'keyup') keys.delete(event.code);
    else {
      keys.add(event.code);
      if (event.code === 'KeyH' && !event.repeat) toggle();
      if (event.code === 'Escape') close();
    }
    event.stopImmediatePropagation();
  }
  window.addEventListener('keydown', key, true);
  window.addEventListener('keyup', key, true);
  window.addEventListener('blur', () => keys.clear());
  getFidelity().subscribe(() => { if (!getFidelity().get('photoMode')) close(); });
  function move(delta) {
    const target = delta.clone().add(view.position).sub(anchor).clampLength(0, 8).add(anchor);
    target.y = THREE.MathUtils.clamp(target.y, -world().seabed_depth + .1, -.1);
    delta.subVectors(target, view.position);
    const distance = delta.length();
    if (distance < .0001) return;
    ray.set(view.position, delta.normalize());
    ray.far = distance + .12;
    const hit = ray.intersectObjects(solids, true)[0];
    view.position.addScaledVector(delta, hit ? Math.max(0, hit.distance - .12) : distance);
    dirty = true;
  }
  function render() {
    const origin = view.position.clone();
    const radius = +aperture.value / 200;
    const samples = radius ? 6 : 1;
    const filters = {doc:'saturate(.85)', clear:'saturate(1.2)', night:'sepia(.3) hue-rotate(155deg) brightness(.7)'};
    ctx.filter = filters[tone.value] + ' brightness(' + 2 ** +exposure.value + ')';
    view.setFocalLength(+lens.value);
    const distance = Math.max(.3, origin.distanceTo(anchor));
    const plane = 2 * distance * Math.tan(THREE.MathUtils.degToRad(view.fov / 2));
    const subject = model();
    const visible = subject.visible;
    const suppression = aids().map(node => [node, node.visible]);
    for (const [node] of suppression) node.visible = false;
    subject.visible = true;
    try {
      for (let i = 0; i < samples; i++) {
        const x = radius * Math.cos(i * 2 * Math.PI / samples);
        const y = radius * Math.sin(i * 2 * Math.PI / samples);
        view.position.copy(origin).add(new THREE.Vector3(x,y,0).applyQuaternion(view.quaternion));
        const scale = canvas.height / plane;
        view.setViewOffset(canvas.width, canvas.height, -x * scale, y * scale, canvas.width, canvas.height);
        renderer.render(scene, view);
        ctx.globalAlpha = 1 / (1 + i);
        ctx.drawImage(renderer.domElement, 0, 0, canvas.width, canvas.height);
      }
    } finally {
      for (const [node, visible] of suppression) node.visible = visible;
      subject.visible = visible;
      ctx.globalAlpha = 1;
      view.clearViewOffset();
      view.position.copy(origin);
    }
    dirty = false;
  }
  async function save() {
    if (shutter.disabled) return;
    shutter.disabled = true;
    try {
      if (dirty) render();
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      let result;
      if (window.rovDesktop?.saveScreenshot) result = await window.rovDesktop.saveScreenshot(await blob.arrayBuffer());
      else downloadCollectionFile('ROV-' + Date.now() + '.png', blob);
      onPhoto();
      hint.textContent = result?.steam === 'failed' ? STRINGS.steamFailed : STRINGS.saved;
    } catch {
      hint.textContent = STRINGS.failed;
    } finally {
      shutter.disabled = false;
    }
  }
  function frame(dt) {
    if (!dialog.open) return false;
    const controller = pad();
    const buttons = controller?.buttons.map(value => value > .5) || [];
    const edge = i => buttons[i] && !previous[i];
    const axis = i => Math.abs(controller?.axes[i] || 0) > .15 ? controller.axes[i] : 0;
    const pair = (a,b) => Number(keys.has(a)) - Number(keys.has(b));
    const yaw = axis(2) + pair('ArrowRight','ArrowLeft');
    const pitch = axis(3) + pair('ArrowDown','ArrowUp');
    view.rotation.y -= yaw * dt;
    view.rotation.x = THREE.MathUtils.clamp(view.rotation.x - pitch * dt, -1.5, 1.5);
    dirty ||= !!(yaw || pitch);
    const delta = new THREE.Vector3(axis(0) + pair('KeyD','KeyA'), 0, axis(1) + pair('KeyS','KeyW'));
    delta.applyQuaternion(view.quaternion);
    delta.y += pair('KeyE','KeyQ') + Number(!!buttons[5]) - Number(!!buttons[4]);
    move(delta.multiplyScalar(dt * 2));
    if (edge(1)) close();
    else if (edge(0)) save();
    else if (edge(3)) toggle();
    if (edge(12) || edge(13)) {
      selected = (selected + (edge(12) ? -1 : 1) + fields.length) % fields.length;
      fields[selected].focus();
    }
    if (edge(14) || edge(15)) {
      const control = fields[selected];
      const direction = edge(14) ? -1 : 1;
      if (control === tone) tone.selectedIndex = (tone.selectedIndex + direction + 3) % 3;
      else if (direction > 0) control.stepUp();
      else control.stepDown();
      control.dispatchEvent(new Event('input'));
    }
    previous = buttons;
    if (dirty) render();
    return true;
  }
  return {open, close, frame, get active() { return dialog.open; }, label: STRINGS.photoMode};
}
