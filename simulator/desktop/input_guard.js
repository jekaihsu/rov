// Desktop-only input gate. Resume requires a deliberate click after focus or overlay loss.
(() => {
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
})();
