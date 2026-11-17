// Fidelity item for the work-order checklist: an instant verdict on each photo ("too far", "not in frame") goes
// beyond what a real pilot gets on the job, where the client reviews the evidence afterwards. In `real` the
// photo is filed without a verdict and the reason shows only on the results screen; the checklist itself (the
// job's scope of work) stays visible in both presets.
import { registerFidelityItem } from '../fidelity.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('career.fidelity_item', {
  photoVerdict: '照片即時判定',
  photoVerdictHelp: '拍照後立刻告訴你照片是否列入交付與原因。真實作業中要等客戶審閱才知道。',
});
export const PHOTO_VERDICT_ITEM = 'photoVerdict';

function isOn(value) {
  return value === true;
}

registerFidelityItem({
  id: PHOTO_VERDICT_ITEM, descriptionKey: 'photoVerdictHelp', type: 'toggle',
  defaults: { real: false, assisted: true }, exceedsReal: true, exceeds: isOn,
}, STRINGS);
