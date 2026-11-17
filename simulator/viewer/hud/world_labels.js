// Screen labels pinned to world points (spool, current objective, wraps and snags), drawn every frame.
// Per frame it only writes what changed: class names and text are compared first, and positions move with a
// transform (no layout). The viewport size comes from the caller's resize handling, so a frame never forces a
// synchronous layout by reading the viewport's geometry after the HUD has written to the DOM.
import * as THREE from 'three';

const projected = new THREE.Vector3();

export function createWorldLabels({ container, camera, enabled }) {
  const elements = new Map();
  const seen = new Set();

  function place(label, width, height) {
    projected.copy(label.pos).project(camera);
    if (projected.z > 1 || projected.z < -1 || Math.abs(projected.x) > 1.05 || Math.abs(projected.y) > 1.05) {
      return;
    }
    let el = elements.get(label.id);
    if (!el) {
      el = document.createElement('div');
      el.style.left = '0px';
      el.style.top = '0px';
      container.appendChild(el);
      elements.set(label.id, el);
    }
    const className = 'lbl ' + (label.cls || '');
    if (el.className !== className) el.className = className;
    if (el.textContent !== label.text) el.textContent = label.text;
    const x = Math.round((projected.x + 1) / 2 * width + 8);
    const y = Math.round((1 - projected.y) / 2 * height);
    // style.css centres the label vertically with translate(0, -50%); keep that after the position.
    const transform = `translate(${x}px, ${y}px) translate(0, -50%)`;
    if (el.style.transform !== transform) el.style.transform = transform;
    if (el.hidden) el.hidden = false;
    seen.add(label.id);
  }

  // list: [{id, text, pos: THREE.Vector3, cls}]; width / height: the viewport's CSS size.
  function draw(list, width, height) {
    seen.clear();
    if (enabled()) {
      for (const label of list) place(label, width, height);
    }
    for (const [id, el] of elements) {
      if (!seen.has(id) && !el.hidden) el.hidden = true;
    }
  }

  return { draw };
}
