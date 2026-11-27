// Scenario weather in linear light. Relative intensities and colours are presentation assumptions.
const TIMES = {
  dawn: {angle: 7, direct: 0.55, tint: [1, 0.59, 0.39], sky: 0.35},
  morning: {angle: 38, direct: 0.93, tint: [1, 0.94, 0.84], sky: 0.93},
  dusk: {angle: 3, direct: 0.38, tint: [1, 0.35, 0.15], sky: 0.18},
  night: {angle: -18, direct: 0, tint: [0.45, 0.61, 1], sky: 0.008}
};

export function weatherPreset(presets, name, weather) {
  const base = presets[name];
  if (!weather) return base;
  const cover = weather.cloud_cover;
  const time = Object.hasOwn(TIMES, weather.time_of_day) ? TIMES[weather.time_of_day] : null;
  const preset = {...base};
  if (Number.isFinite(cover)) {
    const t = Math.max(0, Math.min(1, cover));
    for (const key of Object.keys(base)) {
      const a = presets.clear[key];
      const b = presets.overcast[key];
      preset[key] = Array.isArray(a) ? a.map((v, i) => v + (b[i] - v) * t) : a + (b - a) * t;
    }
    preset.cloudCover = t;
  }
  if (time) {
    preset.sunElevationDeg = time.angle;
    preset.sun *= time.direct;
    preset.sunColour = preset.sunColour.map((v, i) => v * time.tint[i]);
    for (const key of ['skyLight', 'groundLight', 'zenith', 'cloudShade', 'cloudLit', 'horizon']) {
      const horizon = key === 'horizon' || key === 'cloudLit';
      preset[key] = preset[key].map((v, i) => time.sky * (horizon
        ? v * time.tint[i] + (1 - time.sky) * time.tint[i] ** 3 : v));
    }
    preset.exposure = Math.min(3, preset.exposure / Math.sqrt(time.sky));
  }
  const rain = Math.max(0, Math.min(1, weather.rain ?? 0));
  preset.hazeDistance /= 1 + 4 * rain;
  const daylight = (time?.sky ?? 1) * (1 - 0.55 * Math.max(0, Math.min(1, cover ?? 0)));
  preset.underwater = (time?.tint ?? [1, 1, 1]).map(v => weather.time_of_day === 'night' ? 0 : v * daylight);
  return preset;
}
