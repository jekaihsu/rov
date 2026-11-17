// Asks Chromium for the discrete GPU on hybrid-graphics laptops (Intel iGPU + NVIDIA/AMD dGPU, e.g. UHD 620 + MX110),
// where the browser otherwise renders on the integrated chip. Must run before the app's ready event.
// Chromium defines the switch as "force-high-performance-gpu" (gpu/config/gpu_switches.cc); Electron's command-line
// switch documentation spells it "force_high_performance_gpu". Both are appended: Chromium ignores the one it does
// not know. ROV_LOW_POWER_GPU=1 keeps the system's choice (battery play).
const SWITCHES = ['force-high-performance-gpu', 'force_high_performance_gpu'];

function requestDiscreteGpu(app, env = process.env) {
  if (env.ROV_LOW_POWER_GPU === '1') return [];
  for (const name of SWITCHES) app.commandLine.appendSwitch(name);
  return SWITCHES.slice();
}

module.exports = { requestDiscreteGpu, SWITCHES };
