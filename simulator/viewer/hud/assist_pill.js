// Text for the HUD mode pill: the assist level and profile the pilot asked for, and a separate note
// when the simulator is not (yet) flying that request. Pure logic: no DOM and no imports.
const STRINGS = {
  levels: ['手動', '速度輔助', '定點輔助'],
  profiles: {cine: '電影', normal: '標準', sport: '運動'},
  unsupported: '伺服器不支援輔助',
  remote: 'SDK 控制中停用',
  locked: '解鎖後生效',
  autopilot: '自動航線中停用',
  inactive: '未生效',
  inactiveHelp: '模擬器目前以手動飛行。定點與速度輔助需要 DVL 對底有效；離底過高或過近時會暫停。',
  limited: '推力飽和',
  limitedHelp: '推力不足以維持指令，例如洋流過強。',
  holding: '定點中',
  manualOverride: '模擬器回報輔助仍在作用',
};

function result(text, status = '', tone = 'ok', help = '') {
  return {text, status, tone, help};
}

// state: latest simulator state. requested: {level, profile} from the fidelity profile.
// tone: `ok` (flying as requested), `pending` (will apply by itself), `warn` (pilot should know).
export function assistPill(state, requested) {
  const level = STRINGS.levels[requested.level] ? requested.level : 0;
  const profile = STRINGS.profiles[requested.profile] || requested.profile;
  const reported = state?.assist;
  if (level === 0) {
    if (reported?.level > 0 && !state.locked) return result(STRINGS.levels[0], STRINGS.manualOverride, 'pending');
    return result(STRINGS.levels[0]);
  }
  const text = `${STRINGS.levels[level]} · ${profile}`;
  if (!reported || typeof reported !== 'object') return result(text, STRINGS.unsupported, 'warn');
  if (state.remote_control) return result(text, STRINGS.remote, 'warn');
  if (state.locked) return result(text, STRINGS.locked, 'pending');
  if (reported.level !== level || reported.profile !== requested.profile) {
    const autopilot = state.nav?.mode && state.nav.mode !== 'IDLE';
    if (autopilot) return result(text, STRINGS.autopilot, 'pending');
    return result(text, STRINGS.inactive, 'warn', STRINGS.inactiveHelp);
  }
  if (reported.limited) return result(text, STRINGS.limited, 'warn', STRINGS.limitedHelp);
  if (reported.holding) return result(text, STRINGS.holding, 'ok');
  return result(text);
}
