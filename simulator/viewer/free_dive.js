// Free exploration uses the normal pilot and shutter. Only the introductory shot owns the camera.
import {getFidelity} from './fidelity.js';
import {createMenuNavigator, loadControllerDatabase} from './menu/navigator.js';
import {createBeatStage, establishingShot, presentStage, element} from './story/beat_stage.js';
import {createCinematicLook} from './story/cutscene_look.js';
import {COLLECTION_CATEGORIES, listCollection} from './collection_store.js';
import {diveLog, divePhase} from './free_dive_model.js';
import {STRINGS} from './free_dive_copy.js';

const NODES = {
  bow: 'Forecastle_deck',
  chain: 'Anchor_chain_and_fallen_spar',
  hatch: 'Hold_02_CoamingLip',
  bridge: 'Aft_window_frames',
  windlass: 'Windlass_and_bollards',
  rail: 'Forecastle_bent_rails',
  silt: 'Hold_02_SiltedHoldFloor',
  frames: '01_BOW_Transverse_frames',
};
const OBSTACLES = {poolwall: 'wall', pile: 'pile', leg: 'jacket_leg', keel: 'bilge_keel', screw: 'propeller'};
const SUBJECTS = {
  tutorial_pool: ['poolwall'],
  harbor_inspection: ['pile', 'harbor_tool', 'fish_school'],
  hull_inspection: ['keel', 'screw'],
  jacket_inspection: ['leg', 'fish_school'],
  coral_reef: ['coral', 'seastar', 'fish_school'],
  wreck_survey: ['fish_school'],
  free_dive_wreck: [...Object.keys(NODES), 'screw'],
};

export function installFreeDive({params, camera, rovG, setCam, radio, rc, readOnly}) {
  const site = params.get('scenario');
  if (readOnly || params.get('freeDive') !== '1' || !Object.hasOwn(SUBJECTS, site)) return null;
  document.body.classList.add('free-dive');
  const look = createCinematicLook();
  const log = diveLog(site);
  const {known, fresh} = log;
  const subjects = new Set(SUBJECTS[site]);
  const baseline = listCollection().then(function prior(collection) {
    log.restore(collection.photos);
  });
  baseline.catch(function unavailable() {});
  const home = document.getElementById('returnMenu');
  let stage;
  let start;
  let heard = false;
  let leaving = false;
  let dialog;
  let panel;
  let navigator;
  loadControllerDatabase().then(function setup(database) {
    navigator = createMenuNavigator({database, handlers: {scope: () => dialog}});
    if (dialog) startNavigation();
  });
  function startNavigation() {
    navigator?.setActive(true);
    navigator?.start();
  }
  let saving = Promise.resolve();
  function contents(summary) {
    const root = element('section');
    root.append(element('h2', '', summary ? STRINGS.summary : STRINGS.checklist));
    for (const category of summary ? fresh : subjects) {
      const label = COLLECTION_CATEGORIES[category];
      root.append(element('p', '', (!summary && known.has(category) ? '✓ ' : '') + label));
      if (known.has(category)) root.append(element('small', '', STRINGS.notes[category]));
    }
    if (summary && !fresh.size) root.append(element('p', '', STRINGS.empty));
    return root;
  }
  function display(summary) {
    dialog = element('dialog', 'free-dive-log');
    const button = element('button', '', summary ? STRINGS.back : '×');
    button.setAttribute('aria-label', summary ? STRINGS.back : STRINGS.checklist);
    dialog.append(contents(summary), button);
    document.body.append(dialog);
    button.onclick = function done() {
      dialog.close();
      if (summary) {
        leaving = true;
        home.click();
      }
    };
    dialog.addEventListener('close', function cleanup() {
      navigator?.setActive(false);
      navigator?.stop();
      dialog.remove();
      dialog = null;
    });
    dialog.showModal();
    button.focus();
    startNavigation();
  }
  home.addEventListener('click', async function exit(event) {
    if (leaving) return;
    event.stopImmediatePropagation();
    await saving;
    if (!dialog) display(true);
  }, true);
  function frame(now, world, state, environment) {
    if (world?.scenario?.key !== site || state?.mission?.mode !== 'free_explore') return;
    if (start === undefined) {
      start = now;
      stage = createBeatStage('freeDiveOpening', [STRINGS[site], STRINGS.title], '');
      presentStage(stage, {black: 0, letterbox: true, cinematic: true, location: true, reveal: []});
      setCam('cine');
      look.set(true);
      for (const target of environment?.observationTargets || []) {
        if (target.entity_id?.startsWith('inspection-') && Object.hasOwn(STRINGS.notes, target.category)
            && Object.hasOwn(COLLECTION_CATEGORIES, target.category)) {
          subjects.add(target.category);
        }
      }
    }
    const phase = divePhase(now - start);
    if (stage && phase.opening) {
      rc.keep_depth = 1;
      rc.right_switch = 1;
      rc.rc_lock = state.input_latched ? 1 : 0;
      establishingShot(camera, rovG, phase.progress);
    } else if (stage) {
      look.release();
      setCam('onboard');
      stage.body.classList.remove('cold-open', 'cold-open-cinematic');
      delete stage.body.dataset.coldReveal;
      stage.root.remove();
      stage.style.remove();
      stage = null;
      panel = element('button', 'free-dive-list', STRINGS.checklist);
      panel.onclick = function checklist() { display(false); };
      document.body.append(panel);
    } else if (!heard && phase.radioDue && !state.paused && !dialog) {
      if (getFidelity().get('crewCalls')) radio.sayFlight(['supervisor', STRINGS.radio]);
      heard = true;
    }
  }
  function targets(worldGroup, obstacles, environment) {
    const found = [];
    for (const category of subjects) {
      if (NODES[category]) {
        const mesh = worldGroup.getObjectByName(NODES[category]);
        if (mesh) found.push({category, entity_id: NODES[category], mesh});
      } else if (OBSTACLES[category]) {
        const meshes = new Set();
        for (const {ob, mesh} of obstacles.values()) {
          if (!mesh.isMesh || ob.kind !== OBSTACLES[category] || meshes.has(mesh)) continue;
          meshes.add(mesh);
          found.push({category, entity_id: ob.name, mesh});
        }
      }
    }
    for (const target of environment?.observationTargets || []) {
      if (subjects.has(target.category)) found.push(target);
    }
    return found.map(target => ({...target, priority: known.has(target.category) ? 2 : 0}));
  }
  async function record(evidence, store) {
    if (!evidence.ok || !subjects.has(evidence.category) || !Object.hasOwn(STRINGS.notes, evidence.category)) {
      return store(null);
    }
    await baseline;
    const {category, entity_id} = evidence;
    const result = await store({category, entity_id});
    log.record(category);
    return result;
  }
  function pauseActions() {
    return [{id: 'pauseDiveGuide', label: STRINGS.checklist, run: () => display(false)}];
  }
  return {frame, targets, pauseActions, get blocked() { return !panel || !!dialog; },
    save: record,
    notice(entry) {
      return entry ? STRINGS.recorded.replace('{name}', COLLECTION_CATEGORIES[entry.category]) : STRINGS.saved;
    },
    beginPhoto() {
      let finish;
      saving = new Promise(resolve => { finish = resolve; });
      return finish;
    },
  };
}
