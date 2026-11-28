// Select the field recording from the deployed world. Unknown sites retain the engine's synthesized bed.
function siteBed(world) {
  const biome = world?.scenario?.biome;
  if (biome === 'aquaculture') return 'farm';
  if (biome === 'harbor' || biome === 'harbour') return 'harbor';
  const obstacles = world?.obstacles || [];
  if (obstacles.some(ob => ob.kind === 'wreck')) return 'wreck';
  if (obstacles.some(ob => ['jacket_leg', 'monopile', 'transition_piece'].includes(ob.kind))) return 'wind';
  return null;
}

// AudioBufferSourceNode loops on decoded sample boundaries. Share pending loads and discard stale selections.
export function createAmbience(ctx, destination) {
  const buffers = new Map();
  let wanted = null;
  let current = null;
  let world;
  let site;
  let retryAt = 0;

  async function load(name) {
    const response = await fetch(new URL('./ambience/' + name + '.opus', import.meta.url));
    if (!response.ok) throw new Error('Missing ambience: ' + name);
    return ctx.decodeAudioData(await response.arrayBuffer());
  }

  async function select(name) {
    wanted = name;
    retryAt = 0;
    if (current) {
      const {source, gain, started} = current;
      const level = 0.65 * Math.min(1, (ctx.currentTime - started) / 0.8);
      gain.gain.cancelScheduledValues(ctx.currentTime);
      gain.gain.setValueAtTime(level, ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.8);
      source.stop(ctx.currentTime + 0.8);
      current = null;
    }
    if (!name) return;
    if (!buffers.has(name)) buffers.set(name, load(name));
    try {
      const buffer = await buffers.get(name);
      if (wanted !== name || current) return;
      const source = ctx.createBufferSource();
      const gain = ctx.createGain();
      source.buffer = buffer;
      source.loop = true;
      source.connect(gain).connect(destination);
      source.onended = function disconnect() {
        source.disconnect();
        gain.disconnect();
      };
      gain.gain.setValueAtTime(0, ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.65, ctx.currentTime + 0.8);
      source.start();
      current = {source, gain, started: ctx.currentTime};
    } catch {
      buffers.delete(name);
      if (wanted === name) retryAt = ctx.currentTime + 8;
    }
  }

  return function update(nextWorld, surface, underwater) {
    if (world !== nextWorld) {
      world = nextWorld;
      site = siteBed(world);
    }
    const marine = world?.scenario && !world.scenario.key?.includes('pool')
      && world.scenario.water_type !== 'fresh_clear';
    const name = surface && marine ? 'deck' : underwater && !surface ? site : null;
    if (name !== wanted || (retryAt && ctx.currentTime >= retryAt)) select(name);
  };
}
