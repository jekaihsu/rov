import { installChannelTable } from './input/channel_table.js';
import { createRenderState, sampleSnapshots } from './state_buffer.js';
import { createStateMerger, VIEWER_CAPS } from './state_merge.js';
import { createCameraRig } from './camera_rig.js';
import {getFidelity} from './fidelity.js';
import { updateTetherOperations } from './tether/operations.js';
import { tensionColor, warnLoad, gaugePercent } from './tether/tension.js';
import { cableTensionColor } from './tether/snag_focus.js';
import { installProcedure } from './procedure/index.js';
import { rotorRate } from './procedure/deck_flow.js';
import { createSonar } from './sonar/panel.js';
import { hidesTargets } from './sonar/scenario.js';
import {visionTargets} from './vision/targets.js';
import {installVision} from './vision/overlay.js';
import { installCameraLook } from './onboard/camera_look.js';
import {installInput} from './input/index.js';
import {assistFields} from './input/actions.js';
import { updateFlightHUD } from './hud/flight_hud.js';
import { pilotReadings, showsTruth, formatKnots } from './hud/sensor_view.js';
import {installTetherReel} from './tether_reel.js';
import {thrusterLabel} from './hud/thruster_names.js';
import {installStartPresentation} from './start_presentation.js';
import {objectiveFade, objectiveNearFade} from './hud/objective_fade.js';
import {installFlightFeedback} from './story/flight_feedback.js';
import {installPhotoFeedback} from './hud/photo_feedback.js';
import {installIntroSkip} from './play/intro_skip.js';
import {installOnboarding} from './play/onboarding.js';
// X1 ROV training viewer / pilot console.
// Renders the qysim state stream (PROTOCOL.md §2–4) and sends the pilot's RC channels back.
// Frames: server NED world / FRD body  →  three.js Y-up: three(x,y,z) = (−east, −down, north).
import * as THREE from 'three';
import {installAudio, installAudioSettings} from './audio/engine.js';
import {installMusic} from './audio/music.js';
import {installVoice} from './audio/voice.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { DeployIntro } from './deploy_intro.js';
import { SpoolStation } from './spool_station.js';
import { placeSceneModel } from './scene_models.js';
import { Cable } from './cable.js';
import { Environment } from './environment.js';
import {updatePenNet} from './aquaculture.js';
import { buildStructures, structureDetail } from './structures.js';
import { obstacleDistance } from './structure_sdf.js';
import { createFlowField } from './flow_field.js';
import { PilotPiP } from './pilot_pip.js';
import { createVehicleModel } from './vehicle_models.js';
import { Fleet } from './fleet.js';
import { installCockpit } from './cockpit.js';
import { applyVehicleSticker } from './vehicle_stickers.js';
import { installSurfacePaint } from './surface_paint.js';
import {updateRenderQuality,renderQualityInfo,canvasAntialias} from './render_quality.js';
import {installPrologue, prologueControlsBlocked} from './story/prologue.js';
import {installCampaign} from './story/campaign.js';
import {installColdOpen} from './story/cold_open.js';
import {installChapterCards} from './brand/chapter_card.js';
import {installMissionPanel} from './mission_panel.js';
import {installCollectionPanel} from './collection_panel.js';
import {installExpeditionClient} from './expedition_client.js';
import {installExpeditionPanel} from './expedition_panel.js';
import {inspectObservation} from './observation_camera.js';
import {installPilotGuide} from './pilot_guide.js';
import {drawROVAttitude} from './attitude_indicator.js';
import { installUnderwaterPipeline } from './fx/pipeline.js';
import { applyUnderwaterLighting } from './underwater_lighting.js';
import { SiltRenderer } from './fx/silt.js';
import { createDaylight } from './fx/daylight.js';
import { readReplay } from './replay_store.js';
import { installDebrief } from './debrief/install.js';
import {storedControlLayout, rememberControlLayout} from './control_layout.js';
import { openRcLink, createRcPump } from './input/rc_link.js';
import { createLinkInbox } from './input/link_inbox.js';
import {installPauseMenu, pauseMenuOpen} from './menu/pause.js';
import {installFeedbackReport, feedbackOpen} from './feedback/index.js';
import { createLinkPresenter } from './video_link.js';
import { installVideoLinkOverlay } from './video_link_overlay.js';
import { installResults, resultsOpen } from './play/results.js';
import { installAchievements } from './play/achievements.js';
import { installConnectionNotice } from './play/connection_notice.js';
import { missionTimeLimit, scoreSummary, scoreValue } from './play/mission_text.js';
import { installObjectiveCard } from './play/objective_card.js';
import { installCareerDive } from './career/dive.js';
import './prefs/camera_items.js';
import { createFrameGate, installDisplayPrefs } from './prefs/display.js';
import { createWorldLabels } from './hud/world_labels.js';
import { elementSize } from './hud/canvas.js';
import { cssVariable } from './hud/css_variables.js';
import { createShaderWarmup } from './shader_warmup.js';

const $ = (id) => document.getElementById(id);
const DEG = Math.PI / 180, KNOT = 0.514444;
const C = cssVariable;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const fmtT = (s) => { s = Math.max(0, Math.round(s || 0)); return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`; };
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// NED point → three
const P = (p, out = new THREE.Vector3()) => out.set(-p[1], -p[2], p[0]);
// body→world quaternion [w,x,y,z] (FRD→NED) → three (vector part mapped like points)
const Q = (q, out = new THREE.Quaternion()) => out.set(-q[2], -q[3], q[1], q[0]);

/* ═════════════════════════ renderer / scene ═════════════════════════ */
const vp = $('vp');
const renderer = new THREE.WebGLRenderer({ antialias: canvasAntialias(), powerPreference:'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.domElement.className = 'gl';
vp.prepend(renderer.domElement);

const scene = new THREE.Scene();
const waterSurf = new THREE.Color('#1d6378'), waterDeep = new THREE.Color('#01070b');
scene.background = new THREE.Color('#0a2a38');
scene.fog = new THREE.Fog(0x0a2a38, 0.3, 12);
const siltFx = new SiltRenderer(scene);
const camera = new THREE.PerspectiveCamera(55, 1, 0.05, 2600);
camera.position.set(-3, 1.5, -3);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.minDistance = 0.8; controls.maxDistance = 120; controls.enabled = false;

const daylightRig = createDaylight(scene);   // sun, sky light, sky and sea above water (fx/daylight.js)
// daylight fades with depth (roughly e-folding every 10 m in coastal water): at 30 m the
// structures are dim blue shapes and the ROV's lights make the difference
function daylight(depth) { return 0.1 + 0.9 * Math.exp(-Math.max(0, depth) / 10); }

// seabed + grid
const seabed = new THREE.Group(); scene.add(seabed);
{
  const g = new THREE.Mesh(new THREE.PlaneGeometry(800, 800), new THREE.MeshStandardMaterial({ color: 0x4a4636, roughness: 1 }));
  g.rotation.x = -Math.PI / 2; seabed.add(g); seabed.userData.plane = g;
  const grid = new THREE.GridHelper(200, 100, 0x6a7a66, 0x39443a); grid.position.y = 0.02; seabed.add(grid);
  const big = new THREE.GridHelper(800, 40, 0x7d8a70, 0x7d8a70); big.position.y = 0.03; seabed.add(big);
}
seabed.position.y = -30;
// sea surface
const surface = new THREE.Mesh(new THREE.PlaneGeometry(800, 800),
  new THREE.MeshBasicMaterial({ color: 0x6fc3d8, transparent: true, opacity: 0.32, side: THREE.DoubleSide, depthWrite: false }));
surface.rotation.x = -Math.PI / 2; scene.add(surface);

/* ═════════════════════════ ROV ═════════════════════════ */
const rovG = new THREE.Group(); scene.add(rovG);            // posed from state
const body = new THREE.Group(); rovG.add(body);             // model in body frame (three-mapped FRD)
const lightRig = new THREE.Group(); rovG.add(lightRig);
const fleet = new Fleet(scene);
let activeModel = null, modelGeneration = 0, activeModelId = null;
const cameraAnchor = new THREE.Vector3(0, .03, .4);
const placeholder = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.3, 0.6), new THREE.MeshStandardMaterial({ color: 0xf2b705, roughness: .6 }));
body.add(placeholder);
let noseZ = 0.34;
const rotors = [];            // model rotor nodes {o, base, axis, pos}
let rotorOf = [];             // physics thruster index → rotor
const leds = [], beams = [];
// LED lamps: spotlights that light the scene, a visible beam (backscatter in the water) and a glow
const beamMat = new THREE.ShaderMaterial({
  uniforms: { uI: { value: 0 }, uColor: { value: new THREE.Color(0xfff2dc) } },
  vertexShader: `varying float vT; varying vec3 vN; varying vec3 vV;
    void main() { vT = uv.y; vec4 mv = modelViewMatrix * vec4(position, 1.0);
      vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
  fragmentShader: `uniform float uI; uniform vec3 uColor; varying float vT; varying vec3 vN; varying vec3 vV;
    void main() { float along = pow(vT, 2.2);                      // bright at the lamp, fading out
      float core = 0.35 + 0.65 * pow(abs(dot(vN, vV)), 1.4);         // denser towards the axis, never zero seen end-on
      gl_FragColor = vec4(uColor * uI * along * core * 0.22, 1.0); }`,
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
});
const BEAM_LEN = 9, BEAM_HALF = 0.5;                  // m, rad (matches the spot cone)
const glowTex = (() => {
  const c = document.createElement('canvas'); c.width = c.height = 64; const g = c.getContext('2d');
  const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, 'rgba(255,250,235,1)'); r.addColorStop(0.25, 'rgba(255,240,210,.55)'); r.addColorStop(1, 'rgba(255,230,200,0)');
  g.fillStyle = r; g.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c);
})();
for (const x of [0.12, -0.12]) {
  const l = new THREE.SpotLight(0xfff2dc, 0, 22, BEAM_HALF, 0.55, 1.3);
  l.position.set(x, -0.02, noseZ); l.target.position.set(x * 3, -0.4, 6);
  lightRig.add(l); lightRig.add(l.target); leds.push(l);
  // cone with its apex at the lamp, opening along the lamp's aim
  const geo = new THREE.CylinderGeometry(0.03, BEAM_LEN * Math.tan(BEAM_HALF) * 0.85, BEAM_LEN, 32, 1, true);
  geo.translate(0, -BEAM_LEN / 2, 0);                  // apex (top, uv.y = 1) at the origin, cone along -Y
  const cone = new THREE.Mesh(geo, beamMat);
  cone.userData.legacyBeam = true;  // fx/water_optics.js draws the scattered beam itself in the optics tiers
  cone.renderOrder = 5; cone.frustumCulled = false; cone.visible = false;
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0xfff4e6, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  glow.scale.setScalar(0.35); glow.visible = false;
  lightRig.add(cone, glow);
  beams.push({ l, cone, glow });
}
function aimBeams() {
  for (const { l, cone, glow } of beams) {
    cone.position.copy(l.position); glow.position.copy(l.position).add(new THREE.Vector3(0, 0, 0.03));
    const dir = l.target.position.clone().sub(l.position).normalize();
    cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), dir);
  }
}
aimBeams();

