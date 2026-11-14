// GPU instanced near-field marine snow. Light response is physical presentation;
// density, drift and sizes are provisional scene parameters, not sensor measurements.
import * as THREE from 'three';
const systems = new WeakMap();

export function updateSuspension(scene, camera, renderer, quality) {
  let system = systems.get(scene);
  if (!system && ['performance', 'low'].includes(quality?.mode)) return;
  if (!system) {
    const geometry = new THREE.InstancedBufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute([
      -1,-1,0, 1,-1,0, 1,1,0, -1,-1,0, 1,1,0, -1,1,0
    ], 3));
    const seeds = new Float32Array(2048 * 3);
    let randomState = 42;
    for (let i = 0; i < seeds.length; i++) {
      randomState ^= randomState << 13;
      randomState ^= randomState >>> 17;
      randomState ^= randomState << 5;
      seeds[i] = (randomState >>> 0) / 4294967296;
    }
    geometry.setAttribute('seed', new THREE.InstancedBufferAttribute(seeds, 3));
    const uniforms = {
      source: { value: new THREE.Vector3() }, silt: { value: 0 }, wake: { value: 0 },
      direction: { value: new THREE.Vector3(0, 0, -1) },
      cone: { value: new THREE.Vector2(0.5, 0.8) },
      time: { value: 0 }, lamp: { value: new THREE.Vector3() }, power: { value: 0 },
      flow: { value: new THREE.Vector3(0.025, -0.008, 0.01) }
    };
    const material = new THREE.ShaderMaterial({
      uniforms, transparent: true, depthWrite: false,
      vertexShader: `attribute vec3 seed; uniform float time; uniform vec3 flow;
        uniform vec3 source; uniform float silt; uniform float wake;
        uniform vec3 lamp; uniform vec3 direction; uniform vec2 cone; uniform float power;
        varying vec2 disc; varying float brightness;
        void main() {
          vec3 world = cameraPosition + mod(seed * 12.0 + flow * time, 12.0) - 6.0;
          float density = 1.0;
          if (seed.x > 0.8) {
            world = source + vec3((seed.x - 0.9) * 25.0, seed.y * 1.5 - 1.2, (seed.z - 0.5) * 5.0);
            world.xz += flow.xz * mod(time + seed.y * 7.0, 7.0);
            density = silt;
            if (seed.x > 0.95) {
              world.y = source.y + mod(time * 0.4 + seed.y * 3.0, 3.0);
              density = wake * step(-1.5, source.y) * step(world.y, 0.0);
            }
          }
          float d = length(world - lamp);
          float depth = max(0.0, -world.y);
          float beam = smoothstep(cone.x, cone.y, dot(normalize(world - lamp), direction));
          brightness = 0.08 * exp(-depth / 10.0) + beam * power / (1.0 + d*d) * exp(-d * 0.2);
          brightness *= density;
          vec4 view = viewMatrix * vec4(world, 1.0);
          float blur = 1.0 + 1.5 * exp(-abs(view.z));
          view.xy += position.xy * (0.006 + seed.z * 0.012) * blur;
          disc = position.xy;
          gl_Position = projectionMatrix * view;
        }`,
      fragmentShader: `varying vec2 disc; varying float brightness;
        void main() {
          float a = 1.0 - smoothstep(0.15, 1.0, length(disc));
          gl_FragColor = vec4(vec3(0.72, 0.83, 0.8), a * min(0.6, brightness));
        }`
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.frustumCulled = false;
    mesh.name = 'water-suspension';
    mesh.userData.observationIgnore = true;
    scene.add(mesh);
    system = { mesh, uniforms };
    systems.set(scene, system);
  }
  system.mesh.visible = !['performance', 'low'].includes(quality?.mode) && camera.position.y < 0;
  if (!system.mesh.visible) return;
  system.mesh.geometry.instanceCount = quality?.mode === 'ultra' ? 2048 : quality?.mode === 'high' ? 1024 : 384;
  const state = scene.userData.waterState;
  if (state?.pos) system.uniforms.source.value.set(-state.pos[1], -state.pos[2], state.pos[0]);
  system.uniforms.silt.value = Math.max(0, Math.min(1, state?.silt || 0));
  system.uniforms.wake.value = Math.min(1, (state?.thrust || []).reduce((sum, force) => sum + Math.abs(force), 0));
  const current = scene.userData.waterCurrent;
  if (current) system.uniforms.flow.value.set(-current[1], -current[2] - 0.008, current[0]);
  system.uniforms.time.value = performance.now() / 1000;
  let brightest = null;
  scene.traverse(function findLamp(object) {
    if (object.isSpotLight && object.intensity > (brightest?.intensity || 0)) brightest = object;
  });
  system.uniforms.power.value = brightest ? Math.min(3, brightest.intensity / 100) : 0;
  if (brightest) {
    brightest.getWorldPosition(system.uniforms.lamp.value);
    brightest.target.getWorldPosition(system.uniforms.direction.value);
    system.uniforms.direction.value.sub(system.uniforms.lamp.value).normalize();
    system.uniforms.cone.value.set(Math.cos(brightest.angle), Math.cos(brightest.angle * (1 - brightest.penumbra)));
  }
}
