// Chooses the flight HUD presentation: the line instrument or the camera on-screen display (OSD).
// Pure logic with no DOM and no imports, so unit tests can load it directly.
export const HUD_STYLES = ['line', 'osd'];

// setting: the `hudStyle` fidelity value (auto | line | osd). preset: the fidelity preset name.
// view: the active camera mode. Auto shows the OSD only for the real preset seen from the onboard camera,
// which is how a real pilot sees the vehicle; every other combination gets the line instrument.
export function resolveHudStyle({setting = 'auto', preset = 'real', view = 'onboard'} = {}) {
  if (HUD_STYLES.includes(setting)) return setting;
  return preset === 'real' && view === 'onboard' ? 'osd' : 'line';
}
