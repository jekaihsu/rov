// Launch-menu side of the cold open (docs/design/cold-open/README.md §4): the routing of a launch through the cold
// open, the new-game start from the title, the 介面 setting row and the 重玩開場 card of the story list. The rule
// itself (when it plays, the URLs) is cold_open_flow.js; this module only turns it into menu controls.
import { chapterCard } from '../menu/cards.js';
import {
  PROLOGUE, PROLOGUE_CONTRACT, coldOpenUrl, isNewGame, loadColdOpen, playsBefore, setColdOpenEnabled,
} from './cold_open_flow.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('story.cold_open_menu', {
  toggle: ['開場片段', '新遊戲時先播放兩三分鐘的倒敘開場（離岸風場導管架）。只播一次；關閉後直接從序章開始。'],
  replay: ['重玩開場', '再看一次新遊戲的倒敘開場：離岸風場導管架上的一次纜線勾纏。可以跳過。'],
});
// The site whose menu preview stands for the cold open (same jacket builder, menu/previews).
const PREVIEW_SCENE = 'jacket_inspection';

/** The URL to open for a launch: through the cold open when this choice starts the prologue for the first time. */
export function routeLaunch(url, choice, {replay = false} = {}) {
  if (replay) return coldOpenUrl(url, {replay: true});
  return playsBefore(choice) ? coldOpenUrl(url) : url;
}

/** Whether the title's 開始 should start a new game directly (cold open, then the prologue). */
export function startsNewGame({hasLastSession, career, completedChapters}) {
  return isNewGame({hasLastSession, career, completedChapters});
}

/**
 * Launch a new game: the career's prologue work order when the career data has it, else the story prologue.
 * ctx: the launch-menu context (choice, chapterFor, launch, launchContract, career).
 */
export function launchNewGame(ctx) {
  const contract = ctx.career?.data?.contracts?.find(function prologueOrder(entry) {
    return entry.id === PROLOGUE_CONTRACT;
  });
  if (contract && ctx.launchContract) {
    ctx.launchContract(contract, ctx.choice.model);
    return;
  }
  const chapter = ctx.chapterFor(PROLOGUE);
  Object.assign(ctx.choice, {mission: 'campaign', chapter: PROLOGUE, scenario: chapter?.scenario || 'tutorial_pool'});
  ctx.launch();
}

/** The 介面 tab's on/off row, in the mountToggles item shape. */
export function coldOpenToggle(idPrefix) {
  const [label, help] = STRINGS.toggle;
  return {
    id: `${idPrefix}ColdOpen`,
    label,
    help,
    checked: loadColdOpen().enabled,
    onChange(value) {
      setColdOpenEnabled(value);
    },
  };
}

/** The 重玩開場 card for the story list; onChoose replays the cold open. */
export function replayTitle() {
  return STRINGS.replay[0];
}

export function replayCard(index, onChoose) {
  const [title, outline] = STRINGS.replay;
  const card = chapterCard({id: 'cold_open', title, outline, scenario: PREVIEW_SCENE}, {
    index,
    status: 'open',
    onChoose,
  });
  card.id = 'coldOpenReplay';
  return card;
}
