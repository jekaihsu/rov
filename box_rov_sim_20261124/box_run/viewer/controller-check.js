'use strict';

// Independent of the 3D viewer and SDK: this page only samples browser input.
const byId = (id) => document.getElementById(id);
const devices = new Map();
let currentPads = [], lastError = '';
const number = (v) => Number.isFinite(v) ? v : 0;

function createDevice(pad) {
  const article = document.createElement('article');
  const heading = document.createElement('h2');
  heading.textContent = `裝置 ${pad.index}：${pad.id}`;
  const mapping = document.createElement('p');
  mapping.textContent = `按鍵配置：${pad.mapping || '非標準（需另行對應）'} · ${pad.axes.length} 軸 · ${pad.buttons.length} 按鍵`;
  const table = document.createElement('table');
  table.innerHTML = '<thead><tr><th>軸</th><th>目前數值</th><th>本次最小值 / 最大值</th></tr></thead>';
  const axes = pad.axes.map((value, i) => {
    const row = table.insertRow();
    row.insertCell().textContent = `Axis ${i}`;
    return { value: row.insertCell(), range: row.insertCell(), min: number(value), max: number(value) };
  });
  const buttonBox = document.createElement('div');
  buttonBox.className = 'buttons';
  const buttons = pad.buttons.map(() => {
    const el = document.createElement('span');
    el.className = 'button'; buttonBox.append(el); return el;
  });
  article.append(heading, mapping, table, buttonBox);
  byId('devices').append(article);
  return { article, axes, buttons, id: pad.id, mapping: pad.mapping, seenButtons: new Set() };
}

function sample() {
  lastError = '';
  currentPads = [];
  try {
    if (typeof navigator.getGamepads !== 'function') {
      lastError = window.isSecureContext ? '瀏覽器沒有提供遊戲手把介面，請使用 Chrome 或 Edge。' : '目前不是安全來源，請在電腦開啟 http://127.0.0.1:8080/controller-check.html。';
    } else {
      currentPads = Array.from(navigator.getGamepads()).filter((pad) => pad && pad.connected);
    }
  } catch (error) {
    lastError = `瀏覽器無法讀取手把：${error.name} — ${error.message}`;
  }
  for (const [index, device] of devices) {
    if (!currentPads.some((pad) => pad.index === index)) {
      device.article.remove(); devices.delete(index);
    }
  }
  for (const pad of currentPads) {
    let device = devices.get(pad.index);
    if (device && (device.id !== pad.id || device.mapping !== pad.mapping || device.axes.length !== pad.axes.length || device.buttons.length !== pad.buttons.length)) {
      device.article.remove(); devices.delete(pad.index); device = null;
    }
    if (!device) { device = createDevice(pad); devices.set(pad.index, device); }
    pad.axes.forEach((value, i) => {
      const axis = device.axes[i], v = number(value);
      axis.min = Math.min(axis.min, v); axis.max = Math.max(axis.max, v);
      axis.value.textContent = v.toFixed(4);
      axis.range.textContent = `${axis.min.toFixed(4)} / ${axis.max.toFixed(4)}`;
    });
    pad.buttons.forEach((button, i) => {
      const pressed = button.pressed || number(button.value) > 0.1;
      if (pressed) device.seenButtons.add(i);
      device.buttons[i].textContent = `B${i}: ${number(button.value).toFixed(2)}`;
      device.buttons[i].classList.toggle('pressed', pressed);
    });
  }
  byId('context').textContent = `頁面焦點：${document.hasFocus() ? '在此頁' : '不在此頁，請點一下'} · 安全來源：${window.isSecureContext ? '是' : '否'}`;
  byId('status').textContent = lastError || (currentPads.length
    ? `已偵測到 ${currentPads.length} 個裝置。推桿時觀察軸值、按鍵時觀察 B 編號。`
    : '尚未收到遊戲手把輸入。請點一下頁面，再按遙控器任一按鍵。');
}

byId('reportButton').onclick = () => {
  sample();
  const report = {
    secureContext: window.isSecureContext, focused: document.hasFocus(),
    gamepadApi: typeof navigator.getGamepads === 'function', error: lastError,
    devices: currentPads.map((pad) => {
      const device = devices.get(pad.index);
      return {
        id: pad.id, index: pad.index, mapping: pad.mapping || 'non-standard',
        axes: Array.from(pad.axes),
        axisRanges: device.axes.map(({ min, max }) => ({ min, max })),
        buttonCount: pad.buttons.length, buttonsSeen: [...device.seenButtons].sort((a, b) => a - b),
      };
    }),
  };
  const output = byId('report');
  output.value = JSON.stringify(report, null, 2); output.hidden = false;
  output.focus(); output.select();
};
sample();
setInterval(sample, 50);
