// Radio subtitles, shared chapter selection and local campaign progress preferences.
import {actionGlyph, deviceFamily} from '../input/glyphs.js';
import {BINDINGS, axisChannel, pilotAxisKeys} from '../input/bindings.js';
import {listCollection, saveResult} from '../collection_store.js';
import {vehicleName} from '../fleet_names.js';
import {installVoice} from '../audio/voice.js';
import {localize} from '../i18n/index.js';
import {campaignStore} from '../saves/registry.js';
const STRINGS = localize('story.campaign', {
  menuOption: 'YX 海事服務 · 劇情與新手教學',
  menuBrief: '從水池練習開始，解鎖港灣與船殼巡檢。章節與課程可在任務面板重玩。',
  sticker: '裝上首次下潛貼紙', vehicle: `部署解鎖的作業載具 ${vehicleName('falcon')}`,
  resume: '從存檔點繼續', saveFailed: '進度儲存失敗，請匯出學員成績備份。',
  title: 'YX 海事服務', chapters: '章節 / 訓練課程', next: '繼續', skip: '跳過教學',
  history: '無線電紀錄', pending: '籌備中', locked: '先完成前一任務', course: '公司課程（略過故事）',
  export: '匯出學員成績', complete: '任務完成。回到章節選單，準備下一次下潛。',
  retry: '先停一下，別急。我們照剛才那一步再試一次。', replay: '重玩序章',
  // Pad names of the stick channels; keyboard keys come from the active key rows (input/keyboard_layout.js).
  channels: {
    left_ud: '左桿上下', left_lr: '左桿左右', right_ud: '右桿上下', right_lr: '右桿左右',
    left_wave: '左滾輪', right_wave: '右滾輪',
  },
});
export const CAMPAIGN_MENU_STRINGS = {title: STRINGS.menuOption, brief: STRINGS.menuBrief};

const KEY = 'rov.campaign.v1';
const CHANNELS = STRINGS.channels;
// The move_ steps of the prologue test these pilot axes, in the order of their condition paths.
const MOVE_AXES = ['surge', 'sway', 'heave'];
// Story steps that wait for a bound input action.
const STEP_ACTIONS = {unlock: 'lock', depth: 'depth', photo: 'photo'};

