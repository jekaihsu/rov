// Channel readouts and touch-stick captions follow the live layout and operation mode.
import { CHANNELS } from './actions.js';
import { actionLabel, channelAxis, hintItems, keyLabel } from './bindings.js';
import { currentKeyRows } from './keyboard_layout.js';

function cap(label) {
  const key = document.createElement('kbd');
  key.textContent = label || '—';
  return key;
}

export function installChannelTable() {
  const table = document.getElementById('mapTbl');
  const meters = {};
  let lastMode;
  let lastRows;
  function update(mode) {
    const rows = currentKeyRows();
    if (rows === lastRows && mode === lastMode) return;
    lastRows = rows;
    lastMode = mode;
    const hints = hintItems({axes: true, rows, operationMode: mode});
    table.replaceChildren();
    for (const channel of CHANNELS) {
      const {axis, sign} = channelAxis(channel, mode);
      const direct = rows.find(entry => entry.action === channel);
      const pilot = rows.find(entry => entry.action === axis && entry.pilot);
      const pilotKeys = [...(pilot?.keys || [])];
      if (sign < 0) pilotKeys.reverse();
      const keys = [0, 1].map(index =>
        [direct.keys?.[index], pilotKeys[index]].filter(Boolean).map(keyLabel).join(' / '));
      const label = hints.find(item => item.action === channel)?.label || actionLabel(channel);
      const [positive, negative] = label.split(/\s*[／/]\s*/);
      const row = table.insertRow();
      row.insertCell().textContent = actionLabel(channel);
      row.insertCell().textContent = label;
      const bar = row.insertCell();
      bar.className = 'bar';
      bar.innerHTML = '<div class="track c"><div class="fill"></div></div>';
      const pwm = row.insertCell();
      pwm.className = 'pwm';
      pwm.textContent = '1500';
      meters[channel] = {pwm, fill: bar.querySelector('.fill')};
      if (channel.endsWith('wave')) {
        document.getElementById('lbl_' + channel).replaceChildren(
          negative || '', cap(keys[1]), ' ◀ ' + actionLabel(channel) + ' ▶ ', cap(keys[0]), positive);
      } else {
        document.getElementById('lbl_' + channel + '_p').replaceChildren(cap(keys[0]), positive);
        document.getElementById('lbl_' + channel + '_n').replaceChildren(cap(keys[1]), negative || '');
      }
    }
  }
  update('ROV_USA');
  document.addEventListener('rov-key-rows', event => update(event.detail.operationMode));
  return {meters, update};
}
