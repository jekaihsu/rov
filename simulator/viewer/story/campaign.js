// Radio subtitles, shared chapter selection and local campaign progress preferences.
import {glyph, deviceFamily} from '../input/glyphs.js';
import {listCollection, saveResult} from '../collection_store.js';
const STRINGS = {
  menuOption: '潮間帶工作隊 · 劇情與新手教學',
  menuBrief: '從水池練習開始，解鎖港灣與船殼巡檢。章節與課程可在任務面板重玩。',
  sticker: '裝上首次下潛貼紙', vehicle: '部署解鎖的作業載具',
  resume: '從存檔點繼續', saveFailed: '進度儲存失敗，請匯出學員成績備份。',
  title: '潮間帶工作隊', chapters: '章節 / 訓練課程', next: '繼續', skip: '跳過教學',
  history: '無線電紀錄', pending: '籌備中', locked: '先完成前一任務', course: '公司課程（略過故事）',
  export: '匯出學員成績', complete: '任務完成。回到章節選單，準備下一次下潛。',
  retry: '先停一下，別急。我們照剛才那一步再試一次。', replay: '重玩序章',
  channels: {
  left_ud: ['W / S', '左桿上下'], left_lr: ['D / A', '左桿左右'],
  right_ud: ['↑ / ↓', '右桿上下'], right_lr: ['→ / ←', '右桿左右'],
  left_wave: ['E / Q', '左滾輪'], right_wave: ['C / Z', '右滾輪'],
},
};
export const CAMPAIGN_MENU_STRINGS = {title: STRINGS.menuOption, brief: STRINGS.menuBrief};
const KEY = 'rov.campaign.v1';
const CHANNELS = STRINGS.channels;
const MODES = {
  ROV_USA: ['right_ud', 'right_wave', 'left_wave'], ROV_JPN: ['left_ud', 'right_wave', 'left_wave'],
  ROV_CHN: ['left_ud', 'right_wave', 'left_wave'], UAV_USA: ['right_ud', 'right_lr', 'left_ud'],
  UAV_JPN: ['left_ud', 'right_lr', 'right_ud'], UAV_CHN: ['left_ud', 'left_lr', 'right_ud'],
};

export function installCampaign({send, readOnly = false}) {
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
  next.innerHTML = glyph(0, family, 'Enter') + STRINGS.next;
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
  const style = document.createElement('style');
  style.textContent = `
    .story-radio{position:fixed;left:30%;bottom:18%;width:40%;box-sizing:border-box;padding:16px 24px;
      background:rgba(8,18,26,.72);backdrop-filter:blur(14px);border-left:2px solid #4fd1e0;
      color:#e8f1f5;z-index:25;pointer-events:none;transition:opacity .2s ease-out}
    .story-avatar{float:left;width:24px;height:24px;margin-right:8px;fill:none;stroke:#4fd1e0}
    .story-radio[hidden]{display:none}.story-radio strong{color:#4fd1e0;font-size:12px;letter-spacing:.1em}
    .story-radio p{font-size:17px;line-height:1.6;margin:8px 0}.story-radio small{color:#8fa6b2}
    .story-radio button{pointer-events:auto;float:right}.story-menu button{display:block;margin:8px 0;width:100%}
    .story-menu button:focus-visible{outline:2px solid #4fd1e0}.story-menu{padding:8px 0}
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
    next.innerHTML = glyph(0, family, 'Enter') + STRINGS.next;
    const action = {unlock: [3, 'Space'], depth: [2, 'H'], photo: [0, 'P']}[current?.node?.id];
    cap.innerHTML = action ? glyph(action[0], family, action[1]) : '';
  }
  document.addEventListener('rov-input-device', function storyDevice(event) {
    family = deviceFamily(event.detail === 'touch' ? '' : event.detail);
    refreshGlyphs();
  });
  function command(action, extra = {}) {
    send({type: 'operation', action, ...extra});
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
  addEventListener('keydown', function onStoryKey(event) {
    if (event.code === 'Enter' && !event.repeat && !root.hidden && event.target === document.body) advance();
  });
  report.onclick = function exportResults() {
    const blob = new Blob([JSON.stringify(current?.results || [], null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'training-results.json';
    link.click();
    URL.revokeObjectURL(url);
  };
  let confirmHeld = false;
  setInterval(function readStoryController() {
    const held = Array.from(navigator.getGamepads?.() || []).some(pad => pad?.buttons[0]?.pressed);
    if (held && !confirmHeld && !root.hidden && current?.node?.type === 'dialogue') advance();
    confirmHeld = held;
  }, 50);
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
    if (host && !restoreSent && collectionReady) {
      restoreSent = true;
      let save = null;
      try { save = JSON.parse(localStorage.getItem(KEY)); } catch {}
      save = persisted || save;
      if (save) command('campaign_restore', {save});
      // First run enters onboarding; a returning player chooses a chapter in the drawer.
      const requested = new URLSearchParams(location.search).get('mission') === 'campaign';
      if (campaign.status === 'idle' && requested) {
        const completed = save?.completed || [];
        const chapter = campaign.chapters.find(entry => !entry.placeholder
          && !completed.includes(entry.id) && (!entry.requires || completed.includes(entry.requires)));
        if (chapter) command('campaign_start', {chapter: chapter.id, resume: save?.checkpoint?.chapter === chapter.id});
      }
    }
    const save = JSON.stringify({completed: campaign.completed, rewards: campaign.rewards,
      results: campaign.results, checkpoint: campaign.checkpoint});
    if (host && save !== savedSignature && campaign.status !== 'idle') {
      savedSignature = save;
      try { localStorage.setItem(KEY, save); } catch {}
      saveResult({kind: 'campaign-progress', save: JSON.parse(save)}).catch(function saveFailed() {
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
    root.hidden = !['active', 'completed'].includes(campaign.status);
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
      const axis = Number(node.condition.path.split('.').at(-1));
      const channel = MODES[state.operation_mode]?.[axis];
      const pad = Array.from(navigator.getGamepads?.() || []).some(Boolean);
      hint.textContent += ' · ' + (CHANNELS[channel]?.[pad ? 1 : 0] || '');
    }
    next.hidden = node?.type !== 'dialogue';
    log.replaceChildren(...campaign.dialogue.map(entry => {
      const paragraph = document.createElement('p');
      paragraph.textContent = `${entry.speaker}：${entry.text}`;
      return paragraph;
    }));
  }
  return {update};
}
