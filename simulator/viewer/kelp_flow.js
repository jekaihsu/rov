// Kelp and seagrass bending driven by the host's water flow (see flow_field.js).
//
// A 5 x 5 grid of three-space flow vectors near the seabed is uploaded as a uniform array; the
// kelp vertex shader and the CPU replica used by photo observations (observation_camera.js) read
// it with the same bilinear lookup, so blades lean and stir with the local current, gusts and
// structure wakes. Without a host grid every cell holds the vehicle's `current_here`.
import * as THREE from 'three';

export const KELP_GRID = 5;
const STIR_SPEED = 0.25;     // m/s at which the idle flutter reaches full amplitude
const STIR_MIN = 0.15;       // residual flutter in slack water

/** Uniforms shared by every kelp material: flow cells and their NED box (n0, e0, stepN, stepE). */
export function createKelpFlowUniforms() {
  const cells = Array.from({ length: KELP_GRID * KELP_GRID }, () => new THREE.Vector3());
  return { uFlowGrid: { value: cells }, uFlowBox: { value: new THREE.Vector4(0, 0, 1, 1) } };
}

/** GLSL declarations: `vec3 kelpFlow(vec2 xz)` and `float kelpStir(vec3 flow)`. */
export const KELP_FLOW_GLSL = `
uniform vec3 uFlowGrid[${KELP_GRID * KELP_GRID}];
uniform vec4 uFlowBox;
vec3 kelpFlow(vec2 xz) {
  float last = float(${KELP_GRID - 1});
  float fi = clamp((xz.y - uFlowBox.x) / uFlowBox.z, 0.0, last);
  float fj = clamp((-xz.x - uFlowBox.y) / uFlowBox.w, 0.0, last);
  int i = int(min(floor(fi), last - 1.0));
  int j = int(min(floor(fj), last - 1.0));
  float a = fi - float(i);
  float b = fj - float(j);
  vec3 near = mix(uFlowGrid[i * ${KELP_GRID} + j], uFlowGrid[i * ${KELP_GRID} + j + 1], b);
  vec3 far = mix(uFlowGrid[(i + 1) * ${KELP_GRID} + j], uFlowGrid[(i + 1) * ${KELP_GRID} + j + 1], b);
  return mix(near, far, a);
}
float kelpStir(vec3 flow) {
  return clamp(length(flow) / ${STIR_SPEED.toFixed(3)}, ${STIR_MIN.toFixed(3)}, 1.0);
}
`;

/** CPU replica of `kelpFlow` (three-space x, z of the blade root). */
export function kelpFlowAt(uniforms, x, z, out = new THREE.Vector3()) {
  const box = uniforms.uFlowBox.value;
  const cells = uniforms.uFlowGrid.value;
  const last = KELP_GRID - 1;
  const fi = Math.min(Math.max((z - box.x) / box.z, 0), last);
  const fj = Math.min(Math.max((-x - box.y) / box.w, 0), last);
  const i = Math.min(Math.floor(fi), last - 1);
  const j = Math.min(Math.floor(fj), last - 1);
  const a = fi - i;
  const b = fj - j;
  const near = cells[i * KELP_GRID + j].clone().lerp(cells[i * KELP_GRID + j + 1], b);
  const far = cells[(i + 1) * KELP_GRID + j].clone().lerp(cells[(i + 1) * KELP_GRID + j + 1], b);
  return out.copy(near.lerp(far, a));
}

/** CPU replica of `kelpStir`. */
export function kelpStir(flow) {
  return Math.min(Math.max(flow.length() / STIR_SPEED, STIR_MIN), 1);
}

const _ned = [0, 0, 0];

/** Refresh the kelp cells from the host flow grid (1 m above the bed), else from `fallback`. */
export function updateKelpFlow(uniforms, flowField, fallback, seabedDepth, nowMs) {
  const cells = uniforms.uFlowGrid.value;
  const box = flowField?.ready ? flowField.horizontalBox() : null;
  if (!box) {
    for (const cell of cells) cell.copy(fallback);
    uniforms.uFlowBox.value.set(0, 0, 1, 1);
    return;
  }
  const [n0, e0, stepN, stepE, countN, countE] = box;
  const cellN = (stepN * (countN - 1)) / (KELP_GRID - 1) || 1;
  const cellE = (stepE * (countE - 1)) / (KELP_GRID - 1) || 1;
  uniforms.uFlowBox.value.set(n0, e0, cellN, cellE);
  for (let i = 0; i < KELP_GRID; i++) {
    for (let j = 0; j < KELP_GRID; j++) {
      const v = flowField.sample(n0 + i * cellN, e0 + j * cellE, seabedDepth - 1, nowMs, _ned);
      cells[i * KELP_GRID + j].set(-v[1], -v[2], v[0]);
    }
  }
}