export function installCampaign({send, readOnly = false, voice = null} = {}) {
  const radioVoice = voice || installVoice();
  const root = document.createElement('section');
  root.className = 'story-radio';
  root.hidden = true;
  const avatar = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  avatar.setAttribute('viewBox', '0 0 24 24');
  avatar.setAttribute('aria-hidden', 'true');
  avatar.classList.add('story-avatar');
  avatar.innerHTML = '<circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>';
  const speaker = document.createElement('strong');
  const text = document.createElement('p');
  const hint = document.createElement('small');
  const next = document.createElement('button');
  let family = 'keyboard';
  let boundInput = null;
  function keyRows() {
    return boundInput?.keyRows?.() || BINDINGS;
  }
  next.innerHTML = actionGlyph('dialogueAccept', keyRows(), family) + STRINGS.next;
  const cap = document.createElement('span');
  root.append(avatar, speaker, text, cap, hint, next);
  document.body.append(root);
  const menu = document.createElement('details');
  menu.className = 'story-menu';
  const summary = document.createElement('summary');
  summary.textContent = STRINGS.chapters;
  const list = document.createElement('div');
  const course = document.createElement('input');
  course.type = 'checkbox';
  const label = document.createElement('label');
  label.append(course, STRINGS.course);
  const sticker = document.createElement('button');
  sticker.textContent = STRINGS.sticker;
  sticker.onclick = () => command('appearance', {sticker: 'dive'});
  const vehicle = document.createElement('button');
  vehicle.textContent = STRINGS.vehicle;
  vehicle.onclick = () => send({type: 'model', model_id: 'falcon'});
  const resume = document.createElement('button');
  resume.textContent = STRINGS.resume;
  resume.onclick = () => command('campaign_start', {chapter: current?.checkpoint?.chapter, resume: true});
  const history = document.createElement('details');
  const historyTitle = document.createElement('summary');
  historyTitle.textContent = STRINGS.history;
  const log = document.createElement('div');
  history.append(historyTitle, log);
  const skip = document.createElement('button');
  skip.textContent = STRINGS.skip;
  const report = document.createElement('button');
  report.textContent = STRINGS.export;
  menu.append(summary, label, list, resume, sticker, vehicle, skip, report, history);
  document.querySelector('.mission-tools')?.append(menu);
  // The radio sits below the heading tape, right of the depth scale and above the minimap, so it never covers an
  // instrument; its layer comes from the stacking scale in hud/tokens.css. The key cap keeps its own width.
  const style = document.createElement('style');
  style.textContent = `
    .story-radio{position:fixed;left:max(15%,220px);top:max(15%,calc(3% + 108px));width:31%;max-width:45%;
      max-height:44%;
      overflow:auto;box-sizing:border-box;padding:16px 24px;
      background:rgba(8,18,26,.72);backdrop-filter:blur(14px);border-left:2px solid #4fd1e0;
      color:#e8f1f5;z-index:var(--z-story);pointer-events:none;transition:opacity .2s ease-out}
    .story-avatar{float:left;width:24px;height:24px;margin-right:8px;fill:none;stroke:#4fd1e0}
    .story-radio[hidden]{display:none}.story-radio strong{color:#4fd1e0;font-size:12px;letter-spacing:.1em}
    .story-radio p{font-size:17px;line-height:1.6;margin:8px 0}.story-radio small{color:#8fa6b2}
    .story-radio>span:not(:empty){display:inline-block;margin-right:10px;vertical-align:middle}
    .story-radio button svg{margin-right:6px;vertical-align:middle}
    .story-radio button{pointer-events:auto;float:right}.story-menu button{display:block;margin:8px 0;width:100%}
    .story-menu button:focus-visible{outline:2px solid #4fd1e0}.story-menu{padding:8px 0}
    @media(max-width:720px){
      .story-radio{left:4%;top:60px;width:58%;max-width:58%;max-height:250px;padding:8px 12px;pointer-events:auto}
      .story-radio p{font-size:14px;margin:4px 0}
    }
    @media(prefers-reduced-motion:reduce){.story-radio{transition:none}}
  `;
  document.head.append(style);
  let collectionReady = false;
  let persisted = null;
  listCollection().then(function loadCampaign(index) {
    persisted = index.results.filter(r => r.kind === 'campaign-progress').at(-1)?.save || null;
  }).catch(function ignoreUnavailableCollection() {}).finally(function readyCollection() {
    collectionReady = true;
  });
  let current = null;
  let signature = '';
  let chapterSignature = '';
  let revealed = 0;
  let line = '';
  let started = 0;
  let restoreSent = false;
  let savedSignature = '';
  function refreshGlyphs() {
    next.innerHTML = actionGlyph('dialogueAccept', keyRows(), family) + STRINGS.next;
    const step = STEP_ACTIONS[current?.node?.id];
    cap.innerHTML = step ? actionGlyph(step, keyRows(), family) : '';
  }
  document.addEventListener('rov-key-rows', refreshGlyphs);
  document.addEventListener('rov-input-device', function storyDevice(event) {
    family = deviceFamily(event.detail === 'touch' ? '' : event.detail);
    refreshGlyphs();
  });
  function command(action, extra = {}) {
    send({type: 'operation', action, ...(action === 'campaign_start' ? {beats: true} : {}), ...extra});
  }
  function advance() {
    if (revealed < line.length) {
      revealed = line.length;
      text.textContent = line;
    } else {
      command('campaign_advance');
    }
  }
  next.onclick = advance;
  skip.onclick = () => command('campaign_skip');
  let isHost = false;
  // Dialogue is an input context: while it waits for confirmation the input layer gives the confirm
  // button to these actions and withholds it from the flight action on the same button.
  function awaitingConfirm() {
    return !readOnly && isHost && !root.hidden && current?.node?.type === 'dialogue';
  }
  function bindInput(input) {
    boundInput = input;
    input.registerActions({
      dialogueAccept: {
        enabled: awaitingConfirm,
        run: advance,
      },
      dialogueSkip: {
        enabled: function skipAllowed() {
          return awaitingConfirm() && !skip.disabled;
        },
        run: function skipTutorial() {
          command('campaign_skip');
        },
      },
    });
  }
  report.onclick = function exportResults() {
    const blob = new Blob([JSON.stringify(current?.results || [], null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'training-results.json';
    link.click();
    URL.revokeObjectURL(url);
  };
  setInterval(function revealText() {
    if (revealed < line.length) {
      revealed += matchMedia('(prefers-reduced-motion: reduce)').matches ? line.length : 2;
      text.textContent = line.slice(0, revealed);
    }
    if (current?.node?.type === 'wait' && performance.now() - started > 45000) hint.textContent = STRINGS.retry;
  }, 40);
  function update(state) {
    const campaign = state.campaign;
    if (!campaign || readOnly) return;
    current = campaign;
    const host = state.room?.players?.find(p => p.id === state.room.host_id)?.vehicle_id === state.vehicle_id;
    isHost = host;
    if (host && !restoreSent && collectionReady) {
      restoreSent = true;
      let save = null;
      const loaded = campaignStore.load();
      save = persisted || (loaded.reason === 'empty' || loaded.recovered ? null : loaded.value);
      if (save) {
        const { version: _version, ...payload } = save;
        command('campaign_restore', { save: payload });
        save = payload;
      }
      // First run enters onboarding; a returning player chooses a chapter in the drawer.
      const launch = new URLSearchParams(location.search);
      const requested = launch.get('mission') === 'campaign';
      if (campaign.status === 'idle' && requested) {
        const completed = save?.completed || [];
        // A chapter picked in the launch menu (story or incident drill) wins; the server still enforces locks.
        const picked = campaign.chapters.find(entry => entry.id === launch.get('chapter') && !entry.placeholder);
        // Incident drills are launched from the list only; a server without categories is all story.
        const chapter = picked || campaign.chapters.find(entry => !entry.placeholder
          && (entry.category || 'story') === 'story' && !completed.includes(entry.id) && (!entry.requires || completed.includes(entry.requires)));
        if (chapter) {
          const training = launch.get('training') === '1'
            || chapter.category === 'course'
            || String(chapter.id || '').startsWith('course_');
          command('campaign_start', {
            chapter: chapter.id,
            resume: save?.checkpoint?.chapter === chapter.id,
            course: training,
          });
        }
      }
    }
    const record = {
      completed: campaign.completed,
      rewards: campaign.rewards,
      results: campaign.results,
      checkpoint: campaign.checkpoint,
    };
    const save = JSON.stringify(record);
    if (host && save !== savedSignature && campaign.status !== 'idle') {
      savedSignature = save;
      campaignStore.save(record);
      saveResult({ kind: 'campaign-progress', save: record }).catch(function saveFailed() {
        hint.textContent = STRINGS.saveFailed;
      });
    }
    const chapters = JSON.stringify([campaign.chapters, campaign.completed, host]);
    if (chapters !== chapterSignature) {
      chapterSignature = chapters;
      list.replaceChildren(...campaign.chapters.map(chapter => {
        const button = document.createElement('button');
        const locked = chapter.requires && !campaign.completed.includes(chapter.requires);
        const suffix = chapter.placeholder ? STRINGS.pending : locked ? STRINGS.locked : '';
        button.textContent = chapter.title + (suffix ? ' · ' + suffix : '');
        button.disabled = !host || !!locked || !!chapter.placeholder;
        button.onclick = () => command('campaign_start', {chapter: chapter.id, course: course.checked});
        return button;
      }));
    }
    sticker.hidden = !campaign.unlocks?.stickers?.includes('dive');
    vehicle.hidden = !campaign.unlocks?.vehicles?.includes('falcon');
    vehicle.disabled = !host || campaign.status === 'active';
    resume.hidden = !campaign.checkpoint;
    resume.disabled = !host;
    skip.disabled = !host || campaign.chapter !== 'prologue';
    next.disabled = !host;
    // The prelude (the cold open) draws its own radio subtitles (story/cold_open.js).
    const prelude = campaign.chapters.find(entry => entry.id === campaign.chapter)?.category === 'prelude';
    root.hidden = campaign.directed || prelude || !['active', 'completed'].includes(campaign.status);
    const node = campaign.node;
    const key = JSON.stringify([campaign.chapter, campaign.index, campaign.status]);
    if (key === signature) return;
    signature = key;
    refreshGlyphs();
    started = performance.now();
    speaker.textContent = node?.speaker || STRINGS.title;
    line = node?.text || node?.hint || campaign.objective || STRINGS.complete;
    revealed = 0;
    text.textContent = '';
    hint.textContent = node?.type === 'wait' ? node.hint : '';
    if (node?.id?.startsWith('move_')) {
      const axis = MOVE_AXES[Number(node.condition.path.split('.').at(-1))];
      const mode = state.operation_mode || 'ROV_USA';
      const channel = axisChannel(axis, mode)?.channel;
      const keys = pilotAxisKeys(axis, keyRows(), mode).join(' / ');
      hint.textContent += ' · ' + ((family !== 'keyboard' ? CHANNELS[channel] : keys) || '');
    }
    next.hidden = node?.type !== 'dialogue';
    if (!prelude && node?.type === 'dialogue' && node.speaker && node.text) {
      Promise.resolve(radioVoice.playLine({
        speaker: node.speaker,
        text: node.text,
        language: 'zh-TW',
      })).catch(function ignoreVoiceErrors() {});
    } else {
      radioVoice.stop?.();
    }
    log.replaceChildren(...campaign.dialogue.map(entry => {
      const paragraph = document.createElement('p');
      paragraph.textContent = `${entry.speaker}：${entry.text}`;
      return paragraph;
    }));
  }
  return {update, bindInput};
}
