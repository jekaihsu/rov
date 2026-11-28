// Isolated desktop bridge; no raw IPC or native modules are exposed.
// Sandboxed preload (sandbox:true) cannot require node:fs / node:path, so the main
// process passes the build edition through webPreferences.additionalArguments.
const {contextBridge, ipcRenderer} = require('electron');

function readEditionArg(argv = process.argv) {
  const prefix = '--rov-edition=';
  for (const arg of argv) {
    if (!arg.startsWith(prefix)) continue;
    const value = arg.slice(prefix.length);
    if (value === 'steam' || value === 'internal') return value;
  }
  return 'internal';
}

const edition = readEditionArg();

contextBridge.exposeInMainWorld('rovDesktop', Object.freeze({
  edition,
  steamStatus() {
    return ipcRenderer.invoke('rov:steam', 'status');
  },
  steamEvent(event, value = 1) {
    return ipcRenderer.invoke('rov:steam', 'event', { event, value });
  },
  steamPresence(payload) {
    return ipcRenderer.invoke('rov:steam', 'presence', payload);
  },
  steamMock() {
    return ipcRenderer.invoke('rov:steam', 'mock');
  },
  display(value) {
    return ipcRenderer.invoke('rov:display', value);
  },
  readInput() {
    return ipcRenderer.invoke('rov:input-read');
  },
  rememberInput(settings) {
    ipcRenderer.send('rov:input-selected', settings);
  },
  collection(method, payload) {
    if (!['list', 'readPhoto', 'savePhoto', 'saveResult', 'setCover', 'export', 'import'].includes(method)) {
      return Promise.reject(Error('不支援的收藏操作'));
    }
    return ipcRenderer.invoke('rov:collection', method, payload);
  },
  rememberQuality(quality) {
    if (['auto', 'performance', 'medium', 'high'].includes(quality)) {
      ipcRenderer.send('rov:quality-selected', quality);
    }
  },
  rememberModel(model) {
    if (['x1', 'bluerov2_heavy', 'falcon'].includes(model)) {
      ipcRenderer.send('rov:model-selected', model);
    }
  },
  saveReport(payload) {
    return ipcRenderer.invoke('rov:report-save', payload);
  },
  openReportsFolder() {
    return ipcRenderer.invoke('rov:report-open');
  },
  saves: Object.freeze({
    readAll() {
      return ipcRenderer.invoke('rov:saves-read-all');
    },
    write(key, text) {
      return ipcRenderer.invoke('rov:saves-write', key, text);
    },
    backup(key, text) {
      return ipcRenderer.invoke('rov:saves-backup', key, text);
    },
  }),
}));

// Install in the page world before viewer modules create their sockets.
contextBridge.executeInMainWorld({ func: () => {
  let blocked = false;
  const sockets = new Set();
  const NativeSocket = window.WebSocket;
  const channels = ['left_ud', 'left_lr', 'right_ud', 'right_lr', 'left_wave', 'right_wave'];
  function neutral(message) {
    const rc = { ...message.rc, rc_lock: 1, photo: 0, record: 0 };
    for (const channel of channels) rc[channel] = 1500;
    return JSON.stringify({ ...message, rc });
  }
  class GuardedSocket extends NativeSocket {
    constructor(...args) {
      super(...args);
      sockets.add(this);
      this.addEventListener('close', () => sockets.delete(this));
    }
    send(data) {
      try {
        const message = JSON.parse(data);
        if (message.type === 'rc') {
          this.lastControl = message;
          if (blocked) data = neutral(message);
        }
      } catch {}
      super.send(data);
    }
  }
  function pause() {
    blocked = true;
    for (const socket of sockets) {
      if (socket.readyState === NativeSocket.OPEN && socket.lastControl) {
        NativeSocket.prototype.send.call(socket, neutral(socket.lastControl));
      }
    }
  }
  window.WebSocket = GuardedSocket;
  addEventListener('blur', pause);
  addEventListener('keydown', event => {
    if (event.shiftKey && event.code === 'Tab') pause();
  }, true);
  addEventListener('pointerdown', () => { if (document.hasFocus()) blocked = false; }, true);
} });
