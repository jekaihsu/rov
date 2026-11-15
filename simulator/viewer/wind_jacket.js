// Named NED camera anchors for the wind foundation; shared by menu and review tools.
export const WIND_JACKET_CAMERAS = Object.freeze({
  boatApproach: {eye: [1, -17, -1.2], target: [20, 0, -5.5]},
  boatLanding: {eye: [12, -15, -1], target: [21, -3, -6]},
  underwaterBraces: {eye: [12, -9, 10], target: [18, -5, 13]},
  intertidal: {eye: [24, -10, -0.5], target: [25.2, -5.2, 0.2]},
});

// Original analytic sea: no photographic textures. Surface is a visual wave around the physical z=0 plane.
export function createWindSea(THREE, time) {
  const material = new THREE.MeshStandardMaterial({
    color: 0x12384a,
    metalness: 0.25,
    roughness: 0.32,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  material.onBeforeCompile = function seaShader(shader) {
    shader.uniforms.seaTime = time;
    shader.vertexShader = 'varying vec3 seaWorld;\n' + shader.vertexShader.replace(
      '#include <worldpos_vertex>',
      '#include <worldpos_vertex>\nseaWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;');
    shader.fragmentShader = 'uniform float seaTime; varying vec3 seaWorld;\n' + shader.fragmentShader;
    shader.fragmentShader = shader.fragmentShader.replace('#include <normal_fragment_maps>', `
      #include <normal_fragment_maps>
      float a = seaWorld.x * 2.1 + seaWorld.z * 1.4 + seaTime * 1.3;
      float b = seaWorld.x * 5.7 - seaWorld.z * 4.3 - seaTime * 1.9;
      vec3 wave = normalize(vec3(cos(a) * .2 + cos(b) * .1, 1., sin(a) * .18));
      normal = normalize(mat3(viewMatrix) * (gl_FrontFacing ? wave : -wave));`);
    shader.fragmentShader = shader.fragmentShader.replace('#include <opaque_fragment>', `
      diffuseColor.a = cameraPosition.y > 0.0 ? 1.0 : .28;
      #include <opaque_fragment>`);
  };
  material.customProgramCacheKey = function seaKey() { return 'wind-sea-v2'; };
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(6000, 6000), material);
  mesh.name = 'wind-sea';
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.y = 0.025;
  mesh.renderOrder = 1;
  return mesh;
}
