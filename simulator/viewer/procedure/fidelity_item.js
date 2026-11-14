// Registers the deployment-procedure fidelity item. Real operations start with the pre-dive checklist and a
// tended launch; quick launch skips them and therefore exceeds what a real crew may do. Imported for its side
// effect by the in-game procedure panel and by the launch menu, so both fidelity panels list it.
import {registerFidelityItem} from '../fidelity.js';

export const PROCEDURE_ITEM = 'deployProcedure';

registerFidelityItem({
  id: PROCEDURE_ITEM,
  labelKey: PROCEDURE_ITEM,
  descriptionKey: 'deployProcedureHelp',
  type: 'choice',
  options: [{value: 'full', labelKey: 'procedureFull'}, {value: 'quick', labelKey: 'procedureQuick'}],
  defaults: {real: 'full', assisted: 'quick'},
  exceedsReal: true,
  exceeds: function skipsChecks(value) {
    return value === 'quick';
  },
  urlValue: function fromUrl(params) {
    return params.get('procedure') ?? undefined;
  },
}, {
  deployProcedure: '下水流程',
  deployProcedureHelp: '真實作業先做潛前檢查、與纜線手確認再緩放入水；快速下水直接從水中開始。' +
    '下次載入場景時生效；?nointro 一律略過。',
  procedureFull: '完整作業流程',
  procedureQuick: '快速下水',
});