// top-view marker: arrow on the ROV pointing along the nose (scaled with view height)
const topMark = new THREE.Mesh(new THREE.ShapeGeometry(new THREE.Shape([new THREE.Vector2(0, .9), new THREE.Vector2(.5, -.5), new THREE.Vector2(0, -.2), new THREE.Vector2(-.5, -.5)])),
  new THREE.MeshBasicMaterial({ color: 0xf2b705, fog: false, transparent: true, opacity: .85, depthTest: false, side: THREE.DoubleSide }));
topMark.renderOrder = 10; topMark.visible = false; scene.add(topMark);

function loadModel(definition = W?.vehicle || {id:'x1',model:'models/rov.glb'}) {
  if(activeModelId === definition.id)return;
  activeModelId = definition.id; const generation = ++modelGeneration;
  window.__modelLoaded=false;window.__loadedModelId=null;
  createVehicleModel(definition).then(model => {
    if(generation !== modelGeneration){model.dispose();return;}
    if(activeModel){body.remove(activeModel.root);activeModel.dispose();}
    activeModel=model;body.remove(placeholder);body.add(model.root);model.model.visible=camMode!=='onboard';
    applyVehicleSticker(model,S?.appearance?.sticker||'none');
    rotors.splice(0,rotors.length,...model.rotors);
    rotorOf=rotors.slice().sort((a,b)=>a.thrusterIndex-b.thrusterIndex);
    if(definition.camera_body)P(definition.camera_body,cameraAnchor);
    if(definition.gland_body)P(definition.gland_body,GLAND_LOCAL);
    noseZ=cameraAnchor.z;
    leds.forEach((light,i)=>{if(definition.lamp_body?.[i])P(definition.lamp_body[i],light.position);light.target.position.copy(light.position).add(new THREE.Vector3(0,-.3,6));});
    aimBeams();window.__modelLoaded=!model.loadError;window.__loadedModelId=definition.id;
  }).catch(error=>{activeModelId=null;console.error('機型載入失敗',error);});
}

// Map each physics thruster to the GLB rotor nearest in model space (names in the GLB are L/R-swapped).
function matchThrusters() {
  if(activeModel){rotorOf=activeModel.rotors.slice().sort((a,b)=>a.thrusterIndex-b.thrusterIndex);return;}
  const th = W?.thrusters; if (!th || !rotors.length) return;
  const pp = th.map((t) => new THREE.Vector3(-t.pos[1], -t.pos[2], t.pos[0]));
  const mP = pp.reduce((a, v) => a.add(v), new THREE.Vector3()).divideScalar(pp.length);
  const mR = rotors.reduce((a, r) => a.add(r.pos), new THREE.Vector3()).divideScalar(rotors.length);
  const A = pp.map((v) => v.clone().sub(mP)), B = rotors.map((r) => r.pos.clone().sub(mR));
  const n = A.length, used = new Array(B.length).fill(false), cur = [];
  let best = null, bestCost = Infinity;
  (function rec(i, cost) {                       // exhaustive assignment (6! = 720)
    if (cost >= bestCost) return;
    if (i === n) { bestCost = cost; best = cur.slice(); return; }
    for (let j = 0; j < B.length; j++) if (!used[j]) {
      used[j] = true; cur.push(j); rec(i + 1, cost + A[i].distanceToSquared(B[j])); cur.pop(); used[j] = false;
    }
  })(0, 0);
  rotorOf = best ? best.map((j) => rotors[j]) : [];
}

/* ═════════════════════════ world objects ═════════════════════════ */
const worldG = new THREE.Group(); scene.add(worldG);
const obstacleMeshes = new Map();       // name → {mesh, ob}
const objG = new THREE.Group(); scene.add(objG);
let objMarkers = [];
let structureSet = null;                // structures.js: detailed meshes drawn inside the collision shapes

const spoolStation = new SpoolStation(scene, () => loadIntroAssets());
let env = null;
function buildWorld() {
  surfacePaint.update(null);
  for(const ring of wrapG.children){ring.geometry.dispose();ring.material.dispose();}wrapG.clear();
  fleet.reset(W);
  worldG.clear(); obstacleMeshes.clear();
  if (env) env.dispose();
  const detail = structureDetail(renderer);
  env = params.has('noenv') ? null : new Environment(scene, W, {detail});
  seabed.userData.plane.visible = !env;                         // the environment brings its own sand
  seabed.userData.plane.userData.paintable=true;
  seabed.position.y = -W.seabed_depth;
  structureSet?.dispose();
  structureSet = buildStructures(W, {detail});
  worldG.add(structureSet.group);
  for (const [name, entry] of structureSet.entries) obstacleMeshes.set(name, entry);
  for (const ob of W.obstacles || []) if (ob.type === 'model') placeSceneModel(ob, worldG, P, detail);
  spoolStation.build(W, startPresentation?.introStart(W, S?.pos || [0, 0, 3]) || W.start_pos || [0, 0, 3]);
  buildObjectives(W.objectives || []);
  buildThrBars();
  matchThrusters();
  fillCurrentSliders();
}

function buildObjectives(list) {
  if (hidesTargets(W)) list = [];
  const geometries=new Set(),materials=new Set();objG.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)materials.add(o.material);});geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());
  objG.clear(); objMarkers = [];
  list.forEach((o) => {
    const g = new THREE.Group(); P(o.point, g.position);
    const mat = new THREE.MeshBasicMaterial({ color: 0x7f99a8, transparent: true, opacity: .75, depthWrite: false });
    const wire = new THREE.MeshBasicMaterial({ color: 0x7f99a8, transparent: true, opacity: .07, wireframe: true, depthWrite: false });
    let bill = null;
    const r = Math.max(.3, o.radius || 1);
    if (o.kind === 'checkpoint') {
      bill = new THREE.Mesh(new THREE.TorusGeometry(r, .06, 8, 48), mat); g.add(bill);
      g.add(new THREE.Mesh(new THREE.SphereGeometry(.08, 10, 8), mat));
    } else if (o.kind === 'inspect') {
      g.add(new THREE.Mesh(new THREE.OctahedronGeometry(.18), mat));
      g.add(new THREE.Mesh(new THREE.SphereGeometry(r, 16, 10), wire));
    } else {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(r, .07, 8, 48), mat); ring.rotation.x = Math.PI / 2; g.add(ring);
      g.add(new THREE.Mesh(new THREE.SphereGeometry(r, 16, 10), wire));
    }
    objG.add(g);
    objMarkers.push({ o, g, mat, wire, bill });
  });
}

// route / guide line
const MAXR = 400;
const routeLine = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(MAXR * 3), 3)),
  new THREE.LineBasicMaterial({ color: 0xc792ff, fog: false }));
routeLine.frustumCulled = false; scene.add(routeLine);
const navTarget = new THREE.Mesh(new THREE.SphereGeometry(.2, 12, 8), new THREE.MeshBasicMaterial({ color: 0xc792ff, fog: false, wireframe: true }));
scene.add(navTarget);
const guide = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3)),
  new THREE.LineDashedMaterial({ color: 0xf2b705, dashSize: .4, gapSize: .3, transparent: true, opacity: .7, fog: false }));
guide.frustumCulled = false; scene.add(guide);

/* ═════════════════════════ tether ═════════════════════════ */
const MAXN = 1024;
const tetherLine = new THREE.Line(new THREE.BufferGeometry()
  .setAttribute('position', new THREE.BufferAttribute(new Float32Array(MAXN * 3), 3))
  .setAttribute('color', new THREE.BufferAttribute(new Float32Array(MAXN * 3), 3)),
new THREE.LineBasicMaterial({ vertexColors: true }));
tetherLine.frustumCulled = false; scene.add(tetherLine);
const brokenLine = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(MAXN * 3), 3)),
  new THREE.LineDashedMaterial({ color: 0xff4757, dashSize: .35, gapSize: .25 }));
brokenLine.frustumCulled = false; brokenLine.visible = false; scene.add(brokenLine);
const tubeMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: .55, metalness: 0 });
const GLAND_LOCAL = new THREE.Vector3(0, .06, -.38);   // tether.py GLAND_BODY (FRD -0.38, 0, -0.06) in model space
let tetherTarget = [], tetherDisp = [], tetherInfo = null;
const cable = new Cable(tubeMat, { radius: .0065, segments: 240, radial: 8, colors: true });
scene.add(cable.mesh);
const contactMesh = new THREE.InstancedMesh(new THREE.SphereGeometry(.08, 8, 6), new THREE.MeshBasicMaterial({ color: 0xff4757 }), 256);
contactMesh.count = 0; contactMesh.frustumCulled = false; scene.add(contactMesh);
const wrapG = new THREE.Group(); scene.add(wrapG);


const distToObstacle = obstacleDistance;  // p NED; approximate surface distance (structure_sdf.js)

const _c = new THREE.Color(), _m = new THREE.Matrix4();
let wrapLabels = [];
function updateTether(t) {
  const nodes = t.nodes || [];
  const n = Math.min(nodes.length, MAXN);
  const pts = []; for (let i = 0; i < n; i++) pts.push(P(nodes[i]));
  // polyline (always visible); colour via tether/snag_focus (assisted snag hotspot optional)
  const lp = tetherLine.geometry.attributes.position.array, lc = tetherLine.geometry.attributes.color.array;
  for (let i = 0; i < n; i++) {
    lp[i * 3] = pts[i].x; lp[i * 3 + 1] = pts[i].y; lp[i * 3 + 2] = pts[i].z;
    cableTensionColor(t, i / Math.max(1, n - 1), pts, _c);
    lc[i * 3] = _c.r; lc[i * 3 + 1] = _c.g; lc[i * 3 + 2] = _c.b;
  }
  tetherLine.geometry.setDrawRange(0, n);
  tetherLine.geometry.attributes.position.needsUpdate = true; tetherLine.geometry.attributes.color.needsUpdate = true;
  tetherLine.visible = !t.broken;
  // broken: dashed red
  brokenLine.visible = !!t.broken;
  if (t.broken) {
    const bp = brokenLine.geometry.attributes.position.array;
    for (let i = 0; i < n; i++) { bp[i * 3] = pts[i].x; bp[i * 3 + 1] = pts[i].y; bp[i * 3 + 2] = pts[i].z; }
    brokenLine.geometry.setDrawRange(0, n); brokenLine.geometry.attributes.position.needsUpdate = true;
    brokenLine.computeLineDistances();
  }
  // cable: updated in place every frame from smoothed nodes (see renderTether)
  tetherTarget = pts; tetherInfo = t;
  if (tetherDisp.length !== pts.length) tetherDisp = pts.map((p) => p.clone());
  // contact nodes (client-side proximity; server only reports the count)
  let k = 0;
  if (t.contact_nodes > 0 && W) {
    for (let i = 0; i < n && k < 256; i++) {
      for (const ob of W.obstacles || []) {
        if (distToObstacle(nodes[i], ob) < .2) { _m.makeTranslation(pts[i].x, pts[i].y, pts[i].z); contactMesh.setMatrixAt(k++, _m); break; }
      }
      if (k < 256 && nodes[i][2] > (W.seabed_depth - .12)) { _m.makeTranslation(pts[i].x, pts[i].y, pts[i].z); contactMesh.setMatrixAt(k++, _m); }
    }
  }
  contactMesh.count = k; contactMesh.instanceMatrix.needsUpdate = true;
  // snag / wrap highlight
  const snag = new Set(t.snagged_on || []), wraps = t.wraps || {};
  structureSet?.highlight(new Set([...snag, ...Object.keys(wraps).filter((name) => Math.abs(wraps[name]) >= .25)]));
  for(const ring of wrapG.children)ring.visible=false;wrapLabels = [];
  for (const [name, turns] of Object.entries(wraps)) {
    const e = obstacleMeshes.get(name); if (!e || Math.abs(turns) < .05) continue;
    const ob = e.ob; let best = null, bd = 1e9;
    for (let i = 0; i < n; i++) { const d = distToObstacle(nodes[i], ob); if (d < bd) { bd = d; best = i; } }
    if (best == null) continue;
    const at = pts[best].clone();
    if (ob.type === 'cylinder') {
      const a = P(ob.p0), b = P(ob.p1), ax = b.clone().sub(a).normalize();
      const c = a.clone().addScaledVector(ax, at.clone().sub(a).dot(ax));
      let ring=wrapG.children.find(mesh=>mesh.name===name);
      if(!ring){ring=new THREE.Mesh(new THREE.TorusGeometry(ob.radius + .1, .05, 8, 40),new THREE.MeshBasicMaterial({color:0xff4757,fog:false}));ring.name=name;wrapG.add(ring);}
      ring.visible=true;
      ring.position.copy(c); ring.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), ax);
      at.copy(c).add(new THREE.Vector3(0, .6, 0));
    }
    wrapLabels.push({ id: 'wrap:' + name, text: `纏繞 ${name} ${turns > 0 ? '↻' : '↺'} ${Math.abs(turns).toFixed(2)} 圈`, pos: at, cls: 'bad' });
  }
}

