// Text for the HUD mode pill: the assist level and profile the pilot asked for, and a separate note
// when the simulator is not (yet) flying that request. Pure logic: no DOM and no imports.
import { localize } from '../i18n/index.js';

const STRINGS = localize('hud.assist_pill', {
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
  // Why the DVL has no bottom lock (state.sensors.dvl.reason, PROTOCOL.md), in the player's words:
  // [short status, explanation, what to do].
  dvl: {
    too_high: ['離底太高', 'DVL 收不到海床回波（離底 {alt} m）', '下潛靠近海床後會自動恢復。'],
    range: ['離底太高', 'DVL 回波太弱（離底 {alt} m）', '下潛靠近海床後會自動恢復。'],
    window: ['超出 DVL 範圍', '離底高度超出 DVL 可用範圍', '回到離底 0.5 m 以上、可見海床的高度。'],
    too_low: ['離底太近', '太貼近海床，DVL 量不到', '往上一點，離底 0.5 m 以上會自動恢復。'],
    net: ['網面回波', 'DVL 波束打在箱網上', '移到能量到海床的位置。'],
    tilt: ['傾角過大', '機體傾角超出 DVL 工作範圍', '將機體調平。'],
    slope: ['海床太陡', '下方坡度太陡，DVL 失去底鎖', '移到較平坦的海床上方。'],
    vegetation: ['植被遮擋', '海草或海藻擋住 DVL 波束', '升高一點或移到沙地上方。'],
    silt: ['泥沙混濁', '揚起的泥沙擋住 DVL 波束', '暫停推進等泥沙沉降，或離開混濁區。'],
    aeration: ['近水面氣泡', '靠近水面時推進器捲入氣泡，干擾 DVL', '下潛離開水面附近即可恢復。'],
    mud: ['軟泥回波弱', '軟泥海床回波太弱', '升高一點，或移到較硬的海床上方。'],
    pool: ['池壁回波干擾', '水池池壁的回波干擾 DVL', '移到水池中央。'],
    fault: ['DVL 故障', 'DVL 回報故障', '改用手動飛行，結束後檢修。'],
  },
  dvlLost: 'DVL 失去底鎖',
});

// The DVL reason as {status, help}, or null when the state says nothing about it.
export function dvlReason(state) {
  const dvl = state?.sensors?.dvl;
  if (!dvl || dvl.status !== 'lost') return null;
  const words = STRINGS.dvl[dvl.reason];
  if (!words) return {status: STRINGS.dvlLost, help: STRINGS.inactiveHelp};
  const altitude = dvl.altitude ?? state.sensors.altitude;
  const shown = altitude == null ? '—' : Number(altitude).toFixed(1);
  return {status: words[0], help: `${words[1].replace('{alt}', shown)}。${words[2]}`};
}

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
    const reason = dvlReason(state);
    if (reason) return result(text, `${STRINGS.inactive} · ${reason.status}`, 'warn', reason.help);
    return result(text, STRINGS.inactive, 'warn', STRINGS.inactiveHelp);
  }
  if (reported.limited) return result(text, STRINGS.limited, 'warn', STRINGS.limitedHelp);
  if (reported.holding) return result(text, STRINGS.holding, 'ok');
  return result(text);
}
