// Analytic underwater surface window. Refraction uses n=1.333; reflected radiance
// is the local water colour approximation, without an extra scene reflection render.
import * as THREE from 'three';
const surfaces = new WeakMap();

export function updateWaterSurface(surface, camera, scene, low, beauty = false) {
  if (!surface) return;
  let data = surfaces.get(surface);
  if (!data && low) return;
  if (!data) {
    const uniforms = {
      time: { value: 0 }, water: { value: new THREE.Color() }
    };
    const material = new THREE.ShaderMaterial({
      uniforms, side: THREE.DoubleSide, depthWrite: false,
      vertexShader: `varying vec3 world;
        void main() {
          world = (modelMatrix * vec4(position, 1.0)).xyz;
          gl_Position = projectionMatrix * viewMatrix * vec4(world, 1.0);
        }`,
      fragmentShader: `varying vec3 world; uniform float time; uniform vec3 water;
        void main() {
          vec3 view = normalize(cameraPosition - world);
          vec3 normal = normalize(vec3(0.035 * cos(world.x * 1.2 + time), -1.0,
                                      0.025 * sin(world.z * 1.7 - time * 0.7)));
          float incidence = abs(dot(view, normal));
          float window = smoothstep(0.655, 0.67, incidence);
          vec3 transmitted = mix(vec3(0.18, 0.29, 0.32), vec3(0.62, 0.78, 0.83), incidence);
          float fresnel = 0.0204 + 0.9796 * pow(1.0 - incidence, 5.0);
          vec3 reflected = water * 0.7;
          gl_FragColor = vec4(mix(reflected, transmitted, window * (1.0 - fresnel)), 1.0);
          #include <tonemapping_fragment>
          #include <colorspace_fragment>
        }`
    });
    const shaftMaterial = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, side: THREE.DoubleSide,
      uniforms: { time: uniforms.time, depth: { value: 0 } },
      vertexShader: `varying vec2 coord;
        void main() {
          coord = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: `varying vec2 coord; uniform float time; uniform float depth;
        void main() {
          float band = pow(max(0.0, sin(coord.x * 83.0 + sin(coord.y * 5.0 + time * 0.1))), 18.0);
          float fade = sin(coord.y * 3.14159) * exp(-depth / 5.0);
          gl_FragColor = vec4(0.32, 0.48, 0.43, band * fade * 0.035);
        }`
    });
    const shafts = new THREE.Mesh(new THREE.PlaneGeometry(30, 14), shaftMaterial);
    shafts.name = 'shallow-sun-shafts';
    shafts.userData.observationIgnore = true;
    scene.add(shafts);
    data = { original: surface.material, originalIgnore: surface.userData.observationIgnore,
      material, uniforms, shafts };
    surface.userData.observationIgnore = true;
    surfaces.set(surface, data);
  }
  data.shafts.visible = !low && beauty && camera.position.y < 0 && camera.position.y > -12;
  if (data.shafts.visible) {
    data.shafts.position.set(camera.position.x, -7, camera.position.z - 8);
    data.shafts.quaternion.copy(camera.quaternion);
    data.shafts.material.uniforms.depth.value = -camera.position.y;
  }
  surface.material = !low && camera.position.y < 0 ? data.material : data.original;
  data.uniforms.time.value = performance.now() / 1000;
  data.uniforms.water.value.copy(scene.fog?.color || scene.background || new THREE.Color(0x071b20));
}

export function disposeWaterSurface(surface) {
  const data = surfaces.get(surface);
  if (!data) return;
  surface.material = data.original;
  surface.userData.observationIgnore = data.originalIgnore;
  data.material.dispose();
  data.shafts.removeFromParent();
  data.shafts.geometry.dispose();
  data.shafts.material.dispose();
  surfaces.delete(surface);
}
