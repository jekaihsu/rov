// Frame-cost probe for the performance tools (browser_gpu_bench.py --profile / --check).
// Injected with page.add_init_script before any page script runs. It counts, per animation frame, what the page
// asks WebGL to do (draws, triangles, instances, render passes with their viewport sizes, buffer and texture
// uploads, program switches, shader compiles, synchronous read-backs) and how long the frame's JavaScript took.
// It also tracks GPU texture / buffer memory allocated through the context. It never changes what is drawn.
// Use window.__perfProbe.snapshot(frames) after a warm-up; window.__perfProbe.reset() starts a new window.
(function installPerfProbe() {
  if (window.__perfProbe) return;
  const frames = [];
  const LIMIT = 600;
  const textureBytes = new Map();
  const bufferBytes = new Map();
  const boundTextures = new Map();
  const boundBuffers = new Map();
  const totals = {compiles: 0, programs: 0, readbacks: 0, syncQueries: 0};
  let ids = 0;
  let current = newFrame();

  function newFrame() {
    return {
      draws: 0, instancedDraws: 0, instances: 0, triangles: 0, points: 0, lines: 0,
      passes: [], uploadsBytes: 0, textureUploads: 0, programSwitches: 0, compiles: 0, readbacks: 0,
      syncQueries: 0, jsMs: 0, clears: 0
    };
  }

  function currentPass(gl) {
    const passes = current.passes;
    const last = passes[passes.length - 1];
    if (last && !last.closed) return last;
    const viewport = gl.__probeViewport || [0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight];
    const pass = {target: gl.__probeTarget || 0, width: viewport[2], height: viewport[3], draws: 0, triangles: 0};
    passes.push(pass);
    return pass;
  }

  function closePass() {
    const last = current.passes[current.passes.length - 1];
    if (last) last.closed = true;
  }

  function primitives(mode, count, gl) {
    if (mode === gl.TRIANGLES) return [count / 3, 'triangles'];
    if (mode === gl.TRIANGLE_STRIP || mode === gl.TRIANGLE_FAN) return [Math.max(0, count - 2), 'triangles'];
    if (mode === gl.POINTS) return [count, 'points'];
    return [count / 2, 'lines'];
  }

  function recordDraw(gl, mode, count, instances) {
    const [amount, kind] = primitives(mode, count, gl);
    const pass = currentPass(gl);
    current.draws += 1;
    pass.draws += 1;
    if (instances > 1 || instances === 0) current.instancedDraws += 1;
    current.instances += instances;
    current[kind] += amount * instances;
    if (kind === 'triangles') pass.triangles += amount * instances;
  }

  function textureSize(width, height, type, format, gl) {
    let channels = 4;
    if (format === gl.RED || format === gl.RED_INTEGER || format === gl.LUMINANCE || format === gl.ALPHA) channels = 1;
    else if (format === gl.RG) channels = 2;
    else if (format === gl.RGB) channels = 3;
    let bytes = 1;
    if (type === gl.FLOAT) bytes = 4;
    else if (type === gl.HALF_FLOAT || type === 0x8D61) bytes = 2;
    else if (type === gl.UNSIGNED_SHORT || type === gl.UNSIGNED_INT || type === gl.UNSIGNED_INT_24_8) bytes = 4 / channels;
    return width * height * channels * bytes;
  }

  function internalSize(internal, gl) {
    const table = {
      [gl.RGBA8]: 4, [gl.SRGB8_ALPHA8]: 4, [gl.RGBA16F]: 8, [gl.RGBA32F]: 16, [gl.R8]: 1, [gl.RG8]: 2,
      [gl.R16F]: 2, [gl.R32F]: 4, [gl.RGB8]: 4, [gl.DEPTH_COMPONENT24]: 4, [gl.DEPTH24_STENCIL8]: 4,
      [gl.DEPTH_COMPONENT16]: 2, [gl.DEPTH_COMPONENT32F]: 4, [gl.RGB16F]: 8, [gl.RG16F]: 4
    };
    return table[internal] || 4;
  }

  function patch(gl) {
    if (gl.__probePatched) return gl;
    gl.__probePatched = true;
    const wrap = function wrap(name, after) {
      const original = gl[name];
      if (typeof original !== 'function') return;
      gl[name] = function probed(...args) {
        const result = original.apply(gl, args);
        after(args, result);
        return result;
      };
    };
    wrap('drawArrays', function drawArrays(args) {
      recordDraw(gl, args[0], args[2], 1);
    });
    wrap('drawElements', function drawElements(args) {
      recordDraw(gl, args[0], args[1], 1);
    });
    wrap('drawArraysInstanced', function drawArraysInstanced(args) {
      recordDraw(gl, args[0], args[2], args[3]);
    });
    wrap('drawElementsInstanced', function drawElementsInstanced(args) {
      recordDraw(gl, args[0], args[1], args[4]);
    });
    wrap('bindFramebuffer', function bindFramebuffer(args) {
      if (args[0] === gl.READ_FRAMEBUFFER) return;
      const fb = args[1];
      if (fb && !fb.__probeId) fb.__probeId = ++ids;
      gl.__probeTarget = fb ? fb.__probeId : 0;
      closePass();
    });
    wrap('viewport', function viewport(args) {
      gl.__probeViewport = args.slice(0, 4);
      closePass();
    });
    wrap('clear', function clear() {
      current.clears += 1;
    });
    wrap('useProgram', function useProgram() {
      current.programSwitches += 1;
    });
    wrap('compileShader', function compileShader() {
      current.compiles += 1;
      totals.compiles += 1;
    });
    wrap('linkProgram', function linkProgram() {
      totals.programs += 1;
    });
    wrap('readPixels', function readPixels() {
      current.readbacks += 1;
      totals.readbacks += 1;
    });
    for (const name of ['getError', 'getProgramParameter', 'getShaderParameter', 'finish', 'getBufferSubData',
      'clientWaitSync']) {
      wrap(name, function syncQuery() {
        current.syncQueries += 1;
        totals.syncQueries += 1;
      });
    }
    wrap('bindTexture', function bindTexture(args) {
      boundTextures.set(args[0], args[1]);
    });
    wrap('deleteTexture', function deleteTexture(args) {
      textureBytes.delete(args[0]);
    });
    const setTexture = function setTexture(target, level, bytes) {
      const texture = boundTextures.get(target === gl.TEXTURE_2D || target === gl.TEXTURE_3D ||
        target === gl.TEXTURE_2D_ARRAY ? target : gl.TEXTURE_CUBE_MAP);
      if (!texture) return;
      const entry = textureBytes.get(texture) || {};
      entry[`${target}:${level}`] = bytes;
      textureBytes.set(texture, entry);
    };
    wrap('texImage2D', function texImage2D(args) {
      let width = args[3];
      let height = args[4];
      let format = args[6];
      let type = args[7];
      if (args.length === 6) {
        const source = args[5];
        width = source?.naturalWidth || source?.videoWidth || source?.width || 0;
        height = source?.naturalHeight || source?.videoHeight || source?.height || 0;
        format = args[3];
        type = args[4];
      }
      const bytes = textureSize(width, height, type, format, gl);
      setTexture(args[0], args[1], bytes);
      current.uploadsBytes += bytes;
      current.textureUploads += 1;
    });
    wrap('texStorage2D', function texStorage2D(args) {
      let bytes = 0;
      let width = args[3];
      let height = args[4];
      for (let level = 0; level < args[1]; level++) {
        bytes += width * height * internalSize(args[2], gl);
        width = Math.max(1, width >> 1);
        height = Math.max(1, height >> 1);
      }
      const faces = args[0] === gl.TEXTURE_CUBE_MAP ? 6 : 1;
      setTexture(args[0], 0, bytes * faces);
    });
    wrap('texStorage3D', function texStorage3D(args) {
      setTexture(args[0], 0, args[3] * args[4] * args[5] * internalSize(args[2], gl));
    });
    wrap('texSubImage2D', function texSubImage2D(args) {
      const source = args[args.length - 1];
      const bytes = source?.byteLength || (source?.width || 0) * (source?.height || 0) * 4;
      current.uploadsBytes += bytes;
      current.textureUploads += 1;
    });
    wrap('renderbufferStorageMultisample', function renderbufferStorageMultisample(args) {
      totals.renderbufferBytes = (totals.renderbufferBytes || 0) + args[1] * args[3] * args[4] *
        internalSize(args[2], gl);
    });
    wrap('bindBuffer', function bindBuffer(args) {
      boundBuffers.set(args[0], args[1]);
    });
    wrap('deleteBuffer', function deleteBuffer(args) {
      bufferBytes.delete(args[0]);
    });
    wrap('bufferData', function bufferData(args) {
      const data = args[1];
      const bytes = typeof data === 'number' ? data : data?.byteLength || 0;
      const buffer = boundBuffers.get(args[0]);
      if (buffer) bufferBytes.set(buffer, bytes);
      current.uploadsBytes += bytes;
    });
    wrap('bufferSubData', function bufferSubData(args) {
      const data = args[2];
      const length = args[4] || (data?.byteLength || 0) - (args[3] || 0) * (data?.BYTES_PER_ELEMENT || 1);
      current.uploadsBytes += length * (args[4] ? data?.BYTES_PER_ELEMENT || 1 : 1);
    });
    return gl;
  }

  const getContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function probedGetContext(kind, ...rest) {
    const context = getContext.call(this, kind, ...rest);
    if (context && (kind === 'webgl2' || kind === 'webgl')) patch(context);
    return context;
  };

  const raf = window.requestAnimationFrame.bind(window);
  let frameTime = null;
  function finishFrame() {
    if (current.draws || current.jsMs) {
      frames.push(current);
      if (frames.length > LIMIT) frames.shift();
    }
    current = newFrame();
  }
  // Every callback of one animation frame receives the same timestamp: a new timestamp closes the previous frame,
  // so GL work and JS time are attributed per vsync even when the page is too slow for timers to run in between.
  window.requestAnimationFrame = function probedRaf(callback) {
    return raf(function timed(now) {
      if (now !== frameTime) {
        if (frameTime !== null) finishFrame();
        frameTime = now;
      }
      const start = performance.now();
      try {
        callback(now);
      } finally {
        current.jsMs += performance.now() - start;
      }
    });
  };

  function sum(map) {
    let total = 0;
    for (const value of map.values()) {
      if (typeof value === 'number') total += value;
      else for (const bytes of Object.values(value)) total += bytes;
    }
    return total;
  }

  function median(values) {
    if (!values.length) return null;
    const sorted = values.slice().sort(function ascending(a, b) {
      return a - b;
    });
    return sorted[Math.floor(sorted.length / 2)];
  }

  function percentile(values, fraction) {
    if (!values.length) return null;
    const sorted = values.slice().sort(function ascending(a, b) {
      return a - b;
    });
    return sorted[Math.min(sorted.length - 1, Math.round((sorted.length - 1) * fraction))];
  }

  window.__perfProbe = {
    reset() {
      frames.length = 0;
      current = newFrame();
      totals.compiles = 0;
      totals.readbacks = 0;
      totals.syncQueries = 0;
    },
    frames() {
      return frames.slice();
    },
    snapshot() {
      const rendered = frames.filter(function drew(frame) {
        return frame.draws > 0;
      });
      const pick = function pick(key) {
        return median(rendered.map(function value(frame) {
          return frame[key];
        }));
      };
      const passes = rendered.length ? rendered[rendered.length - 1].passes.filter(function used(pass) {
        return pass.draws > 0;
      }).map(function brief(pass) {
        return {target: pass.target, size: `${pass.width}x${pass.height}`, draws: pass.draws,
          triangles: Math.round(pass.triangles)};
      }) : [];
      return {
        frames: frames.length,
        renderedFrames: rendered.length,
        draws: pick('draws'),
        instancedDraws: pick('instancedDraws'),
        instances: pick('instances'),
        triangles: Math.round(pick('triangles') || 0),
        points: Math.round(pick('points') || 0),
        passes: passes.length,
        passList: passes,
        fullScreenPasses: passes.filter(function fullScreen(pass) {
          return pass.draws <= 2 && pass.triangles <= 2;
        }).length,
        uploadsKB: Math.round((pick('uploadsBytes') || 0) / 1024),
        textureUploads: pick('textureUploads'),
        programSwitches: pick('programSwitches'),
        jsMsMedian: Math.round((median(frames.map(function js(frame) {
          return frame.jsMs;
        })) || 0) * 100) / 100,
        jsMsP95: Math.round((percentile(frames.map(function js(frame) {
          return frame.jsMs;
        }), 0.95) || 0) * 100) / 100,
        compilesInWindow: totals.compiles,
        programsLinkedTotal: totals.programs,
        readbacksPerFrame: rendered.length ? totals.readbacks / rendered.length : 0,
        syncQueriesPerFrame: rendered.length ? totals.syncQueries / rendered.length : 0,
        textureMB: Math.round(sum(textureBytes) / 1048576 * 10) / 10,
        bufferMB: Math.round(sum(bufferBytes) / 1048576 * 10) / 10,
        renderbufferMB: Math.round((totals.renderbufferBytes || 0) / 1048576 * 10) / 10
      };
    }
  };
})();
