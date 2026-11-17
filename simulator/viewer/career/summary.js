// Career summary on the launch menu's main screen: one status line (YX licence held · money · real pilot hours)
// and 繼續職涯, the screen's primary button, which opens the recommended next work order (rules.js) one press
// away from the dive. The assisted hours and the next licence are on the line's tooltip; the full logbook
// figures are on the results screen.
import { createHero, primaryButton, statusLine } from '../menu/big_picture.js';
import { licenceProgress, recommendedContract } from './rules.js';
import { assistedHours, realHours } from './save.js';
import { moneyText } from './board.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('career.summary', {
  kicker: '下一張委託',
  status: '{licence} · {money} 元 · 真實 {real} h',
  hours: '真實 {real} h · 輔助 {assisted} h',
  next: '下一張執照：{label}',
  top: '已取得目前最高的執照',
  resume: '繼續職涯',
  nothing: '暫無可接工單',
});

/**
 * {element, refresh(), actions} for the main screen (actions: the row other text actions join).
 * ctx.career and ctx.openContract come from career/menu.js.
 */
export function buildCareerSummary(ctx) {
  const root = document.createElement('section');
  root.className = 'career-summary';
  root.id = 'careerSummary';
  const status = statusLine('careerStatus');
  const hero = createHero({ titleTag: 'h3' });
  hero.element.classList.add('bp-hero-corner');
  hero.title.id = 'careerNext';
  hero.kicker.textContent = STRINGS.kicker;
  const { button: resume } = primaryButton('careerContinue', STRINGS.resume, { cap: false });
  hero.actions.append(resume);
  root.append(status, hero.element);
  let target = null;
  resume.addEventListener('click', function continueCareer() {
    if (target) ctx.openContract(target);
  });
  function refresh() {
    const { data, save, sceneKeys } = ctx.career;
    const progress = licenceProgress(save, data);
    status.textContent = STRINGS.status.replace('{licence}', progress.current?.label || '')
      .replace('{money}', moneyText(save.money)).replace('{real}', realHours(save).toFixed(1));
    const hours = STRINGS.hours.replace('{real}', realHours(save).toFixed(1))
      .replace('{assisted}', assistedHours(save).toFixed(1));
    const next = progress.next ? STRINGS.next.replace('{label}', progress.next.label) : STRINGS.top;
    status.title = [hours, next].join('\n');
    target = recommendedContract(data, save, sceneKeys);
    resume.disabled = !target;
    hero.setTitle(target ? target.title : STRINGS.nothing);
  }
  return { element: root, refresh, actions: hero.actions };
}
