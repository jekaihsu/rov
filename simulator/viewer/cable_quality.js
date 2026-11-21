// Cable tube resolution for the live tether (presentation only). Lower tiers keep a readable yellow tube without
// rebuilding thousands of vertices every frame on integrated GPUs.
export function cableTubeOptions(mode = 'auto', {startsLow = false} = {}) {
  if (mode === 'high' || mode === 'ultra') {
    return {radius: 0.0065, segments: 240, radial: 8, colors: true};
  }
  if (mode === 'performance' || mode === 'low' || startsLow) {
    return {radius: 0.0065, segments: 96, radial: 5, colors: true};
  }
  return {radius: 0.0065, segments: 160, radial: 6, colors: true};
}

// How often the thick tube may rebuild (Hz). The thin polyline can stay at the display rate.
export function cableTubeHz(mode = 'auto', {startsLow = false} = {}) {
  if (mode === 'performance' || mode === 'low' || startsLow) return 20;
  if (mode === 'high' || mode === 'ultra') return 60;
  return 30;
}
