// Local MIT onnxruntime-web adapter. Model contract: RGB NCHW -> normalized [x,y,w,h,score,class].
let session;
let ort;
self.onmessage = async function infer(event) {
  const {id, config, pixels, size} = event.data;
  try {
    if (config) {
      ort = await import(config.runtimeUrl);
      ort.env.wasm.wasmPaths = config.wasmPaths;
      try {
        session = await ort.InferenceSession.create(config.modelUrl, {executionProviders: ['webgpu']});
      } catch {
        session = await ort.InferenceSession.create(config.modelUrl, {executionProviders: ['wasm']});
      }
      self.postMessage({id, detections: []});
      return;
    }
    const input = new Float32Array(3 * size * size);
    for (let i = 0; i < size * size; i++) {
      for (let c = 0; c < 3; c++) input[c * size * size + i] = pixels[i * 4 + c] / 255;
    }
    const output = await session.run({[session.inputNames[0]]: new ort.Tensor('float32', input, [1, 3, size, size])});
    const data = output[session.outputNames[0]].data;
    const detections = [];
    for (let i = 0; i < data.length; i += 6) {
      if (data[i + 4] < .5) continue;
      detections.push({cls: data[i + 5], score: data[i + 4], box: Array.from(data.slice(i, i + 4))});
    }
    self.postMessage({id, detections});
  } catch (error) {
    self.postMessage({id, error: String(error)});
  }
};
