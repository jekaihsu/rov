// Camera preferences as fidelity items so the camera rig, which only receives the fidelity store, can follow
// them: the field of view of the external (chase, orbit, top, cinematic) cameras, and motion comfort, which
// turns off the chase camera's speed effects. The onboard camera keeps the real lens, so neither item changes
// what the real vehicle would show; both are presetNeutral preferences. Motion comfort also marks <html> so the
// menus and overlays drop their decorative animations.
import { getFidelity, registerFidelityItem } from '../fidelity.js';

export const EXTERNAL_FOV_ITEM = 'externalFov';
export const MOTION_COMFORT_ITEM = 'motionComfort';

registerFidelityItem({
  id: EXTERNAL_FOV_ITEM, descriptionKey: 'externalFovHelp', type: 'range', min: 40, max: 90, step: 1,
  unitKey: 'unitDegree', defaults: { real: 55, assisted: 55 }, presetNeutral: true,
}, {
  externalFov: '外部視角視野（FOV）',
  externalFovHelp: '追蹤、環繞、俯視視角的視野角度；機載鏡頭維持真實鏡頭，不受影響。',
  unitDegree: '°',
});
registerFidelityItem({
  id: MOTION_COMFORT_ITEM, descriptionKey: 'motionComfortHelp', type: 'toggle',
  defaults: { real: false, assisted: false }, presetNeutral: true,
}, {
  motionComfort: '動態舒適',
  motionComfortHelp: '關閉追蹤視角隨速度拉遠與視野放大，並減少介面動畫，降低暈眩。',
});

function markComfort() {
  const root = globalThis.document?.documentElement;
  if (root) root.classList.toggle('motion-comfort', !!getFidelity().get(MOTION_COMFORT_ITEM));
}
getFidelity().subscribe(markComfort);
markComfort();
