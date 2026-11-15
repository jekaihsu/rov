// Detector contract: normalized top-left xywh boxes, asynchronous detect(frame).
export class OracleDetector {
  constructor({miss = 0, falsePositive = 0, jitter = 0, random = Math.random} = {}) {
    Object.assign(this, {miss, falsePositive, jitter, random});
  }
  async detect(frame) {
    const results = frame.truth.filter(() => this.random() >= this.miss).map(target => ({
      ...target,
      cls: target.category,
      score: 1,
      box: target.box.map((value, index) => index < 2
        ? Math.max(0, Math.min(1 - target.box[index + 2], value + (this.random() - .5) * this.jitter))
        : value),
    }));
    if (this.random() < this.falsePositive) {
      results.push({cls: 'unknown', score: .5, box: [this.random() * .9, this.random() * .9, .1, .1]});
    }
    return results;
  }
}

export class RemoteDetector {
  constructor(url) {
    this.socket = new WebSocket(url);
    this.nextId = 0;
    this.pending = new Map();
    this.socket.onmessage = event => {
      const reply = JSON.parse(event.data);
      const pending = this.pending.get(reply.id);
      if (pending) {
        clearTimeout(pending.timer);
        this.pending.delete(reply.id);
        pending.resolve(reply.detections);
      }
    };
  }
  async detect(frame) {
    if (this.socket.readyState !== WebSocket.OPEN) return [];
    const id = ++this.nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(Error('Remote inference timeout'));
      }, 2000);
      this.pending.set(id, {resolve, timer});
      this.socket.send(JSON.stringify({id, image: frame.image, width: frame.width, height: frame.height}));
    });
  }
  dispose() {
    this.socket.close();
  }
}

export class OnnxDetector {
  constructor(config) {
    this.size = config.size || 320;
    this.worker = new Worker(new URL('./onnx_worker.js', import.meta.url), {type: 'module'});
    this.pending = new Map();
    this.nextId = 0;
    this.worker.onmessage = event => {
      const pending = this.pending.get(event.data.id);
      if (!pending) return;
      clearTimeout(pending.timer);
      this.pending.delete(event.data.id);
      if (event.data.error) pending.reject(Error(event.data.error));
      else pending.resolve(event.data.detections);
    };
    this.ready = this.request({config});
  }
  request(message) {
    const id = ++this.nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(Error('ONNX worker timeout'));
      }, 30000);
      this.pending.set(id, {resolve, reject, timer});
      this.worker.postMessage({id, ...message});
    });
  }
  async detect(frame) {
    await this.ready;
    const canvas = new OffscreenCanvas(this.size, this.size);
    const context = canvas.getContext('2d');
    context.drawImage(frame.canvas, 0, 0, this.size, this.size);
    return this.request({pixels: context.getImageData(0, 0, this.size, this.size).data, size: this.size});
  }
  dispose() {
    this.worker.terminate();
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(Error('Detector disposed'));
    }
    this.pending.clear();
  }
}