/* ═════════════════════════ current: arrow + drifting particles ═════════════════════════ */
const curArrow = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(), 1, 0x4fd1ff, .25, .16);
scene.add(curArrow);
function layer(kn, dir) { const a = dir * DEG; return [Math.cos(a) * kn * KNOT, Math.sin(a) * kn * KNOT]; }
function currentAt(depth) {           // replicates world.CurrentProfile.mean_at (horizontal NED m/s)
  const c = W?.current; if (!c) return [0, 0];
  const sb = W.seabed_depth, s = layer(c.surface_kn, c.surface_dir), m = layer(c.mid_kn, c.mid_dir), b = layer(c.bottom_kn, c.bottom_dir);
  const md = sb / 2; let v;
  if (depth <= md) { const t = clamp(depth / md, 0, 1); v = [s[0] * (1 - t) + m[0] * t, s[1] * (1 - t) + m[1] * t]; }
  else { const t = clamp((depth - md) / Math.max(sb - md, 1e-6), 0, 1); v = [m[0] * (1 - t) + b[0] * t, m[1] * (1 - t) + b[1] * t]; }
  const above = sb - depth; if (above < 1) { const f = Math.max(0, above); v = [v[0] * f, v[1] * f]; }
  return v;
}
const NP = 900, HB = [9, 5, 9];
const partPos = new Float32Array(NP * 3);
for (let i = 0; i < NP; i++) for (let k = 0; k < 3; k++) partPos[i * 3 + k] = (Math.random() * 2 - 1) * HB[k];
const partGeo = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(partPos, 3));
const dot = (() => { const c = document.createElement('canvas'); c.width = c.height = 32; const x = c.getContext('2d');
  const g = x.createRadialGradient(16, 16, 0, 16, 16, 16); g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(.4, 'rgba(255,255,255,.6)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, 32, 32); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; })();
const particles = new THREE.Points(partGeo, new THREE.PointsMaterial({ color: 0xbfe3ef, size: .035, map: dot, transparent: true, opacity: .8, depthWrite: false }));
particles.frustumCulled = false; scene.add(particles);
let partCentre = null;
const flowField = createFlowField(), partFlow = [0, 0, 0];
function particleFlow(x, y, z) {      // host flow grid (NED) when available, else the mean profile
  const v = flowField.sample(z, -x, -y, performance.now(), partFlow);
  if (v) return v;
  const m = currentAt(-y); partFlow[0] = m[0]; partFlow[1] = m[1]; partFlow[2] = 0; return partFlow;
}
function updateParticles(dt, centre) {
  particles.visible = $('optFlow').checked;
  if (!particles.visible) return;
  if (!partCentre) partCentre = centre.clone();
  for (let i = 0; i < NP; i++) {
    const j = i * 3; let x = partPos[j], y = partPos[j + 1], z = partPos[j + 2];
    const v = particleFlow(x, y, z);
    x += -v[1] * dt; z += v[0] * dt; y += (Math.sin(i * 12.9 + x) * .02 - v[2]) * dt;
    // keep inside a box around the camera target (world-fixed particles, wrapped)
    const dx = x - centre.x, dy = y - centre.y, dz = z - centre.z;
    if (dx > HB[0]) x -= 2 * HB[0]; else if (dx < -HB[0]) x += 2 * HB[0];
    if (dy > HB[1]) y -= 2 * HB[1]; else if (dy < -HB[1]) y += 2 * HB[1];
    if (dz > HB[2]) z -= 2 * HB[2]; else if (dz < -HB[2]) z += 2 * HB[2];
    if (W && (y < -W.seabed_depth || y > 0)) y = centre.y + (Math.random() * 2 - 1) * HB[1] * .5;
    partPos[j] = x; partPos[j + 1] = y; partPos[j + 2] = z;
  }
  partGeo.attributes.position.needsUpdate = true;
}

/* ═════════════════════════ networking ═════════════════════════ */
const params = new URLSearchParams(location.search);
const REPLAY = params.get('replay') || document.documentElement.dataset.replay || window.QYSIM_REPLAY || null;
let menuSettings={};try{menuSettings=JSON.parse(localStorage.getItem('rov.menuSettings')||'{}');}catch{}
for(const [id,key]of [['optSticks','sticks'],['optFog','fog'],['optLabels','labels'],['optIntro','intro']])if(typeof menuSettings[key]==='boolean')$(id).checked=menuSettings[key];
const preferredPad=params.get('pad')||'auto';
let launchScene=params.get('scenario');
let launchControl=params.get('control')||storedControlLayout();
let launchSticker=params.get('sticker');
let launchMission=params.get('mission'),missionSignature='';
const WS_URL = params.get('ws') || (location.protocol === 'https:' ? `wss://${location.host}/ws` : `ws://${location.hostname || '127.0.0.1'}:8765`);
let ws = null, wsOpen = false, retry = 0, retryAt = 0, needResync = true, lastT = -1;
const renderState = createRenderState({P, Q, rovG, fleet, updateTether, params, fidelity: getFidelity(),
  link: createLinkPresenter()});
const videoLinkOverlay = installVideoLinkOverlay(vp);
let W = null, S = null, stateCount = 0;
let session = null, inputSequence = 0;
// Live join declares static_once; replay keeps full frames and never declares caps.
const stateMerger = createStateMerger();
let collectionOpen=false;
const collectionPanel=installCollectionPanel({onOpen(){collectionOpen=true;stopForCollection();},onClose(){collectionOpen=false;needResync=true;}});
const vision = installVision({send,canvas:renderer.domElement,getContext:()=>({renderer,scene,camera,environment:env,state:S || {},world:W || {},camMode,targets:visionTargets(S,fleet,cable)})});
let photoFeedback=null;
const photoClient=installExpeditionClient({send,getState:()=>S,getWorld:()=>W,getSession:()=>session,readOnly:!!REPLAY,
  onShutter:()=>{photoFeedback?.shutter();careerDive.photo();},
  notify:text=>{cockpit.message({message:text});expeditionPanel.notify(text);},
  capture:()=>new Promise((resolve,reject)=>{
    vision.assertPhoto();
    if(!S||!W){reject(Error('連線後才能拍照。'));return;}
    const restoreCamera = cameraRig.physicalCapture(S);
    renderer.render(scene,camera);
    const targets=engineeringPhotoTargets();
    const evidence=inspectObservation({scene,camera,environment:env,state:S,world:W,camMode,targets});
    const view=camMode;
    renderer.domElement.toBlob(blob=>resolve({blob,evidence,view}),'image/png');
    restoreCamera();
  })});
const cockpit = installCockpit({send,getState:()=>S,getWorld:()=>W,getSession:()=>session,wsUrl:WS_URL,canvas:renderer.domElement,renderer,capturePhoto:callback=>{renderer.render(scene,camera);renderer.domElement.toBlob(callback);},takePhoto:options=>photoClient.takePhoto(options),openCollection:()=>collectionPanel.open(),rememberVehicle:!REPLAY,readOnly:!!REPLAY});
const surfacePaint=installSurfacePaint({THREE,scene,camera,renderer,getState:()=>S,getTargets:()=>[worldG,seabed,...(env?[env.group]:[])],send,readOnly:!!REPLAY});
const rotorSpin = [];
const procedurePanel = installProcedure({send, readOnly: !!REPLAY,
  deck: {getIntro: () => intro, rov: rovG, getRotors: () => rotorOf}});
const campaignPanel = installCampaign({send, readOnly: !!REPLAY});
const chapterCards = installChapterCards({readOnly: !!REPLAY});
const missionPanel=installMissionPanel({send,getState:()=>S,readOnly:!!REPLAY});
const expeditionPanel=installExpeditionPanel({send,getSession:()=>session,takePhoto:()=>photoClient.takePhoto(),openCollection:()=>collectionPanel.open(),setOnboard:()=>setCam('onboard'),readOnly:!!REPLAY});
const pilotGuide=installPilotGuide({getState:()=>S,getWorld:()=>W,readOnly:!!REPLAY});
let startPresentation=null;
installDisplayPrefs();
const skipFrame = createFrameGate();
const careerDive = installCareerDive({send, getWorld: () => W, getCamMode: () => camMode, readOnly: !!REPLAY,
  showResult: outcome => results.show(outcome)});
const objectiveCard = installObjectiveCard({send, getSession: () => session, readOnly: !!REPLAY, career: careerDive});
const results = installResults({send, getState: () => S, getWorld: () => W, getSession: () => session,
  readOnly: !!REPLAY, onContracts: () => objectiveCard.showContracts(), onVisible: open => music.showResults(open),
  career: careerDive});
const achievements = installAchievements({readOnly: !!REPLAY});
$('offUrl').textContent = WS_URL;
const connectionNotice = installConnectionNotice({element: $('offline')});

function send(obj) { if (ws && wsOpen) { try { ws.send(JSON.stringify(obj)); return true; } catch { } } return false; }
function setConn(kind, text) { const el = $('conn'); el.className = 'pill ' + kind; el.textContent = text; }
const sonarPanel = createSonar(send);
const linkInbox = createLinkInbox({
  onWorld(m) { if (session) onWorld(m); },
  onState(m) { if (session) onState(m); },
  onSession(m) {
    session = m; needResync = true;
    try { sessionStorage.setItem(`rov.session:${WS_URL}:${cockpit.room}`, m.resume_token); } catch { }
    for (const id of ['btnLoad', 'btnReset', 'btnPause', 'btnCur']) $(id).disabled = !m.is_host;
  },
  onOther(m) {
    if (m.type === 'error' || m.type === 'operation_result') {
      photoClient.receive(m); cockpit.message(m);
      if (m.message) expeditionPanel.notify(m.message);
    }
  },
});
function connect() {
  if (REPLAY) { startReplay(REPLAY); return; }
  setConn('wait', '連線中…');
  try { ws = openRcLink(WS_URL); } catch (e) { scheduleRetry(); return; }
  ws.onopen = () => {
    wsOpen = true; retry = 0; needResync = true; session=null;inputSequence=0;
    linkInbox.dispose();
    stateMerger.reset();
    setConn('wait', '已連線 · 等待資料'); rcPump.reset();
    let token;try{token=sessionStorage.getItem(`rov.session:${WS_URL}:${cockpit.room}`);}catch{}
    send({type:'join',room_id:cockpit.room,name:cockpit.name,resume_token:token,model_id:cockpit.model,
      caps:VIEWER_CAPS});
  };
  // Coalesce state on the page so software-GL stalls cannot bury host_only behind a snapshot backlog.
  ws.onmessage = (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    // Deltas are merged in arrival order first; only complete snapshots are coalesced by the inbox.
    if (m.type === 'state') m = stateMerger.merge(m);
    linkInbox.receive(m);
  };
  ws.onclose = () => { wsOpen = false; ws = null; linkInbox.dispose(); setConn('stop', '離線'); connectionNotice.lost(); scheduleRetry(); };
  ws.onerror = () => { };
}
function scheduleRetry() {
  const d = Math.min(5000, 800 * 2 ** retry++);
  retryAt = performance.now() + d;
  setTimeout(connect, d);
}
setInterval(() => {
  const r = retryAt - performance.now();
  $('offRetry').textContent = !wsOpen && r > 0 ? `（${Math.ceil(r / 1000)} 秒後重試）` : !wsOpen ? '（連線中…）' : '';
}, 250);

function onWorld(m) {
  if(launchScene&&!REPLAY){const chosen=launchScene;launchScene=null;const seed=Number(params.get('seed')||42);if(session?.is_host&&(m.scenario?.key!==chosen||m.scenario?.seed!==seed)){send({type:'scenario',key:chosen,seed});return;}}
  if(launchControl&&!REPLAY){send({type:'operation_mode',value:launchControl});launchControl=null;}
  if(launchSticker!==null&&!REPLAY){send({type:'operation',action:'appearance',sticker:launchSticker});launchSticker=null;}
  if(launchMission==='campaign')launchMission=null;
  if(launchMission&&!REPLAY){if(session?.is_host)send({type:'operation',action:'mission_mode',mode:launchMission});launchMission=null;}
  const firstOrNew = !W || W.scenario?.key !== m.scenario?.key || W.scenario?.seed !== m.scenario?.seed;
  W = m;
  loadModel(m.vehicle);
  buildWorld();
  missionSignature='';
  $('scnName').textContent = m.scenario?.name || '—';
  $('brief').textContent = m.scenario?.brief || '';
  fillCatalogue(firstOrNew);
  connectionNotice.connected();
  if (firstOrNew && (!session || session.is_host) && (m.room?.players?.length||1)<=1) procedurePanel.startIntro(startIntro);
}

function onState(m) {
  sonarPanel.receive(m);
  if(m.model_id !== S?.model_id)needResync=true;
  if(m.control_generation !== S?.control_generation)needResync=true;
  if (lastT >= 0 && m.t < lastT - 0.5) needResync = true;    // scenario loaded / reset → server RC reset to locked
  if (m.controller?.generation !== S?.controller?.generation) needResync = true;
  if (m.controller?.revision !== S?.controller?.revision) needResync = true;
  lastT = m.t;
  flowField.ingest(m.flow_field, performance.now());
  S = m; stateCount++;
  renderState.ingest(m, rep);
  if(session && m.room){session.is_host=m.room.host_id===session.player_id;for(const id of ['btnLoad','btnReset','btnPause','btnCur'])$(id).disabled=!session.is_host;}
  cockpit.update(m);activeModel?.updateArm(m.operations?.arm);
  applyVehicleSticker(activeModel,m.appearance?.sticker||'none');surfacePaint.update(m);
  missionPanel.update(m);
  procedurePanel.update(m);
  campaignPanel.update(m);
  coldOpen.update(m, W);
  if (!REPLAY) prologue.update(m);
  chapterCards.update(m);
  expeditionPanel.update(m);photoClient.update(m);
  pilotGuide.update(m);
  startPresentation?.update(m, W);
  careerDive.update(m);
  objectiveCard.update(m);
  onboarding.update(m);
  results.update(m);
  achievements.update(m);
  if(m.mission){const objectives=m.mission.mode==='expedition'?expeditionObjectives(m):m.mission.mode==='scenario_training'?(W?.objectives||[]):(m.mission.targets||[]).map(t=>({...t,kind:'inspect'}));const key=JSON.stringify([m.mission.mode,objectives.map(t=>[t.id,t.point,t.done])]);if(key!==missionSignature){missionSignature=key;buildObjectives(objectives);}}
  if(m.model_id&&m.model_id!==activeModelId){const def=W?.vehicle_catalogue?.find(d=>d.id===m.model_id);if(def)loadModel(def);}
  if (needResync && !m.remote_control && m.rc) {
    rc.rc_lock = m.rc.rc_lock; rc.keep_depth = m.rc.keep_depth; rc.left_switch = m.rc.left_switch; rc.right_switch = m.rc.right_switch;
    needResync = false;
  }
  setConn('run', rep ? '回放 · 錄製的訓練飛行' : m.paused ? '已連線 · 暫停' : '已連線');
  if (W) connectionNotice.connected();
  target.pos = P(m.pos, target.pos); Q(m.q, target.q);
  if (!target.init) { rovG.position.copy(target.pos); rovG.quaternion.copy(target.q); target.init = true; }
  updateRoute(m.nav);
  const ch = m.current_here || [0, 0, 0], cv = P(ch), sp = cv.length();
  if (sp > 1e-3) curArrow.setDirection(cv.clone().normalize());
  curArrow.setLength(.3 + sp / KNOT * .45, .16, .1);
  curArrow.visible = sp > 1e-3 && !introActive() && showsTruth(m);
  checkEvents(m.events || []);
  uiDirty = true;
}
const target = { pos: new THREE.Vector3(), q: new THREE.Quaternion(), init: false };

function expeditionObjectives(state){
  return [...(state.expedition?.active?.steps||[]).filter(step=>step.point&&!step.completed).map(step=>({...step,kind:'inspect',done:step.completed})),
    ...(state.expedition?.markers||[]).filter(marker=>marker.point||marker.pos).map(marker=>({...marker,id:'discovery:'+marker.entity_id,point:marker.point||marker.pos,kind:'checkpoint',radius:.35}))];
}
function engineeringPhotoTargets(){
  const id=S?.expedition?.active?.id;
  const needed=new Set((S?.expedition?.active?.steps||[]).filter(step=>step.role==='photo'&&!step.completed).map(step=>step.entity_id));
  return (S?.operations?.objects||[]).filter(object=>id&&object.task_id===id&&needed.has(object.id)).map(object=>({entity_id:object.id,category:'engineering',mesh:fleet.objects.get(object.id)})).filter(item=>item.mesh);
}

function updateRoute(nav) {
  const r = nav?.route || [];
  const a = routeLine.geometry.attributes.position.array, n = Math.min(r.length, MAXR);
  const v = new THREE.Vector3();
  for (let i = 0; i < n; i++) { P(r[i], v); a[i * 3] = v.x; a[i * 3 + 1] = v.y; a[i * 3 + 2] = v.z; }
  routeLine.geometry.setDrawRange(0, n); routeLine.geometry.attributes.position.needsUpdate = true;
  routeLine.visible = n > 1;
  navTarget.visible = !!nav?.target; if (nav?.target) P(nav.target, navTarget.position);
}

let lastEvT = null;
function checkEvents(evs) {
  if (!evs.length) { lastEvT = lastEvT ?? -1; return; }
  const newest = evs[evs.length - 1];
  if (lastEvT === null) { lastEvT = newest.t; return; }       // don't flash history on connect
  if (newest.t > lastEvT) {
    lastEvT = newest.t;
    const f = $('flash'); f.className = 'flash ' + (newest.severity || 'touch');
    setTimeout(() => (f.className = 'flash'), 350);
  }
}

/* ═════════════════════════ input → RC ═════════════════════════ */
const CH = ['left_ud', 'left_lr', 'right_ud', 'right_lr', 'left_wave', 'right_wave'];
const input = installInput({blocked: () => prologueControlsBlocked(S) || collectionOpen || pauseMenuOpen()
    || resultsOpen() || feedbackOpen(),
  camera: () => cameraRig.cycle(), tick: () => inputTick(),
  preferred: () => preferredPad, gain: () => +$('kbGain').value,
  setMode: mode => { $('opMode').value = mode; $('opMode').dispatchEvent(new Event('change')); },
  arm: () => { $('armMode').click(); }});
const {rc, hold, keys, touch, out, toggleLock, toggleDepth, cycleMode, cycleLed} = input;
startPresentation = installStartPresentation({send, rc, readOnly: !!REPLAY});
const onboarding = installOnboarding({input, readOnly: !!REPLAY});
installPauseMenu({input, send, state: () => S, replay: !!REPLAY, tutorial: onboarding,
  extraActions: () => [...procedurePanel.pauseActions(), ...careerDive.pauseActions()]});
installFeedbackReport({
  input,
  getState: () => S,
  getWorld: () => W,
  capture() {
    renderer.render(scene, camera);
    return renderer.domElement;
  },
  getPerformance: () => window.__viewer?.performance?.(),
});

document.addEventListener('visibilitychange',()=>{
  if(!document.hidden){needResync=true;return;}
  keys.clear();hold.photo.clear();hold.record.clear();rc.rc_lock=1;
  if(session && !S?.controller){const stopped={...rcMessage(),rc_lock:1,photo:0,record:0};CH.forEach(c=>stopped[c]=1500);send({type:'rc',rc:stopped,seq:++inputSequence});}
});
function stopForCollection(){
  keys.clear();hold.photo.clear();hold.record.clear();CH.forEach(c=>{touch[c]=0;out[c]=0;});rc.rc_lock=1;
  if(session)send({type:'rc',rc:{...rcMessage(),photo:0,record:0},seq:++inputSequence,controller_generation:S?.controller?.generation});
}

let photoPressed=false;
const rcPump = createRcPump({ transport: () => (wsOpen ? ws : null), sequence: () => ++inputSequence });
function rcMessage() {
  const m = {};
  for (const c of CH) m[c] = cockpit.armMode ? 1500 : Math.round(1500 + 500 * out[c]);
  m.rc_lock = rc.rc_lock; m.keep_depth = rc.keep_depth; m.left_switch = rc.left_switch; m.right_switch = rc.right_switch;
  Object.assign(m, assistFields(S, rc));
  m.photo = 0; m.record = collectionOpen?0:hold.record.size ? 1 : 0;
  if(collectionOpen){CH.forEach(c=>m[c]=1500);m.rc_lock=1;}
  return m;
}
function inputTick() {
  const pad = input.sample();
  input.feedback(S);
  const pressed=!collectionOpen&&hold.photo.size>0;
  if(pressed&&!photoPressed&&!REPLAY)photoClient.takePhoto();photoPressed=pressed;
  if (S?.controller) for (const c of CH) out[c] = clamp(((S.controller.axes[c] ?? 1500) - 1500) / 500, -1, 1);
  if (rep && S?.rc) for (const c of CH) out[c] = clamp(((S.rc[c] ?? 1500) - 1500) / 500, -1, 1);   // replay: recorded sticks
  const msg = rcMessage();
  // Replay must not send RC or keep the worker repeating a packet (AGENTS.md input heartbeat).
  const live = !REPLAY && !document.hidden && !!session && !needResync;
  rcPump.offer(msg, { live, generation: S?.controller?.generation });
  $('padInfo').textContent = S?.controller
    ? (S.controller.connected ? 'Q-iRC USB 已連接 · 搖桿、波輪、模式、燈光與功能鍵可用' : S.controller.reason)
    : pad ? `手把：${pad.id.slice(0, 48)}` : '未偵測到手把（按任一手把按鍵喚醒）。';
  drawSticks(msg);
}
rcPump.start(inputTick);

function drawSticks(msg) {
  const place = (el, x, y) => {
    const r = elementSize(el).width / 2 * .62;   // cached size: no forced layout per input tick (hud/canvas.js)
    el.querySelector('.knob').style.transform = `translate(${x * r}px, ${-y * r}px)`;
  };
  place($('stickL'), out.left_lr, out.left_ud); place($('stickR'), out.right_lr, out.right_ud);
  for (const [id, c] of [['wheelL', 'left_wave'], ['wheelR', 'right_wave']]) {
    const el = $(id);
    el.querySelector('.wk').style.transform = `translateX(${out[c] * (elementSize(el).width / 2 - 14)}px)`;
  }
  // panel mirror
  for (const c of CH) {
    const row = mapRows[c]; if (!row) continue;
    row.pwm.textContent = msg[c];
    const v = out[c], pct = Math.abs(v) * 50;
    row.fill.style.left = v >= 0 ? '50%' : (50 - pct) + '%'; row.fill.style.width = pct + '%';
  }
  $('bLock').classList.toggle('on', !!rc.rc_lock); $('bLock').textContent = rc.rc_lock ? '已鎖定' : '已解鎖';
  $('bDepth').classList.toggle('on', !!rc.keep_depth);
  $('bMode').textContent = '模式 ' + 'ASC'[rc.left_switch];
  $('bLed').textContent = 'LED ' + rc.right_switch; $('bLed').classList.toggle('on', rc.right_switch > 0);
  $('bPhoto').classList.toggle('on', hold.photo.size > 0); $('bRec').classList.toggle('on', hold.record.size > 0);
}

const {meters: mapRows, update: buildMapTable} = installChannelTable();

/* ═════════════════════════ training / panel controls ═════════════════════════ */
function fillCatalogue(select) {
  const sel = $('scnSel'), cat = W?.catalogue || [];
  const prev = sel.value;
  sel.innerHTML = cat.map((c) => `<option value="${esc(c.key)}">${esc(c.name)}</option>`).join('');
  sel.value = select ? W.scenario.key : (prev || W.scenario.key);
  if (select && W.scenario.seed != null) $('seed').value = W.scenario.seed;
  syncSeed();
}
function syncSeed() { $('seed').disabled = false; }
$('scnSel').onchange = () => {
  syncSeed();
  const c = (W?.catalogue || []).find((x) => x.key === $('scnSel').value);
  if (c) $('brief').textContent = c.brief + (c.key !== W.scenario.key ? '（按「載入」開始）' : '');
};
$('btnLoad').onclick = () => {
  const key = $('scnSel').value; if (!key) return;
  const msg = { type: 'scenario', key };
  if ($('seed').value !== '') msg.seed = +$('seed').value;
  send(msg);
};
$('btnReset').onclick = () => send({ type: 'reset' });
$('btnPause').onclick = () => send({ type: 'pause', value: !(S && S.paused) });
$('btnRelease').onclick = () => send({ type: 'remote_release' });
$('opMode').onchange = () => { rememberControlLayout($('opMode').value); send({ type: 'operation_mode', value: $('opMode').value }); };
const updateTetherReel = installTetherReel({ send });
$('kbGain').oninput = () => ($('kbGainV').textContent = Math.round($('kbGain').value * 100) + '%'); $('kbGain').oninput();

// current override sliders
const CUR_KEYS = [['surface', '表層'], ['mid', '中層'], ['bottom', '底層']];
{
  const host = $('curSliders');
  for (const [k, lbl] of CUR_KEYS) {
    host.insertAdjacentHTML('beforeend',
      `<div class="sl"><div class="row"><label for="c_${k}_kn">${lbl}流速</label><span id="c_${k}_knV"></span></div><input type="range" id="c_${k}_kn" min="0" max="4" step="0.1" value="0"></div>` +
      `<div class="sl"><div class="row"><label for="c_${k}_dir">${lbl}流向</label><span id="c_${k}_dirV"></span></div><input type="range" id="c_${k}_dir" min="0" max="355" step="5" value="90"></div>`);
  }
  host.parentElement.querySelectorAll('input[type=range]').forEach((el) => {
    const u = () => { $(el.id + 'V').textContent = el.id.endsWith('kn') ? (+el.value).toFixed(1) + ' kn' : el.id.endsWith('dir') ? String(el.value).padStart(3, '0') + '°' : (+el.value).toFixed(2); };
    el.addEventListener('input', u); u();
  });
}
function fillCurrentSliders() {
  const c = W?.current; if (!c) return;
  for (const [k] of CUR_KEYS) {
    for (const f of ['kn', 'dir']) { const el = $(`c_${k}_${f}`); if (document.activeElement !== el) { el.value = c[`${k}_${f}`]; el.dispatchEvent(new Event('input')); } }
  }
  const t = $('c_turbulence'); t.value = c.turbulence ?? .15; t.dispatchEvent(new Event('input'));
}
$('btnCur').onclick = () => {
  const m = { type: 'current', turbulence: +$('c_turbulence').value };
  for (const [k] of CUR_KEYS) { m[`${k}_kn`] = +$(`c_${k}_kn`).value; m[`${k}_dir`] = +$(`c_${k}_dir`).value; }
  send(m);
};

/* ═════════════════════════ camera modes ═════════════════════════ */
const cameraRig = createCameraRig({THREE, camera, controls, rovG, renderer, params, fidelity: getFidelity(),
  getAnchor: () => cameraAnchor, getObstacles: () => [seabed, ...(structureSet?.raycastMeshes() || [])],
  onMode(m, name) {
    camMode = m;
    $('camBtn').dataset.mode = m;
    $('camBtn').dataset.label = `視角：${name}（V）`;
    $('xhair').hidden = m !== 'onboard';
    placeholder.visible = m !== 'onboard';
    if (activeModel) activeModel.model.visible = m !== 'onboard';
  }});
cameraRig.bindInput(input);
surfacePaint.bindInput(input);
procedurePanel.bindInput(input);
campaignPanel.bindInput(input);
sonarPanel.bindInput(input);
vision.bindInput(input);
let camMode = cameraRig.mode;
const cameraLook = installCameraLook({renderer, getMode: () => camMode, fidelity: getFidelity()});
const cine = cameraRig.cine;
const setCam = m => cameraRig.setMode(m);
const updateCamera = dt => cameraRig.update(dt);
$('camBtn').onclick = () => cameraRig.cycle();
const _f = new THREE.Vector3(), _v = new THREE.Vector3(), _q = new THREE.Quaternion();

/* ═════════════════════════ labels ═════════════════════════ */
const worldLabels = createWorldLabels({container: $('labels'), camera, enabled: () => $('optLabels').checked});
const drawLabels = worldLabels.draw;

/* ═════════════════════════ instruments ═════════════════════════ */
const adi = $('adi');
function drawADI(pitch, roll, hdg) {
  drawROVAttitude(adi,{pitch:pitch/DEG,roll:roll/DEG,heading:hdg});
}

const prof = $('profile'), pctx = prof.getContext('2d');
function arrow(ctx, x, y, dirDeg, len, col, lw = 2) {
  const a = dirDeg * DEG, dx = Math.sin(a) * len, dy = -Math.cos(a) * len;
  ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = lw;
  ctx.beginPath(); ctx.moveTo(x - dx / 2, y - dy / 2); ctx.lineTo(x + dx / 2, y + dy / 2); ctx.stroke();
  const hx = x + dx / 2, hy = y + dy / 2, ang = Math.atan2(dy, dx);
  ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(hx - 9 * Math.cos(ang - .45), hy - 9 * Math.sin(ang - .45)); ctx.lineTo(hx - 9 * Math.cos(ang + .45), hy - 9 * Math.sin(ang + .45)); ctx.fill();
}
function drawProfile() {
  const Wd = prof.width, H = prof.height; pctx.clearRect(0, 0, Wd, H);
  pctx.font = '16px ' + C('--f-data'); pctx.textBaseline = 'middle';
  if (!W) { pctx.fillStyle = '#7f99a8'; pctx.fillText('等待世界資料…', 20, H / 2); return; }
  const c = W.current, sb = W.seabed_depth, y0 = 22, y1 = H - 18, x0 = 58, x1 = 300;
  const maxKn = Math.max(1, c.surface_kn, c.mid_kn, c.bottom_kn) * 1.1;
  const Y = (d) => y0 + (d / sb) * (y1 - y0), X = (kn) => x0 + kn / maxKn * (x1 - x0);
  pctx.strokeStyle = '#1f3a4a'; pctx.lineWidth = 1;
  for (const d of [0, sb / 2, sb]) { pctx.beginPath(); pctx.moveTo(x0, Y(d)); pctx.lineTo(Wd - 10, Y(d)); pctx.stroke(); }
  pctx.fillStyle = '#4a4636'; pctx.fillRect(x0, y1, Wd - 10 - x0, H - y1);
  pctx.fillStyle = '#7f99a8'; pctx.textAlign = 'right';
  for (const d of [0, sb / 2, sb]) pctx.fillText(Math.round(d) + 'm', x0 - 6, Y(d));
  // speed profile curve
  pctx.strokeStyle = '#4fd1ff'; pctx.lineWidth = 2.5; pctx.beginPath();
  for (let i = 0; i <= 40; i++) { const d = sb * i / 40, v = currentAt(d), kn = Math.hypot(v[0], v[1]) / KNOT; i ? pctx.lineTo(X(kn), Y(d)) : pctx.moveTo(X(kn), Y(d)); }
  pctx.stroke();
  // layer arrows
  pctx.textAlign = 'left';
  const rows = [['表層', 0, c.surface_kn, c.surface_dir], ['中層', sb / 2, c.mid_kn, c.mid_dir], ['底層', sb, c.bottom_kn, c.bottom_dir]];
  for (const [n, d, kn, dir] of rows) {
    const y = clamp(Y(d), y0 + 8, y1 - 8);
    arrow(pctx, 330, y, dir, 12 + kn * 8, '#4fd1ff');
    pctx.fillStyle = '#d6e4ec'; pctx.fillText(`${n} ${kn.toFixed(1)}kn ${String(Math.round(dir)).padStart(3, '0')}°`, 356, y);
  }
  // ROV depth + local current
  if (S) {
    const d = S.pos[2], y = Y(clamp(d, 0, sb)), ch = S.current_here || [0, 0, 0];
    pctx.strokeStyle = '#f2b705'; pctx.setLineDash([6, 4]); pctx.lineWidth = 1.5; pctx.beginPath(); pctx.moveTo(x0, y); pctx.lineTo(x1, y); pctx.stroke(); pctx.setLineDash([]);
    const kn = S.current_kn || 0, dir = (Math.atan2(ch[1], ch[0]) / DEG + 360) % 360;
    pctx.fillStyle = '#f2b705'; pctx.beginPath(); pctx.arc(X(kn), y, 5, 0, 7); pctx.fill();
    pctx.textAlign = 'left'; pctx.fillText(`ROV ${kn.toFixed(2)}kn ${String(Math.round(dir)).padStart(3, '0')}°`, x0 + 4, y - 12 < y0 ? y + 12 : y - 12);
  }
  pctx.fillStyle = '#7f99a8'; pctx.textAlign = 'left'; pctx.fillText('↑N 流向 = 水流去向', 330, 10);
}

let thrRows = [];
const thrLabel = thrusterLabel;
function buildThrBars() {
  const host = $('thrBars'); host.innerHTML = ''; thrRows = [];
  (W?.thrusters || []).forEach((t) => {
    const row = document.createElement('div'); row.className = 'thr';
    row.innerHTML = `<span class="nm">${esc(thrLabel(t.name))}</span><div class="track c"><div class="fill"></div></div><span class="pc">0</span><span class="hp">100%</span>`;
    host.appendChild(row); thrRows.push({ row, fill: row.querySelector('.fill'), pc: row.querySelector('.pc'), hp: row.querySelector('.hp') });
  });
}

/* ═════════════════════════ UI refresh (throttled) ═════════════════════════ */
let uiDirty = false, uiLast = 0;
const setTxt = (id, v) => { const el = $(id); if (el.textContent !== String(v)) el.textContent = v; };
const setHTML = (id, v) => { const el = $(id); if (el._h !== v) { el.innerHTML = v; el._h = v; } };
function updateUI() {
  const s = S; if (!s) return;
  const [roll, pitch] = s.euler || [0, 0, 0];
  const reading = pilotReadings(s, W);
  const hdg = reading.heading;
  const depth = reading.depth;
  const alt = reading.altitude;
  setTxt('gDepth', depth.toFixed(2)); setTxt('gHdg', String(Math.round(hdg) % 360).padStart(3, '0'));
  setTxt('gAtt', `${pitch.toFixed(0)}° / ${roll.toFixed(0)}°`); setTxt('gSpd', formatKnots(reading.speedKn));
  setTxt('gBat', (s.battery ?? 0).toFixed(0)); $('gBat').closest('.g').classList.toggle('low', s.battery < 20);
  setTxt('gAlt', alt == null ? '—' : alt.toFixed(2)); $('gAlt').closest('.g').classList.toggle('low', alt != null && alt < 1);
  setTxt('gHold', s.depth_hold != null ? `定深設定點 ${s.depth_hold.toFixed(2)} m` : '');
  setTxt('rDepth', depth.toFixed(1)); setTxt('rAlt', alt == null ? '—' : alt.toFixed(1)); setTxt('rSpd', formatKnots(reading.speedKn)); setTxt('rCur', formatKnots(reading.currentKn));
  drawADI(pitch * DEG, roll * DEG, hdg);

  // HUD
  const lk = $('lockBadge');
  lk.classList.toggle('locked', !!s.locked);
  const hm = $('hMode'); hm.textContent = `${s.ctrl_mode} 模式`; hm.className = 'chip ' + (s.ctrl_mode === 'A' ? '' : s.ctrl_mode === 'S' ? 'on' : 'warn');
  const hh = $('hHold'); hh.textContent = s.keep_depth ? `定深 ${s.depth_hold != null ? s.depth_hold.toFixed(1) + ' m' : '開'}` : '定深 關'; hh.className = 'chip ' + (s.keep_depth ? 'on' : 'dim');
  setTxt('hOp', s.operation_mode==='UAV_CHN'?'ROV 雙桿':s.operation_mode);
  const led = s.rc?.right_switch || 0; $('hLed').hidden = !led; setTxt('hLed', `LED ${led}`);
  $('hRec').hidden = !s.recording;
  $('hPaused').hidden = !s.paused;
  const nav = s.nav || {}; $('hNav').hidden = !nav.mode || nav.mode === 'IDLE'; setTxt('hNav', `NAV ${nav.mode || ''}${nav.route?.length ? ` ${nav.route_i}/${nav.route.length}` : ''}`);
  $('hRemote').hidden = !s.remote_control;
  if (document.activeElement !== $('opMode')) $('opMode').value = s.operation_mode;
  buildMapTable(s.operation_mode);
  $('btnPause').textContent = s.paused ? '繼續' : '暫停'; $('btnPause').classList.toggle('on', !!s.paused);
  const lv = s.power?.lights_on === false ? 0 : [0, 0.55, 1][led] || 0;   // a tripped or empty supply
  leds.forEach((l) => (l.intensity = lv * 260));                  // candela (physically based lights)
  beamMat.uniforms.uI.value = lv;
  for (const b of beams) { b.cone.visible = lv > 0 && camMode !== 'onboard'; b.glow.visible = lv > 0; b.glow.material.opacity = 0.5 + 0.5 * lv; }

  // thrusters
  (s.thrust || []).forEach((t, j) => {
    const r = thrRows[j]; if (!r) return;
    const pct = Math.min(1, Math.abs(t)) * 50, h = s.health?.[j] ?? 1;
    r.fill.style.left = t >= 0 ? '50%' : (50 - pct) + '%'; r.fill.style.width = pct + '%';
    r.fill.style.background = Math.abs(t) > .95 ? C('--warn') : C('--jet');
    r.pc.textContent = Math.round(t * 100);
    r.hp.textContent = h <= 0.01 ? '失效' : Math.round(h * 100) + '%';
    r.row.classList.toggle('dmg', h < .999);
  });

  // tether
  const t = s.tether || {};
  setTxt('tLen', (t.length ?? 0).toFixed(1)); setTxt('tMax', (t.max_length ?? 0).toFixed(0));
  $('tLenFill').style.width = (100 * (t.length || 0) / (t.max_length || 1)) + '%';
  for (const [k, id] of [['tension_rov', 'tRov'], ['tension_spool', 'tSpool']]) {
    const T = t[k] || 0; setTxt(id, `${T.toFixed(0)} N`);
    const f = $(id + 'Fill'); f.style.width = gaugePercent(T) + '%';
    f.style.background = '#' + tensionColor(T, _c, warnLoad(t, k)).getHexString();
    f.nextElementSibling.style.left = gaugePercent(warnLoad(t, k)) + '%';
  }
  const ts = $('tState');
  if (t.broken) { ts.textContent = '已斷裂'; ts.className = 'chip bad'; }
  else if (t.warn) { ts.textContent = '張力過高'; ts.className = 'chip warn'; }
  else if (t.snagged_on?.length) { ts.textContent = '卡纜'; ts.className = 'chip warn'; }
  else { ts.textContent = '正常'; ts.className = 'chip on'; }
  updateTetherReel(t, s.t);
  const wr = Object.entries(t.wraps || {}).filter(([, v]) => Math.abs(v) >= .05);
  setHTML('tWraps', [
    wr.length ? '纏繞：' + wr.map(([n, v]) => `<b style="color:${Math.abs(v) >= .25 ? 'var(--bad)' : 'var(--amber)'}">${esc(n)} ${v > 0 ? '↻' : '↺'}${Math.abs(v).toFixed(2)} 圈</b>`).join('、') : '無纏繞',
    t.snagged_on?.length ? `卡在：<b style="color:var(--amber)">${t.snagged_on.map(esc).join('、')}</b>` : '',
    t.contact_nodes ? `接觸節點 ${t.contact_nodes}` : '',
  ].filter(Boolean).join(' · '));

  // collisions / damage / log
  const ev = (s.events || []).slice().reverse().slice(0, 8);
  const SEV = { touch: '輕觸', hard: '撞擊', severe: '嚴重' };
  setHTML('events', ev.length ? ev.map((e) => `<li><span class="t">${fmtT(e.t)}</span><span class="sev ${esc(e.severity)}">${SEV[e.severity] || esc(e.severity)}</span><span class="x">${esc(e.obstacle)} · ${(+e.speed || 0).toFixed(2)} m/s${e.where ? ' · ' + esc(e.where) : ''}</span></li>`).join('') : '<li class="hint">無碰撞紀錄</li>');
  const dm = (s.damage || []).slice().reverse();
  setHTML('damage', dm.map((d) => `<li><span class="t">${fmtT(d.t)}</span><span class="sev severe">損傷</span><span class="x">${esc(typeof d.thruster === 'number' ? thrLabel(W?.thrusters?.[d.thruster]?.name ?? 'T' + (d.thruster + 1)) : thrLabel(d.thruster))} 健康 ${Math.round((d.health ?? 0) * 100)}%</span></li>`).join(''));
  setHTML('log', (s.log || []).slice().reverse().map((l) => `<li><span class="t">${esc(l.stamp || fmtT(l.t))}</span><span class="x">${esc(l.text)}</span></li>`).join(''));

  // training
  const sc = s.score || {}, lim = missionTimeLimit(s, W);
  setTxt('score', scoreValue(s));
  setTxt('timer', `${fmtT(sc.elapsed)} / ${lim ? fmtT(lim) : '—'}`);
  $('timeFill').style.width = lim ? clamp(100 * (sc.elapsed || 0) / lim, 0, 100) + '%' : '0%';
  $('timeFill').style.background = lim && sc.elapsed > lim * .85 ? C('--warn') : C('--jet');
  const objs = sc.objectives || [];
  setTxt('scoreState', scoreSummary(s));
  setHTML('objs', objs.map((o, i) => {
    const cls = o.done ? 'done' : i === sc.current_index ? 'cur' : '';
    return `<li class="${cls}"><span class="ic">${o.done ? '✓' : i === sc.current_index ? '▶' : '○'}</span><span>${esc(o.label)}${o.hold_s ? `<span class="hint"> · 停留 ${o.hold_s}s</span>` : ''}</span><span></span><div class="track"><div class="fill" style="width:${(o.done ? 1 : o.progress || 0) * 100}%"></div></div></li>`;
  }).join(''));
  const pens = sc.penalties || [];
  setHTML('pens', pens.slice(-6).reverse().map((p) => `<div class="row"><span>${fmtT(p.t)} ${esc(p.reason)}</span><span>−${p.points}</span></div>`).join(''));

  // banner
  const bn = $('banner');
  if (sc.failed) { bn.className = 'banner fail'; bn.innerHTML = `任務失敗<small>${esc(sc.failed)}</small>`; bn.hidden = false; }
  else if (t.broken) { bn.className = 'banner fail'; bn.innerHTML = '纜線斷裂<small>ROV 失去連線，請重置情境</small>'; bn.hidden = false; }
  else if (sc.finished) { bn.className = 'banner win'; bn.innerHTML = `任務完成 · ${sc.score} 分<small>用時 ${fmtT(sc.elapsed)}，扣分 ${sc.penalty_total || 0}</small>`; bn.hidden = false; }
  else if (t.warn) { bn.className = 'banner warn'; bn.innerHTML = `纜線張力 ${Math.round(t.tension_max || 0)} N<small>減少拉扯、檢查纏繞</small>`; bn.hidden = false; }
  else bn.hidden = true;
  drawProfile();
}

function updateObjectives(time) {
  const objs = S?.mission?.mode==='expedition'?expeditionObjectives(S):S?.score?.objectives; if (!objs) return null;
  let ci = S?.mission?.mode==='expedition'?0:S.score.current_index;let cur = null;
  if(S.mission?.mode==='inspection_coop'){let distance=Infinity;ci=-1;objMarkers.forEach((m,i)=>{if(objs[i]?.done)return;const d=m.g.position.distanceToSquared(rovG.position);if(d<distance){distance=d;ci=i;}});}
  objMarkers.forEach((m, i) => {
    const o = objs[i] || m.o, isCur = i === ci && !o.done;
    const col = o.done ? 0x3ddc97 : isCur ? 0xf2b705 : 0x7f99a8;
    m.mat.color.setHex(col); m.wire.color.setHex(col);
    m.mat.fog = !isCur; m.wire.fog = !isCur;
    m.mat.opacity = isCur ? .6 + .35 * Math.sin(time * 5) : o.done ? .55 : .45;
    if (m.bill) m.mat.opacity *= objectiveFade(m.g.position, Math.max(.3, o.radius || 1), camera, vp);
    if (!m.bill && m.o.kind !== 'inspect') objectiveNearFade(m, Math.max(.3, o.radius || 1), camera);
    m.g.scale.setScalar(isCur ? 1 + .06 * Math.sin(time * 5) : 1);
    if (m.bill) { _v.copy(camera.position).sub(m.g.position); m.bill.rotation.set(0, Math.atan2(_v.x, _v.z), 0); }
    if (isCur) cur = { o, m };
  });
  return cur;
}

/* ═════════════════════════ render loop ═════════════════════════ */
let vpRect = { width: 1, height: 1 };
function resize() {
  const r = vpRect = vp.getBoundingClientRect();
  renderer.setSize(Math.max(1, r.width), Math.max(1, r.height), false);
  camera.aspect = r.width / Math.max(1, r.height); camera.updateProjectionMatrix();
}

// Smooth the cable like the ROV pose (states arrive at 30 Hz), pin its end to the rendered gland
// so it never detaches from the vehicle, and draw it as a real-thickness (9.5 mm) cable.
const _gl = new THREE.Vector3();
function renderTether(dt) {
  const t = tetherInfo, n = tetherDisp.length;
  if (!t || n < 2) { cable.hide(); return; }
  for (let i = 0; i < n; i++) tetherDisp[i].copy(tetherTarget[i]);
  if (!t.broken && target.init) { rovG.updateMatrixWorld(); tetherDisp[n - 1].copy(rovG.localToWorld(_gl.copy(GLAND_LOCAL))); }
  const lp = tetherLine.geometry.attributes.position.array;
  for (let i = 0; i < n; i++) { lp[i * 3] = tetherDisp[i].x; lp[i * 3 + 1] = tetherDisp[i].y; lp[i * 3 + 2] = tetherDisp[i].z; }
  tetherLine.geometry.attributes.position.needsUpdate = true;
  if (t.broken) { cable.hide(); return; }
  cable.update(tetherDisp, (s, out) => cableTensionColor(t, s, tetherDisp, out));
}

/* ═════════════════════════ deploy intro + pilot PiP ═════════════════════════ */
let introAssetsP = null, intro = null, pip = null;
const loadIntroAssets = () => (introAssetsP ||= DeployIntro.loadAssets('models/'));
function introActive() { return !!(intro && intro.playing); }
function endIntroUI() {
  vp.classList.remove('intro'); $('skipIntro').hidden = true;
  tetherLine.visible = true;
}
// held: open on the aft deck and wait; the returned function starts the launch (deployment procedure).
async function startIntro(held = false) {
  if (params.get('chapter') === 'prologue') return null;
  if (!W || !$('optIntro').checked || params.has('nointro')) return null;
  if (MOVIE && movie.introDone) return;
  const assets = await loadIntroAssets();
  introStarts++;
  if (intro) { intro.dispose(); intro = null; }
  intro = new DeployIntro(scene, { spool: W.spool || [-4, 0, 0], start: startPresentation.introStart(W, S?.pos || [0, 0, 3]), seabed: W.seabed_depth || 30, assets });
  intro.showVehicle(() => activeModel?.model);       // the onboard view hides the hull; the intro shows it
  vp.classList.add('intro'); $('skipIntro').hidden = held;
  let wasPaused = !!S?.paused;
  if (!wasPaused && !held) send({ type: 'pause', value: true });
  intro.play(rovG, camera, () => {
    endIntroUI();
    intro?.dispose();                           // the spool station holds station from here on (deploy_intro.js)
    target.init = false;                        // snap back to the simulated pose
    if (!wasPaused) send({ type: 'pause', value: false });
  });
  if (!held) return null;
  const heldIntro = intro;
  heldIntro.hold();
  return function launchFromDeck() {
    wasPaused = !!S?.paused;
    if (!wasPaused) send({ type: 'pause', value: true });
    $('skipIntro').hidden = false;
    heldIntro.release();
  };
}
installIntroSkip({input, button: $('skipIntro'), skip: () => intro?.skip(), active: introActive});
let introStarts = 0;
window.__intro = () => intro && { t: intro.t, playing: intro.playing, starts: introStarts, held: !!intro.held };
async function ensurePip() {
  const on = $('optPip').checked && !params.has('nopip');
  $('pip').hidden = !on;
  if (!on || pip || ensurePip.loading) return;
  ensurePip.loading=true;
  const assets = await loadIntroAssets();
  pip = new PilotPiP($('pip'), { mirror: renderer.domElement, human: assets.human, width: 300, height: 190 });
  ensurePip.loading=false;
  $('pip').hidden = !$('optPip').checked || params.has('nopip');
}
try{$('optPip').checked=localStorage.getItem('rov.operatorVisible')==='true';}catch{$('optPip').checked=false;}
function togglePip(){try{localStorage.setItem('rov.operatorVisible',String($('optPip').checked));}catch{}ensurePip();}
$('optPip').addEventListener('change', togglePip);
$('closePip').onclick=()=>{$('optPip').checked=false;togglePip();};
ensurePip();
/* ═════════════════════════ replay (recorded demo flights, no server) ═════════════════════════ */
let rep = null;
let debrief = null;
function prepClip(c) {
  let r = null;                                 // the recorder stores the route only when it changes
  for (const f of c.frames) { if ('route' in f.nav) r = f.nav.route; else f.nav.route = r; }
  c.dur = Math.max(.01,c.frames.at(-1).t-c.frames[0].t);
}
function setReplayTime(t, {pause} = {}) {
  if (!rep) return;
  if (introActive()) intro.skip();
  rep.t = Math.max(0, Math.min(clipNow().dur, t));
  rep.endHold = 0;
  if (pause) {
    rep.playing = false;
    $('rpPlay').textContent = '▶';
  }
}
async function startReplay(url) {
  setConn('wait', '載入回放…'); connectionNotice.connected();
  let data;
  try { data = url.startsWith('local:')?await readReplay(url.slice(6)):await (await fetch(url)).json(); } catch (e) { setConn('stop', '回放檔載入失敗');cockpit.message({message:e.message}); return; }
  rep = { data, ci: 0, t: 0, playing: true, speed: 1, endHold: 0 };
  document.body.classList.add('replaying');
  data.clips.forEach(prepClip);
  $('replayBar').hidden = false;
  $('rpClips').innerHTML = data.clips.map((c, i) => `<button data-i="${i}">${i + 1}. ${esc(c.title)}</button>`).join('');
  $('rpClips').onclick = (e) => { const i = e.target.dataset?.i; if (i != null) loadClip(+i); };
  $('rpPlay').onclick = () => { rep.playing = !rep.playing; $('rpPlay').textContent = rep.playing ? '❚❚' : '▶'; };
  $('rpSeek').oninput = (e) => { setReplayTime(+e.target.value / 1000 * clipNow().dur); };
  $('rpSpeed').onchange = (e) => { rep.speed = +e.target.value; };
  // the bar fades out while watching and comes back on any mouse / touch / key activity
  let idleTimer = 0;
  const wake = () => {
    $('replayBar').classList.remove('idle'); clearTimeout(idleTimer);
    idleTimer = setTimeout(() => { if (rep.playing) $('replayBar').classList.add('idle'); }, 2500);
  };
  for (const ev of ['pointermove', 'pointerdown', 'touchstart']) vp.addEventListener(ev, wake, { passive: true });
  addEventListener('keydown', wake);
  $('rpPlay').addEventListener('click', wake);
  wake();
  debrief = installDebrief({
    replayBar: $('replayBar'), getReplay: () => rep, setReplayTime, setCam, feed: feedReplay,
    source: url, recording: data,
    capture() { renderer.render(scene, camera); return renderer.domElement; },
  });
  loadClip(0);
}
const clipNow = () => rep.data.clips[rep.ci];
function loadClip(i) {
  rep.ci = i; rep.t = 0; rep.endHold = 0; lastT = -1; target.init = false; tetherDisp = [];
  [...$('rpClips').children].forEach((b, j) => b.classList.toggle('on', j === i));
  const c = clipNow();
  onWorld({ ...c.world, type: 'world' });
  debrief?.timeline.renderEvents();
  feedReplay();
}
function feedReplay() {
  const c = clipNow(), fr = c.frames, time = fr[0].t + (debrief ? debrief.displayTime() : rep.t);
  const s = { ...sampleSnapshots(fr, time), type: 'state', paused: false };
  onState(s);
  debrief?.afterFeed(s);
  const line = [...c.script].reverse().find((l) => l.t <= s.t + 0.05);
  const show = !!line && s.t - line.t < 7 && !introActive();
  $('rpSub').hidden = !show; if (show) $('rpSub').textContent = line.text;
  $('rpSeek').value = Math.round(rep.t / c.dur * 1000);
  $('rpTime').textContent = `${fmtT(rep.t)} / ${fmtT(c.dur)}`;
}
function replayTick(dt) {
  if (rep && introActive()) { $('rpSub').hidden = true; return; }   // the clock waits for the deployment intro
  if (!rep) return;
  if (rep.playing) rep.t += dt * rep.speed;
  const c = clipNow();
  if (rep.t >= c.dur) {
    rep.t = c.dur; rep.endHold += dt;
    if (MOVIE && rep.ci === rep.data.clips.length - 1) { feedReplay(); return; }
    if (rep.endHold > (MOVIE ? 1.2 : 3)) { loadClip((rep.ci + 1) % rep.data.clips.length); return; }
  }
  feedReplay();
}
window.__replay = () => rep && { clip: rep.ci, t: rep.t, dur: clipNow().dur };

/* ═════════════════════════ movie mode: ?replay=…&movie (add &capture for frame-by-frame) ═════════════════════════ */
const MOVIE = params.has('movie'), CAPTURE = params.has('capture');
const MOVIE_SPEED = [1, 1.6, 1.8, 2.6];
// per clip: [start s, camera] in clip time
const MOVIE_SHOTS = [
  [[0, 'chase'], [9.5, 'cine'], [17, 'chase']],
  [[0, 'cine']],
  [[0, 'cine'], [14, 'chase'], [40, 'cine']],
  [[0, 'cine'], [16, 'chase'], [78, 'cine'], [100, 'chase']],
];
const movie = { t: 0, phase: 'open', introDone: false, endT: 0, clipShown: -1 };
if (MOVIE) {
  document.body.classList.add('movie');
  $('optLabels').checked = true;
  const card = document.createElement('div'); card.className = 'card'; card.id = 'card';
  card.innerHTML = '<i>ROV SIMULATOR · OPERATOR TRAINING</i><b>ROV 操作員訓練模擬器</b><span>下水 → 導管架碰撞 → 纜線纏繞脫困 → 強流懸停 → 沉船調查。畫面中的飛行全部由模擬器即時計算。</span>';
  vp.appendChild(card);
  const low = document.createElement('div'); low.className = 'lower'; low.id = 'lower'; low.hidden = true;
  low.innerHTML = '<i></i><b></b>'; vp.appendChild(low);
}
function movieTick(dt) {
  if (!MOVIE || !rep) return;
  movie.t += dt;
  const card = $('card'), low = $('lower');
  if (movie.phase === 'open') {
    if (movie.t > 3.8) card.hidden = true;
    if (!introActive() && movie.t > 4) { movie.phase = 'clips'; movie.introDone = true; }
  }
  if (movie.phase === 'clips') {
    const shots = MOVIE_SHOTS[rep.ci] || [[0, 'chase']];
    let want = shots[0][1];
    for (const [t0, m] of shots) if (rep.t >= t0) want = m;
    if (camMode !== want) { if (want === 'cine') cine.a = Math.atan2(camera.position.z - rovG.position.z, camera.position.x - rovG.position.x); setCam(want); }
    rep.speed = MOVIE_SPEED[rep.ci] || 1;
    const c = clipNow();
    low.hidden = !(rep.t < 3.5);
    if (movie.clipShown !== rep.ci) { movie.clipShown = rep.ci; low.querySelector('i').textContent = `${rep.ci + 1} / ${rep.data.clips.length}`; low.querySelector('b').textContent = c.title; }
    if (rep.t >= c.dur && rep.ci === rep.data.clips.length - 1) {
      movie.phase = 'end'; movie.endT = movie.t; low.hidden = true;
    card.innerHTML = '<i>ROV SIMULATOR · OPERATOR TRAINING</i><b>接上手把，自己飛一次</b><span>協作探索與巡檢 · 碰撞、纜線、洋流、燈光即時模擬</span>';
      card.hidden = false;
    }
  }
  if (movie.phase === 'end' && movie.t - movie.endT > 5) window.__movieDone = true;
}
window.__movieDone = false;

new ResizeObserver(resize).observe(vp);
const _wc = new THREE.Color();
const audio = installAudio({
  getWorld: () => W, getCamera: () => camera, getMode: () => camMode, isPaused: () => !!rep && !rep.playing,
});
installAudioSettings(audio, document.querySelector('.rack.left'));
const music = installMusic({engine: audio});
installVoice({engine: audio, music});
const prologue = installPrologue({input, send, camera, scene, rovG, setCam, music});
const coldOpen = installColdOpen({input, setCam, camera, rovG, hidden: [objG, guide, curArrow, wrapG, contactMesh],
  music, readOnly: !!REPLAY, plain: () => structureSet?.highlight(new Set())});
const flightFeedback = installFlightFeedback({canvas: renderer.domElement, radio: procedurePanel.radio,
  onboard: () => camMode === 'onboard'});
photoFeedback = installPhotoFeedback({viewport: vp, audio, haptics: input.haptics});
const shaderWarmup = createShaderWarmup({renderer, scene, camera});
let last = performance.now(), fpsN = 0, fpsT = 0, fps = 0;
function frame(now) {
  linkInbox.flush();
  if (!CAPTURE && skipFrame(now)) {
    requestAnimationFrame(frame);
    return;
  }
  const frameSeconds=Math.max(0,(now-last)/1000);
  const dt = Math.min(.25, frameSeconds); last = now;
  updateRenderQuality(renderer,frameSeconds,{suspended:CAPTURE||!!cockpit.recording||introActive()});
  // pose (smoothed toward latest state)
  replayTick(dt);
  updateFlightHUD(renderState.display(S), W, dt, input.hudState());
  updateTetherOperations(S);
  movieTick(dt);
  const inIntro = introActive();
  if (intro) intro.update(dt);
  if (inIntro) { /* the intro poses the ROV and the camera */ }
  else if (target.init) {
    renderState.update(S, rep);
  }
  if (!inIntro) renderTether(dt); else { cable.hide(); tetherLine.visible = false; }
  // rotors
  if (S && rotorOf.length) {
    rotorOf.forEach((r, j) => {
      if (!r) return; r.ang += rotorRate(S, j, dt, rotorSpin) * dt;
      r.o.quaternion.copy(r.base).multiply(_q.setFromAxisAngle(r.axis, r.ang));
    });
  }
  if (!inIntro) updateCamera(dt);
  // water colour + fog from camera depth, visibility and silt
  const camDepth = clamp(-camera.position.y, 0, 60);
  installUnderwaterPipeline(renderer, { surface });
  applyUnderwaterLighting(scene, S, renderer);
  shaderWarmup.update(now);
  fleet.update(dt);
  _wc.copy(waterSurf).lerp(waterDeep, 1 - Math.exp(-camDepth / 13));
  siltFx.update({camera, state: S, world: W, waterColour: _wc, real: $('optFog').checked && camMode !== 'top',
    displayFar: Math.max(90, cameraRig.topH * 4), lampLevel: [0, .55, 1][S?.rc?.right_switch || 0] || 0, rov: rovG});
  daylightRig.update({ camera, world: W, dt, view: camMode, surface, renderer });
  spoolStation.update(dt, !!intro?.onScene, camera);           // the intro brings its own boat while it plays
  objG.visible = !inIntro; if (inIntro) { curArrow.visible = false; particles.visible = false; }
  if (!inIntro) updateParticles(dt, rovG.position);
  updatePenNet(structureSet, flowField, now / 1000);
  if (env) env.update(dt, camera, S?.current_here ? P(S.current_here) : null, renderState.state || S, flowField);
  topMark.visible = camMode === 'top';
  if (topMark.visible) {
    _f.set(0, 0, 1).applyQuaternion(rovG.quaternion);
    topMark.position.copy(rovG.position).add(new THREE.Vector3(0, .6, 0));
    topMark.rotation.set(-Math.PI / 2, 0, Math.atan2(-_f.x, -_f.z), 'XYZ');
    topMark.scale.setScalar(cameraRig.topH / 22);
  }
  curArrow.position.copy(rovG.position).add(new THREE.Vector3(0, .55, 0));
  // objectives + guide line
  const cur = updateObjectives(now / 1000);
  const gp = guide.geometry.attributes.position.array;
  if (cur) {
    const a = rovG.position, b = cur.m.g.position;
    gp.set([a.x, a.y, a.z, b.x, b.y, b.z]); guide.geometry.attributes.position.needsUpdate = true; guide.computeLineDistances();
    guide.visible = camMode !== 'onboard';
  } else guide.visible = false;
  const displayed = renderState.display(S);
  audio.update(displayed);
  music.update(displayed);
  if (displayed) flightFeedback.update(displayed, W,
    !!(rep || introActive() || pauseMenuOpen() || collectionOpen || resultsOpen()));
  coldOpen.frame(dt);
  prologue.frame();
  cameraLook.update();
  if (!window.__skipRender) renderer.render(scene, camera);      // the movie renderer fast-forwards without drawing
  videoLinkOverlay.update(renderState.linkEffect, camMode, renderer.domElement);
  vision.update(now);
  if (pip && !$('pip').hidden) pip.update(dt, S?.rc || rc);
  // labels
  const r = vpRect;
  const L = [];
  if (W?.spool) L.push({ id: 'spool', text: '纜盤 / 投放點', pos: spoolStation.labelPosition(W), cls: 'spool' });
  if (cur) L.push({ id: 'obj', text: `${cur.o.label} · ${cur.m.g.position.distanceTo(rovG.position).toFixed(1)} m`, pos: cur.m.g.position, cls: 'obj' });
  for (const w of wrapLabels) L.push(w);
  for (const n of S?.tether?.snagged_on || []) { const e = obstacleMeshes.get(n); if (e && !wrapLabels.some((w) => w.id === 'wrap:' + n)) { const p = e.mesh.position.clone(); if (e.ob.type === 'cylinder') p.y = rovG.position.y + 1; L.push({ id: 'snag:' + n, text: `卡纜：${n}`, pos: p, cls: 'bad' }); } }
  drawLabels(L, r.width, r.height);
  if (uiDirty && now - uiLast > 110) { uiDirty = false; uiLast = now; updateUI(); }
  fpsN++; fpsT += frameSeconds; if (fpsT > .5) { fps = Math.round(fpsN / fpsT); fpsN = 0; fpsT = 0; const quality=renderQualityInfo(renderer);setTxt('meta', `${fps} FPS${quality?.mode==='auto'?` · 自動 ${quality.scale}%`:''}${S ? ` · t=${S.t.toFixed(1)} s` : ''}`);$('meta').title=quality?.hardwareRenderer||''; }
  if (!CAPTURE) requestAnimationFrame(frame);
}

if (matchMedia('(max-width: 720px)').matches) $('optLabels').checked = false;
setCam(camMode); resize(); drawProfile(); loadModel(); connect();
if (CAPTURE) {
  let vnow = performance.now();
  last = vnow;
  window.__advance = (dt) => { vnow += dt * 1000; frame(vnow); };
} else requestAnimationFrame(frame);
window.__viewer = { cameraLook, THREE, scene, camera, rovG, worldG, siltFx, get W() { return W; }, get S() { return S; }, rotors, get rotorOf() { return rotorOf; }, setCam, rc, touch, toggleLock, takePhoto:options=>photoClient.takePhoto(options), send, flushLink: () => linkInbox.flush() };
Object.defineProperties(window.__viewer, { debrief: { get: () => debrief }, rep: { get: () => rep } });
window.__viewer.performance=()=>({fps,...renderQualityInfo(renderer)});
window.__viewer.renderer = renderer;
