// The last full-screen pass of the optics pipeline (fx/pipeline.js), in place of three's OutputPass: one pass that
// applies the camera's exposure and white balance (fx/exposure.js), the onboard camera look when it can be folded
// in (onboard/camera_look.js), the beautify vignette, and then OutputPass's tone mapping and output transfer.
// Before this module those were up to four full-screen passes, each reading and writing a half-float image the size
// of the screen; folding them changes no step and no order, only where the intermediate values live (registers
// instead of half-float targets), so the picture is the same up to half-float rounding.
// Every option is a uniform, not a define: switching views (the camera look is onboard only) or toggling beautify
// never recompiles the shader.
import * as THREE from 'three';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { exposureUniforms } from './exposure.js';
import { WHITE_BALANCE_GLSL } from './white_balance.js';

// Camera passes that set `outputFold` to this id are drawn by this pass instead of on their own.
export const CAMERA_LOOK_FOLD = 'camera-look-v1';

const VERTEX = /* glsl */ `
  precision highp float;
  uniform mat4 modelViewMatrix;
  uniform mat4 projectionMatrix;
  attribute vec3 position;
  attribute vec2 uv;
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;

// GLSL ES 1.0 (a raw shader, like OutputShader): the 1x1 exposure textures are nearest-filtered, so a texture2D at
// their centre reads the same texel as texelFetch does in the separate passes.
const FRAGMENT = /* glsl */ `
  precision highp float;
  uniform sampler2D tDiffuse;
  uniform sampler2D tCameraExposure;
  uniform sampler2D tCameraBalance;
  uniform float uApplyExposure;
  uniform float uLook;
  uniform vec2 uBlocks;
  uniform float uTime;
  uniform float uNoise;
  uniform vec2 uGain;
  uniform float uVignette;
  #include <tonemapping_pars_fragment>
  #include <colorspace_pars_fragment>
  ${WHITE_BALANCE_GLSL}
  varying vec2 vUv;
  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
  }
  // fx/exposure.js APPLY: the sensor's channel overlap, then exposure and white-balance gains.
  vec3 expose(vec3 c, vec3 gain) {
    return uApplyExposure > 0.5 ? sensorResponse(c) * gain : c;
  }
  void main() {
    float logExposure = texture2D(tCameraExposure, vec2(0.5)).r;
    vec3 gain = exp(logExposure + texture2D(tCameraBalance, vec2(0.5)).rgb);
    vec4 c;
    if (uLook > 0.0) {
      // onboard/camera_look.js LOOK_SHADER on the exposed signal (the exposure is linear, so it commutes with the
      // filtered taps).
      vec2 p = vUv - .5;
      vec2 uv = clamp(.5 + p * (1. + uLook * .08 * dot(p, p)), 0., 1.);
      vec2 block = (floor(uv * uBlocks) + .5) / uBlocks;
      c = texture2D(tDiffuse, uv);
      c.rgb = expose(c.rgb, gain);
      c.rgb = mix(c.rgb, expose(texture2D(tDiffuse, block).rgb, gain), uLook * .18);
      float factor = clamp(exp(logExposure) / uGain.x, 0., uGain.y);
      float grain = hash(gl_FragCoord.xy + floor(uTime * 30.)) - .5;
      c.rgb = max(c.rgb + grain * uLook * uNoise * factor, 0.);
    } else {
      c = texture2D(tDiffuse, vUv);
      c.rgb = expose(c.rgb, gain);
    }
    // fx/pipeline.js beautify finish: a gentle vignette on the exposed linear image.
    float edge = smoothstep(0.25, 0.8, length(vUv - 0.5));
    c.rgb *= 1.0 - uVignette * 0.28 * edge;
    gl_FragColor = c;
    #ifdef LINEAR_TONE_MAPPING
      gl_FragColor.rgb = LinearToneMapping(gl_FragColor.rgb);
    #elif defined(REINHARD_TONE_MAPPING)
      gl_FragColor.rgb = ReinhardToneMapping(gl_FragColor.rgb);
    #elif defined(CINEON_TONE_MAPPING)
      gl_FragColor.rgb = OptimizedCineonToneMapping(gl_FragColor.rgb);
    #elif defined(ACES_FILMIC_TONE_MAPPING)
      gl_FragColor.rgb = ACESFilmicToneMapping(gl_FragColor.rgb);
    #elif defined(AGX_TONE_MAPPING)
      gl_FragColor.rgb = AgXToneMapping(gl_FragColor.rgb);
    #endif
    #ifdef SRGB_TRANSFER
      gl_FragColor = sRGBTransferOETF(gl_FragColor);
    #endif
  }`;

export class CameraOutputPass extends OutputPass {
  constructor() {
    super();
    Object.assign(this.uniforms, {
      tCameraExposure: exposureUniforms.tCameraExposure,
      tCameraBalance: exposureUniforms.tCameraBalance,
      uApplyExposure: { value: 0 },
      uLook: { value: 0 },
      uBlocks: { value: new THREE.Vector2(1, 1) },
      uTime: { value: 0 },
      uNoise: { value: 0 },
      uGain: { value: new THREE.Vector2(1, 1) },
      uVignette: { value: 0 }
    });
    this.material.name = 'CameraOutputShader';
    this.material.vertexShader = VERTEX;
    this.material.fragmentShader = FRAGMENT;
    this.material.uniforms = this.uniforms;
    this.material.needsUpdate = true;
  }

  // Per frame: applyExposure when no separate camera pass sits between the exposure pass and this one; look is the
  // folded camera pass's uniforms (or null); vignette 0..1.
  configure({ applyExposure, look, vignette }) {
    const uniforms = this.uniforms;
    uniforms.uApplyExposure.value = applyExposure ? 1 : 0;
    uniforms.uVignette.value = vignette;
    uniforms.uLook.value = look ? look.uAmount.value : 0;
    if (!look) return;
    uniforms.uBlocks.value.copy(look.uBlocks.value);
    uniforms.uTime.value = look.uTime.value;
    uniforms.uNoise.value = look.uNoise.value;
    uniforms.uGain.value.copy(look.uGain.value);
  }
}
