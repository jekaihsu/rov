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
// Call update() once per frame after the underwater lighting has patched the materials (app.js frame loop).
const CHECK_MS = 1000;

export function createShaderWarmup({ renderer, scene, camera }) {
  let nextCheck = 0;
  let signature = -1;
  let warmed = 0;

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

  // Without the extension a compile blocks just as it would on first sight, and would also block for materials that
  // are never shown: warm only where the driver compiles in the background (Chrome on D3D11 / Metal / most GL).
  const parallel = !!renderer.extensions?.has?.('KHR_parallel_shader_compile');

  function update(now = performance.now()) {
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
