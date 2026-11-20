// Page-local measurements. Drained by the pilot between inputs, without disabling WebGL.
(() => {
  // The RC socket runs in a worker. Observe the same error packets it forwards to the input layer.
  window.Worker = class AuditWorker extends window.Worker {
    constructor(...args) {
      super(...args);
      this.addEventListener('message', function received(event) {
        const packet = event.data;
        if (packet?.event === 'message' && packet.data?.includes('invalid_command')) {
          window.auditWorkerPacket?.(packet.data);
        }
      });
    }
  };
  const frames = [];
  function beat() {
    const state = window.__viewer?.S;
    const cold = window.__coldOpen?.report.beats.at(-1)?.beat;
    if (cold) return cold;
    if (window.__results?.outcome) return 'results';
    const deck = document.querySelector('#procedurePanel:not([hidden])');
    if (deck) {
      return [deck.dataset.phase, deck.querySelector('.pp-title')?.textContent,
        deck.querySelector('.pp-primary')?.textContent].filter(Boolean).join('/');
    }
    const campaign = state?.campaign;
    if (campaign?.status === 'active') return campaign.node?.id;
    const item = window.__career?.snapshot()?.items.find(item => !item.done && item.required);
    return item?.id || 'loading';
  }
  const query = new URLSearchParams(location.search);
  const level = query.has('coldOpen') ? 'cold_open' : query.get('contract');
  let lastBeat;
  let entered = 0;
  let transitHint;
  let silenceShot = false;
  let stallShot = false;
  let previous;
  function tick(t) {
    const current = beat();
    if (previous !== undefined) frames.push([t / 1000, (t - previous) / 1000, lastBeat || current]);
    const changed = current !== lastBeat;
    if (changed) {
      lastBeat = current;
      entered = t;
      silenceShot = false;
      stallShot = false;
    }
    const quiet = !silenceShot && t - entered > 30000;
    const stalled = !stallShot && t - entered >= 120000;
    const hint = current === 'transit' ? document.querySelector('#coldOpenHint.visible')?.dataset.hint : null;
    const switched = hint && hint !== transitHint;
    transitHint = hint;
    if (level && current && (changed || quiet || stalled || switched)) {
      silenceShot ||= quiet;
      stallShot ||= stalled;
      const cues = visibleCues(window.__viewer?.S?.campaign?.node);
      const sample = {level, beat: current, wall: Date.now() / 1000, ...cues};
      console.debug('playtest-beat ' + JSON.stringify(sample));
    }
    previous = t;
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  let bindings;
  async function flightKeys(mode) {
    bindings ||= Promise.all([import('/input/bindings.js'), import('/input/keyboard_layout.js')]);
    const [api, layout] = await bindings;
    const rows = layout.currentKeyRows();
    const axes = {};
    for (const name of ['surge', 'sway', 'yaw', 'heave']) {
      const drive = api.axisChannel(name, mode);
      const own = rows.find(row => row.action === name && row.keys?.length);
      const codes = own?.keys || rows.find(row => row.action === drive?.channel)?.keys || [];
      axes[name] = {keys: !own && drive?.sign < 0 ? codes.slice().reverse() : codes};
    }
    return axes;
  }
  function texts(selector) {
    return [...document.querySelectorAll(selector)].filter(el => el.checkVisibility({opacityProperty: true,
      visibilityProperty: true})).map(el => el.innerText.trim()).filter(Boolean);
  }
  function visibleCues(node) {
    if (document.querySelector('.brand-card-overlay, #resultsScreen:not([hidden])')) {
      return {hints: [], radio: []};
    }
    const hints = texts('#coldOpenHint.visible .cold-open-hint-line, #onboardingHint.visible li, '
      + '.story-radio small, .story-radio button:enabled, #procedurePanel .pp-primary:enabled, '
      + '.career-card-actions .objective-accept:enabled');
    const radio = texts('.cold-open-radio.speaking, .career-radio');
    const deckRadio = window.__procedure?.()?.radio?.text;
    if (deckRadio && texts('#procedurePanel').length) radio.push(deckRadio);
    if (node?.type === 'dialogue' && texts('.story-radio strong').length) radio.push(node.speaker + ' ' + node.text);
    return {hints, radio};
  }
  window.auditSample = async function sample() {
    const state = window.__viewer?.S;
    const node = state?.campaign?.node;
    const {hints, radio} = visibleCues(node);
    const items = window.__career?.snapshot()?.items || [];
    const goal = items.find(item => !item.done && item.required);
    let primary = document.querySelector('#procedurePanel:not([hidden]) .pp-primary:enabled, '
      + '.career-card-actions .objective-accept');
    const arm = state?.operations?.arm;
    if (!primary && goal?.kind === 'lift' && arm?.available && !arm.held && arm.grip > .5) {
      const drawer = document.getElementById('engineering');
      const panel = document.getElementById('armPanel');
      if (drawer?.hidden) primary = document.getElementById('flightDrawer');
      else if (!panel?.open) primary = panel?.querySelector('summary');
      else primary = document.getElementById('gripClose');
      primary?.scrollIntoView({block: 'nearest'});
    }
    let click;
    if (primary && !document.querySelector('.brand-card-overlay')) {
      const r = primary.getBoundingClientRect();
      const x = r.x + r.width / 2;
      const y = r.y + r.height / 2;
      if (primary.contains(document.elementFromPoint(x, y))) click = [x, y, primary.innerText];
    }
    const object = state?.operations?.objects?.find(entry => entry.kind === 'dead_fish' && !entry.held_by);
    const progress = items.filter(item => item.done).length + (goal?.progress || 0);
    return {beat: beat(), progress, click, held: arm?.held, fish: object?.pos, hints, radio,
      walked: (state?.procedure?.seen?.length || 0) > 0,
      frames: frames.splice(0), pos: state?.pos,
      heading: state?.euler?.[2], locked: state?.locked, mode: state?.operation_mode, type: node?.type,
      velocity: state?.vel, point: window.__viewer?.W?.objectives?.[0]?.point, goal: goal?.id,
      cold: !!window.__coldOpen, outcome: window.__coldOpen?.report.outcome || window.__results?.outcome?.success,
      controls: window.__coldOpen?.controls() || (state && await flightKeys(state.operation_mode)),
      coldHint: document.querySelector('#coldOpenHint')?.dataset.hint};
  };
})();
