// Career glue for the launch menu (menu/main.js): loads the career data and save, adds the career screens
// (YX 委託看板, contract detail, YX 裝備部) and the context functions the other screens call (open the board or a
// contract, launch a contract dive, the hangar title with its Block number). A contract dive is an ordinary
// launch with ?contract=<id>; an exam also carries ?fidelity=real&exam=1 and stashes the stored fidelity
// settings, which career/boot.js puts back when the player returns to the menu.
import { getFidelity, STORAGE_KEY as FIDELITY_KEY, fidelityItems } from '../fidelity.js';
import { PROCEDURE_ITEM } from '../procedure/fidelity_item.js';
import { vehicleTitle } from '../fleet_names.js';
import { introForLaunch } from '../menu/preferences.js';
import { buildBoard } from './board.js';
import { buildContractScreen } from './contract_screen.js';
import { buildShop } from './shop.js';
import { buildCareerSummary } from './summary.js';
import { stickerAvailable, updateBlocks } from './shop_rules.js';
import { careerDataFrom, loadCareerData } from './data.js';
import { loadCareer, storeCareer } from './save.js';
import { REPEAT_RATE } from './scoring.js';

function storedFidelity() {
  try {
    return globalThis.localStorage?.getItem(FIDELITY_KEY) ?? '';
  } catch {
    return '';
  }
}

// Whether the launch runs the full pre-dive procedure: an exam uses the real preset's value of that item.
function procedureFull(exam) {
  if (!exam) return getFidelity().get(PROCEDURE_ITEM) === 'full';
  const item = fidelityItems().find(function byId(entry) {
    return entry.id === PROCEDURE_ITEM;
  });
  return item?.defaults.real === 'full';
}

/** ctx: the launch menu context; screens: its screen table. Returns {buildScreens()}. */
export async function installCareerMenu(ctx, screens) {
  // Without its data files the career stays empty; the rest of the menu keeps working.
  const data = await loadCareerData().catch(function noData(error) {
    console.error(error);
    return careerDataFrom({});
  });
  let save = loadCareer();
  updateBlocks(save, data);
  const career = {
    data,
    sceneKeys: new Set(ctx.data.scenes.map(function key(scene) {
      return scene.key;
    })),
    repeatRate: REPEAT_RATE,
    get save() {
      return save;
    },
    sceneFor: ctx.sceneFor,
    setStatus: ctx.setStatus,
    commit(next = save) {
      save = next;
      storeCareer(save);
    },
    replace(next) {
      save = next;
      storeCareer(save);
      for (const screen of Object.values(screens)) {
        if (screen.element?.dataset.active !== undefined) screen.enter?.();
      }
    },
  };
  ctx.career = career;
  ctx.openBoard = function openBoard(tab) {
    if (tab) screens.board.show(tab);
    ctx.go('board');
  };
  ctx.openContract = function openContract(contract) {
    screens.contract.show(contract);
    ctx.go('contract');
  };
  ctx.careerSummary = function careerSummary() {
    return buildCareerSummary(ctx);
  };
  ctx.openShop = function openShop() {
    ctx.go('shop');
  };
  ctx.stickerAvailable = function stickerOpen(preset) {
    return stickerAvailable(save, data, preset);
  };
  ctx.titleFor = function titleFor(vehicle) {
    return vehicleTitle(vehicle.id, save);
  };
  ctx.launchContract = function launchContract(contract, model) {
    const choice = ctx.choice;
    const exam = !!contract.exam;
    choice.mission = contract.runtime === 'chapter' ? 'campaign' : 'free_explore';
    choice.chapter = contract.campaignChapter || '';
    // launchScenario: a variant of the site for this order (start point, slack-water current), same physics.
    choice.scenario = contract.launchScenario || contract.scenario;
    choice.model = model;
    choice.multiplayer = false;
    choice.contract = contract.id;
    choice.exam = exam;
    choice.intro = introForLaunch(choice, procedureFull(exam));
    if (exam && save.fidelityStash === null) {
      save.fidelityStash = storedFidelity();
      storeCareer(save, { mirror: false });
    }
    ctx.launch();
  };
  return {
    career,
    buildScreens() {
      return {
        board: buildBoard(ctx),
        contract: buildContractScreen(ctx),
        shop: buildShop(ctx),
      };
    },
  };
}
