// Shader warm-up: compiles the programs of everything in the scene before it is first drawn.
// three.js compiles a material's program the first time an object using it is rendered, synchronously, in the middle
// of a frame. Objects that are loaded or shown later (the vehicle model when the pilot first leaves the onboard view,
// the support boat and its crew, LOD levels, assets that finish loading after the first frame) each cost a stall of
// tens to hundreds of milliseconds on a laptop GPU, mid-dive. Once a second this module checks whether the scene's
// object count changed; when it did, it hands every material (hidden objects included) to renderer.compile, which
// starts the compiles and links without waiting for their status (three r160 checks a program on first use; with
// KHR_parallel_shader_compile the driver compiles in the background), with the same render target the frame will use
// so the programs match (linear HDR target in the optics tiers, the canvas otherwise). compileAsync is not used: its
// readiness poll throws for materials that have no program yet.
//
// S2: during a black screen or title card (`idleCover`) the warm-up also briefly raises lamp intensity and unhides
// fish / beam proxies so the first lights-on, first school and first photo do not compile mid-dive. Without the
// parallel-compile extension it still warms while the cover hides the hitch.
// Call update() once per frame after the underwater lighting has patched the materials (app.js frame loop).
const CHECK_MS = 1000;
const IDLE_FORCE_MS = 400;

export function createShaderWarmup({renderer, scene, camera, getLamps = null, getEnvironment = null}) {
  let nextCheck = 0;
  let signature = -1;
  let warmed = 0;
  let lastIdleWarm = 0;
  let lampBoosted = false;

  function objectCount() {
    let count = 0;
    scene.traverse(function countObject() {
      count++;
    });
    return count;
  }

  // The render target the scene pass draws into: program variants differ in tone mapping and output colour space.
  function sceneTarget() {
    const pipeline = renderer.userData?.underwaterPipeline;
    if (!pipeline?.optics || !pipeline.composer) return null;
    return pipeline.composer.renderTarget1;
  }

  function revealFish(visible) {
    const env = getEnvironment?.();
    for (const school of env?.fishSchools?.schools ?? env?.schools ?? []) {
      const root = school.mesh;
      if (!root) continue;
      root.userData._warmupWasVisible = root.userData._warmupWasVisible ?? root.visible;
      root.visible = visible ? true : root.userData._warmupWasVisible;
    }
  }

  function boostLamps(on) {
    const lamps = getLamps?.();
    if (!lamps?.length) return;
    if (on && !lampBoosted) {
      for (const lamp of lamps) {
        lamp.userData._warmupIntensity = lamp.intensity;
        lamp.intensity = Math.max(lamp.intensity, 1.2);
        lamp.visible = true;
      }
      lampBoosted = true;
    } else if (!on && lampBoosted) {
      for (const lamp of lamps) {
        if (lamp.userData._warmupIntensity != null) lamp.intensity = lamp.userData._warmupIntensity;
      }
      lampBoosted = false;
    }
  }

  function warm() {
    const previous = renderer.getRenderTarget();
    renderer.setRenderTarget(sceneTarget());
    try {
      renderer.compile(scene, camera);
      warmed++;
    } finally {
      renderer.setRenderTarget(previous);
    }
  }

  // Without the extension a compile blocks just as it would on first sight. During an idle cover (black / title
  // card) that hitch is acceptable; otherwise only warm where the driver compiles in the background.
  const parallel = !!renderer.extensions?.has?.('KHR_parallel_shader_compile');

  function update(now = performance.now(), {idleCover = false} = {}) {
    if (idleCover) {
      if (now - lastIdleWarm >= IDLE_FORCE_MS) {
        lastIdleWarm = now;
        revealFish(true);
        boostLamps(true);
        warm();
        revealFish(false);
        boostLamps(false);
        signature = objectCount();
        nextCheck = now + CHECK_MS;
      }
      return;
    }
    if (!parallel || now < nextCheck) return;
    nextCheck = now + CHECK_MS;
    const count = objectCount();
    if (count === signature) return;
    signature = count;
    warm();
  }

  return {
    update,
    parallel,
    get warmed() {
      return warmed;
    },
  };
}
