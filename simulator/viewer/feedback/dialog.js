// Modal form: one-line description plus a category, then save the attached screenshot and summary.
import { localize } from '../i18n/index.js';

const STRINGS = localize('feedback.dialog', {
  title: '回報問題',
  lead: '請用一句話描述問題。截圖與最近 60 秒狀態會一併附上，只存在本機，不會自動上傳。',
  description: '問題描述',
  placeholder: '例如：解鎖後右搖桿無反應',
  category: '分類',
  categories: {
    visual: '畫面',
    feel: '手感',
    crash: '當機',
    text: '文字',
    other: '其他',
  },
  submit: '儲存回報',
  cancel: '取消',
  saving: '正在儲存…',
  savedDesktop: '已存到本機回報資料夾',
  savedBrowser: '已下載回報 ZIP',
  failed: '儲存失敗：{reason}',
  openFolder: '開啟回報資料夾',
  required: '請先寫一句描述。',
});

const CATEGORIES = ['visual', 'feel', 'crash', 'text', 'other'];

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export function createFeedbackDialog({ onSubmit, canOpenFolder, onOpenFolder, onClose = null }) {
  const root = element('section', 'feedback-dialog');
  root.id = 'feedbackDialog';
  root.hidden = true;
  root.setAttribute('role', 'dialog');
  root.setAttribute('aria-modal', 'true');
  root.setAttribute('aria-labelledby', 'feedbackTitle');
  const panel = element('div', 'feedback-panel');
  const title = element('h2', 'feedback-title', STRINGS.title);
  title.id = 'feedbackTitle';
  const lead = element('p', 'feedback-lead', STRINGS.lead);
  const form = element('form', 'feedback-form');
  form.id = 'feedbackForm';
  const descLabel = element('label', 'feedback-label', STRINGS.description);
  descLabel.htmlFor = 'feedbackDescription';
  const description = element('textarea', 'feedback-description');
  description.id = 'feedbackDescription';
  description.name = 'description';
  description.rows = 3;
  description.maxLength = 280;
  description.required = true;
  description.placeholder = STRINGS.placeholder;
  const catLabel = element('label', 'feedback-label', STRINGS.category);
  catLabel.htmlFor = 'feedbackCategory';
  const category = element('select', 'feedback-category');
  category.id = 'feedbackCategory';
  category.name = 'category';
  for (const id of CATEGORIES) {
    const option = document.createElement('option');
    option.value = id;
    option.textContent = STRINGS.categories[id];
    category.append(option);
  }
  const status = element('p', 'feedback-status');
  status.id = 'feedbackStatus';
  status.setAttribute('role', 'status');
  const actions = element('div', 'feedback-actions');
  const cancel = element('button', 'feedback-cancel', STRINGS.cancel);
  cancel.type = 'button';
  cancel.id = 'feedbackCancel';
  const submit = element('button', 'feedback-submit', STRINGS.submit);
  submit.type = 'submit';
  submit.id = 'feedbackSubmit';
  const openFolder = element('button', 'feedback-folder', STRINGS.openFolder);
  openFolder.type = 'button';
  openFolder.id = 'feedbackOpenFolder';
  openFolder.hidden = !canOpenFolder?.();
  actions.append(cancel, submit);
  if (canOpenFolder?.()) actions.append(openFolder);
  form.append(descLabel, description, catLabel, category, status, actions);
  panel.append(title, lead, form);
  root.append(panel);
  document.body.append(root);

  let open = false;
  let busy = false;

  function setStatus(text, ok = true) {
    status.textContent = text || '';
    status.dataset.state = text ? (ok ? 'ok' : 'err') : '';
  }

  function show() {
    if (open) return;
    open = true;
    busy = false;
    form.reset();
    category.value = 'other';
    setStatus('');
    submit.disabled = false;
    submit.textContent = STRINGS.submit;
    root.hidden = false;
    description.focus({ preventScroll: true });
  }

  function hide() {
    if (!open) return;
    open = false;
    root.hidden = true;
    setStatus('');
    onClose?.();
  }

  cancel.addEventListener('click', hide);
  openFolder.addEventListener('click', async function openReports() {
    try {
      await onOpenFolder?.();
    } catch (error) {
      setStatus(STRINGS.failed.replace('{reason}', error?.message || ''), false);
    }
  });
  root.addEventListener('keydown', function onKey(event) {
    if (event.code === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      hide();
    }
  });
  form.addEventListener('submit', async function submitForm(event) {
    event.preventDefault();
    if (busy) return;
    const text = description.value.trim();
    if (!text) {
      setStatus(STRINGS.required, false);
      description.focus({ preventScroll: true });
      return;
    }
    busy = true;
    submit.disabled = true;
    submit.textContent = STRINGS.saving;
    setStatus('');
    try {
      const result = await onSubmit({
        description: text,
        category: category.value || 'other',
      });
      const message = result?.mode === 'desktop' ? STRINGS.savedDesktop : STRINGS.savedBrowser;
      setStatus(message, true);
      setTimeout(hide, 900);
    } catch (error) {
      setStatus(STRINGS.failed.replace('{reason}', error?.message || ''), false);
      submit.disabled = false;
      submit.textContent = STRINGS.submit;
      busy = false;
    }
  });

  return {
    show,
    hide,
    get open() {
      return open;
    },
  };
}
