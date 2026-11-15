// Career summary on the launch menu's main screen: the YX licence held, money, real and assisted pilot hours, the
// progress toward the next licence, and 繼續職涯, which opens the recommended next work order (rules.js) one
// press away from the dive. A button, so the menu navigator reaches it with the pad.
import { licenceProgress, recommendedContract } from './rules.js';
import { assistedHours, realHours } from './save.js';
import { moneyText } from './board.js';

const STRINGS = {
  kicker: 'YX 職涯',
  money: '資金 {money} 元',
  hours: '真實 {real} h · 輔助 {assisted} h',
  next: '下一張執照：{label}',
  top: '已取得目前最高的執照',
  resume: '繼續職涯',
  resumeLine: '{title}',
  nothing: '看板上暫時沒有可接的工單。',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

/** {element, refresh()} for the main screen; ctx.career and ctx.openContract come from career/menu.js. */
export function buildCareerSummary(ctx) {
  const root = element('section', 'career-summary');
  root.id = 'careerSummary';
  const licence = element('strong', 'career-summary-licence');
  const money = element('p', 'career-summary-money');
  const hours = element('p', 'menu-help');
  const next = element('p', 'menu-help');
  const bar = element('div', 'career-bar');
  const fill = element('i');
  bar.append(fill);
  // A secondary action (outlined): the screen's accent colour stays with its one primary button.
  const resume = element('button', 'menu-next career-resume');
  resume.type = 'button';
  resume.id = 'careerContinue';
  const resumeLine = element('span', 'menu-quick-detail');
  resume.append(element('span', 'menu-label', STRINGS.resume), resumeLine);
  root.append(element('p', 'menu-kicker', STRINGS.kicker), licence, money, hours, next, bar, resume);
  let target = null;
  resume.addEventListener('click', function continueCareer() {
    if (target) ctx.openContract(target);
  });
  function refresh() {
    const { data, save, sceneKeys } = ctx.career;
    const progress = licenceProgress(save, data);
    licence.textContent = progress.current?.label || '';
    money.textContent = STRINGS.money.replace('{money}', moneyText(save.money));
    hours.textContent = STRINGS.hours.replace('{real}', realHours(save).toFixed(1))
      .replace('{assisted}', assistedHours(save).toFixed(1));
    next.textContent = progress.next ? STRINGS.next.replace('{label}', progress.next.label) : STRINGS.top;
    fill.style.width = `${Math.round(progress.fraction * 100)}%`;
    bar.hidden = !progress.next;
    target = recommendedContract(data, save, sceneKeys);
    resume.disabled = !target;
    resumeLine.textContent = target ? STRINGS.resumeLine.replace('{title}', target.title) : STRINGS.nothing;
  }
  return { element: root, refresh };
}
