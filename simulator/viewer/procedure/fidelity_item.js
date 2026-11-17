// Registers the deployment-procedure fidelity item. Real and standard run the full hands-on deck checks;
// simple (assisted) still uses the full flow but the client asks the crew to do the checks (`checks:"crew"`).
// Quick launch skips the procedure entirely and therefore exceeds what a real crew may do. Imported for its
// side effect by the in-game procedure panel and by the launch menu, so both fidelity panels list it.
import {registerFidelityItem} from '../fidelity.js';

export const PROCEDURE_ITEM = 'deployProcedure';

registerFidelityItem({
  id: PROCEDURE_ITEM,
  labelKey: PROCEDURE_ITEM,
  descriptionKey: 'deployProcedureHelp',
  type: 'choice',
  options: [{value: 'full', labelKey: 'procedureFull'}, {value: 'quick', labelKey: 'procedureQuick'}],
  // All three difficulty presets keep the deck flow; simple difficulty wires crew-done via beginFields.
  defaults: {real: 'full', standard: 'full', assisted: 'full'},
  exceedsReal: true,
  exceeds: function skipsChecks(value) {
    return value === 'quick';
  },
  urlValue: function fromUrl(params) {
    return params.get('procedure') ?? undefined;
  },
}, {
  deployProcedure: '下水流程',
  deployProcedureHelp: '真實與標準：完整潛前檢查後下水；簡單：船員代做檢查後下水。' +
    '「快速下水」略過流程、直接從水中開始（超出真機）。下次載入場景時生效；?nointro 一律略過。',
  procedureFull: '完整作業流程',
  procedureQuick: '快速下水',
});
