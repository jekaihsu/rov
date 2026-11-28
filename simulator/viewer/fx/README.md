# Underwater optics (`simulator/viewer/fx/`)

The screen pipeline structure (an `EffectComposer` that only exists in the optics tiers, the `setCameraPass`
hook, quality tiers, offscreen bypass) comes from the first T07 pull request (#26, branch
`task/T07-visuals`). The light model, exposure, background, surface and particles were reworked after its
review: the lit wreck rendered almost black, the water above the horizon was a hard black band and the
lamp-lit seabed blew out. This document describes the reworked version.

## What a frame does (medium, high, ultra, and auto until it falls back)

1. `underwater_lighting.js` patches every `MeshStandardMaterial` once (`onBeforeCompile`, program key
   `water-optics-v3`):
   - **daylight** (directional, hemisphere, ambient and the high-tier reflection cube) is multiplied by
     `exp(-Kd * depth)` per channel at the shaded point: the surface -> object leg;
   - **lamps** (every `SpotLight` in the scene) keep three's inverse-square and cone falloff and are
     multiplied by `exp(-c * lampDistance)`: the lamp -> object leg;
   - three's fog is replaced by `waterApply`: the object -> camera leg `color * exp(-c * L)` plus daylight
     scattered into that segment (closed form, below) plus lamp backscatter (8 samples along the ray).
2. `water_optics.js` updates one set of shared uniforms per frame (`waterUniforms`), draws a full-screen
   **water background** that evaluates the same in-scatter integral for an infinite ray in each pixel's
   direction, and turns the lamps into physical lamps while optics are on (decay 2, no cut-off distance,
   soft 120° beam whose intensity falls smoothly from the axis, penumbra 1). The legacy values are restored
   when the look falls back.
3. `surface.js` shades the surface from below: Snell's window (critical angle for n = 1.333) with moving
   normals, total internal reflection of the water below outside it, then the same water path to the camera.
4. `suspension.js` draws instanced marine snow in a 4 m box around the camera, lit by the lamps (inverse
   square, beam, extinction both ways) and faint daylight. Particles are point-like (about 0.3 % of the
   frame width, from real footage), slightly larger and softer right at the lens. Silt puffs are not drawn
   here (the silt module owns them).
5. `pipeline.js` renders: scene (linear HDR, half float) -> `AutoExposurePass` -> camera pass (optional,
   T14b) -> beautify finish (vignette, only when enabled) -> `OutputPass`. `OutputPass` is the only tone
   mapping (ACES) and output transfer; `renderer.toneMappingExposure` is held at 1 while composing.
   Since the performance pass (`docs/design/performance/`) the exposure gain, the onboard camera look, the vignette
   and the output step are one full-screen pass (`camera_output.js`); `AutoExposurePass` then only runs its three
   tiny meter passes (`deferApply`). A camera pass that is not the known camera look still runs on its own, on the
   exposed image, and the exposure pass applies the gain for it as before. The water background is drawn after the
   other opaque meshes, depth tested on the far plane, so only uncovered pixels evaluate its in-scatter integral;
   the surface seen from below (no depth write) is drawn right after it.

### The water model (`water_model.js`, pure functions, tested by `tests/test_water_optics.mjs`)

Per channel R, G, B (about 620 / 540 / 470 nm):

| Symbol | Meaning | Source in the frame |
|---|---|---|
| `c` | beam attenuation, direct signal (lamp -> object, object -> camera) | green: `4.8 / visibility`; red adds pure-water absorption |
| `b` | scattering, drives in-scatter and backscatter | 92 % of residual extinction on the shelf, 80 % elsewhere |
| `Kd` | diffuse attenuation of daylight going down | Lee et al. (2005) with a 20° sun and a backscatter fraction of 0.0183 |

The clean-water `visibility` is published by the silt module (`scene.userData.waterVisibility`: the
scenario's visibility, or the legacy silt-reduced value when the server sends no turbidity field, or the
display distance when the "real visibility" toggle is off); without it the scene fog is read instead. Water colour at infinity looking with vertical
component `u` from depth `z` is `b * E(z) / (c - Kd u)` with `E(z) = exp(-Kd z)`. Distant objects tend to
exactly this colour, so there is no seam at the horizon, and looking up is brighter than looking down.

**Water type.** The scenario's optional `water_type` (`world.scenario.water_type`, PROTOCOL.md; the server
derives it from the biome when a scenario does not set it) adds yellow substance (CDOM and detritus)
absorption `a_g(440)`, spectrum `exp(-0.015 (lambda - 440))`, taken out of the same visibility budget:

| `water_type` | Sites (default from biome) | `a_g(440)` 1/m | Look |
|---|---|---|---|
| `oceanic` | reef and open-water training site (Jerlov I-III) | 0.015 | blue-cyan |
| `coastal` | seagrass (Jerlov coastal 1-3) | 0.08 | cyan-green |
| `shelf` | temperate: offshore wind, jackets, wrecks (coastal 3-7) | 0.2 | blue-green, subdued at depth |
| `harbour` | harbor (coastal 7-9) | 0.35 | yellow-green |
| `fresh_clear` | pool | 0 | clear |

Blue is absorbed first, so the in-scattered water colour moves from blue to green as `a_g` rises (test:
blue/green ratio of the water colour falls oceanic > coastal > shelf > harbour). Very clear display
visibilities (the third-person training fog) cannot make shelf water blue any more: the yellow substance
caps the clarity. Missing or unknown type (old recordings): no yellow substance, the previous generic water.

Red leaves first: in 10 m visibility daylight red is below 3 % at 10 m while green is still above 10 %
(test). Lamp light travels lamp -> object -> camera, so near objects in the lamps keep their colour at any
depth while daylit objects lose red with depth plus distance, as described in
`docs/reference/real-rov-research.md` ("色彩沿整條光路流失").

### Exposure (`exposure.js`)

The scene is metered on the GPU (32 x 18 grid, centre-weighted log-average luminance), the log exposure
moves towards its target with a first-order lag (`tau` 0.35 s, symmetric in stops). With lamps on, the meter
corrects 65 % of the error in stops around a reference gain of 50, within `[0.3, 400]`. With lamps off, it
corrects 82 % around a reference gain of 25 and caps the gain at 800. Between gains of 400 and 800 the
output gradually mixes up to 55 % equal-luminance grey into the colour, modelling low-light chroma reduction.
No pixel is read back for rendering (`state.exposure()` is a synchronous diagnostic for
tools only).

**Highlight protection** (`metering.js`, pure, mirrored by the GPU adaptation pass, tested by
`tests/test_metering.mjs`). A log-average meter follows whatever fills most of the frame; under the lamps that is
dark water, so it opened the camera up until the lamp-lit subject clipped. Like a video camera's AE, the target is
also capped by the bright end of the frame: the level that the brightest 5 % of the centre-weighted meter
(quarter-stop histogram of the cells) exceeds may reach at most 0.8 on the exposed scale (about sRGB 220 after
ACES). The cap is a hard minimum with the ordinary target, so frames without a sizeable bright area (lamps off,
uniform water, a single glint) keep exactly the previous exposure; small speculars may still clip. Above water the
daylight camera (`AutoExposurePass.metering`) keeps its fixed gain without the cap.

**White balance.** The same pass runs the camera's auto white balance (`white_balance.js`, pure functions
mirrored by the GPU meter, tested by `tests/test_white_balance.mjs`). Small ROV cameras default to auto WB and
the WB setting changes the look more than depth (`research_notes/洋流與波浪對ROV作業/real_dive_footage.md` §8
target 9), but working-camera footage with auto WB keeps the water strongly coloured (net pens R/G 0-0.1, B/G
0.25-0.7 linear; reef water blue; lake and harbour water green; `docs/design/underwater-look/README.md`). So the
model is a camera AWB, not grey world:

- each meter cell is a white-point candidate only if its colour is close to neutral (Gaussian gate across the
  green-magenta axis, width 0.45 in log units, and along the warm-cool axis, width 1.0): saturated water is
  rejected, near lamp-lit subjects (white LED light over a short path) are accepted;
- candidates count with the square of their brightness relative to the previous frame's metered average, capped
  at twice the average (white-patch behaviour): lamp-lit subjects several times brighter than the water drive the
  balance even with a daylight cyan cast, while dark, noisy cells and uniform water of a similar hue do not;
- below 10 % of the centre-weighted frame as candidates the camera keeps its default (daylight) balance, fully
  correcting from 35 % (a uniform frame reaches at most 25 %, so plain water is never pulled grey);
- the correction removes 80 % of the candidates' cast, limited to 0.6 (about 1.8x) along the warm-cool axis and
  0.2 along the green-magenta axis, lagged like the exposure;
- before metering and gain the image passes the sensor's channel overlap (`SENSOR_RESPONSE`: 20 % of green
  into red, 15 % into blue, 6 % of red and blue into green). The renderer's three bands are narrow; a real red
  filter also passes 570-600 nm light that water absorbs far less than 620 nm, so deep green and cyan water
  keeps some red, as in footage (assumed shares, tuned to the footage ranges).

The previous grey-world balance (60 % of the average log cast of every cell, equal weight however dark, gains up
to 3x) pulled green water along the green-magenta axis, which is why harbour and jacket frames turned mauve and
grey. Unlit helpers are divided by these gains too.

Unlit helpers (`MeshBasicMaterial`, lines, points, sprites: objective markers, the flow particles, lamp
glows) are divided by the same exposure (`neutraliseExposure`), so they keep their designed screen
brightness instead of washing out when the camera gains up in deep water. Three's fog colour for those
materials is set to the horizontal water colour during the render.

## Assumptions (not measurements)

Everything numeric here is a visualization assumption; nothing is X1 data. Mark it as such in reviews.

- Pure-water absorption `[0.33, 0.06, 0.02] /m`, scattering share 0.8, particulate absorption spectrum
  `[0.6, 1, 1.7]`, `Kd = 1.1 a + 0.15 b`: textbook orders of magnitude, no water-type table was available.
- `visibility = 4.8 / c` (about 1 % contrast threshold), shared with the silt module.
- Lamps (`LAMP_ASSUMED` in `water_optics.js`, vehicle parameters, provisional): 4,000 lm effective per lamp at
  full power in a smooth 120 degree flood (about 2,500 cd on axis), and the daylight rig at the surface standing
  for 10,000 lux (overcast). That gives `LAMP_SCALE` of about 0.003. Research gives 1,500-3,000 lm per lamp for
  observation-class lamps and a vendor claim of 2 x 6,000 lm for X1 (unverified, x1-measurement-checklist item 12
  is the footage that would settle it). The first calibration (0.03, "overcast daylight at 2 m") made the lamps ten
  times stronger relative to daylight: subjects outshone daylight 7-150 times at 1 m and up to 18 times at 2 m and
  clipped, while footage shows colour coming back only within about 1 m (`docs/design/lamp-exposure/README.md`).
- Daylight in-scatter phase 0.015 and lamp backscatter phase 0.00025, with the near-lamp `1/d²` limited at
  0.5 m: tuned on the review shots so that 10 m visibility shows a veil but keeps a lit hull at 2-3 m readable, and
  harbour water (7 m) is clearly murkier. The lamp veil scales with lamp power like the subjects it veils, so this
  ratio did not change with the lamp scale. A Petzold-type value near 180 degrees (0.0025) was tried and buries a
  hull at 1 m in 4 m water: the integral puts the lamps at the lens, which overstates the near-field veil.
- Multiple-scattering lamp glow (0.007, cube law in `c`; scales with lamp power like the veil) and sediment
  scattering share `[0.85, 0.8, 0.6]`: visual calibration against main's silt screenshots; `silt-validation.md`
  has no image measurements either.
- Water types and their `a_g(440)` values, the spectral slope 0.015/nm and the biome mapping: orders of
  magnitude for open-ocean, coastal and estuarine water, not site data; chlorophyll absorption is not
  modelled separately.
- Auto white balance gate widths, confidence range, strength 0.8, the brightness weighting, the 0.6 / 0.2
  correction limits and the sensor overlap shares: no measured WB behaviour of the vehicle camera exists; tuned so
  the footage colour targets of `docs/design/underwater-look/README.md` hold.
- Exposure key 0.15, partial compensation 0.65 around gain 50, range 0.3-400, lag 0.35 s, centre weighting, the
  highlight cap (brightest 5 % at 0.8 exposed; the brightest lamps-off review frame, sun-lit reef sand at
  13 m, reaches 0.67): the research report has no measured auto-exposure or gain behaviour.
- Particle sizes, density (scaled by `b`) and drift; sun shaft and caustic patterns. Size and the order of
  the visible count follow `research_notes/洋流與波浪對ROV作業/real_dive_footage.md` (§8 target 12), not X1.

## Quality tiers and cost

- `low` / `performance`: `installUnderwaterPipeline` returns `null` at start-up and the renderer is not
  wrapped; the original single-coefficient depth shader (`legacy_lighting.js`) is used. No composer, no
  extra draw calls, no particles.
- `auto`: starts with optics (on software GL it starts with `effectsSuppressed` already set, i.e. the
  legacy look, since there is no frame budget to spend); the first slow sample sets `effectsSuppressed`,
  which switches the frame back
  to the legacy look (materials recompile once, lamps get their legacy falloff back); later slow samples
  lower the resolution as before.
- `medium` / `high` / `ultra`: optics; 1024 / 2048 / 4096 particles in a 4 m box; high and ultra add the small
  procedural reflection cube and millimetre normal detail (from #26).

## Fidelity

Beautify (`fx/beautify.js`) is the fidelity item `waterBeautify` (toggle, `exceedsReal`, off in `real`,
on in `assisted`; `?beautify=1|0` overrides it for one session). It adds faint sun shafts in shallow water,
caustics on upward-facing surfaces and a vignette. With it off, nothing but the real-mode optics remains.
`state.setEnhancements(v)` from #26 now just sets the fidelity item.

## Hooks for other modules

### Camera pass (T14b)

`renderer.userData.underwaterPipeline.setCameraPass(pass)` inserts a pass after auto-exposure and before
the beautify finish and `OutputPass`. Its input and output are linear and already exposed (the sensor gain
has been applied), so sensor noise added there scales like real gain noise. Do not tone-map. The caller
owns and disposes the pass; `setCameraPass(null)` removes it. The pass is not used in low / fallback.

### Extra participating medium (silt)

```js
import { addMediumContributor } from './fx/pipeline.js';   // also exported by fx/water_optics.js
const remove = addMediumContributor(function siltAtCamera({ scene, camera, water }) {
  return { extinction: 1.2, scattering: [1.0, 0.95, 0.8], local: true };   // 1/m; or null
});
```

Called once per optics frame. `extinction` adds to the beam attenuation `c` of every light path (so
visibility drops as `4.8 / c`); `scattering` adds to `b`, i.e. to the daylight in-scatter, the water
colour at infinity and the lamp backscatter (per channel gives coloured backscatter, e.g. brown silt); the
absorbed remainder `extinction - scattering` also dims daylight going down unless `local: true` (a cloud
around the camera, not a property of the whole column). The model is homogeneous: the values are taken as
uniform along every ray, so pass the concentration sampled at the camera.

`fx/silt.js` (from main) is the one contributor today. In the optics tiers there is exactly one medium:
it publishes the clean-water visibility and contributes `k * C` at the camera (C from the server's puffs
and near-bed layer, `state.environment`) as `local` sediment with scattering `[0.85, 0.8, 0.6]` of the
extinction (brown-green clouds; the assisted visibility floor caps the total). Its exponential fog, fog
colour and lamp veil are then unused (the optics shaders replace three's fog and the background), so there
is one attenuation path and one lamp-backscatter integral. Its puff sprites stay as geometry and are made
exposure-neutral. In the low / fallback tiers `silt.js` behaves exactly as on main.

Dense water also needs the lamps' multiple scattering, which single scattering misses (extinction kills
the single-scatter path within centimetres): `uLampGlow` = lamp power x `b / c` x `(1 - exp(-0.3 c))^3` x
0.007, added along every camera path. It is negligible below `c` of about 1/m and saturates in a
silt-out; calibrated so `incident_silt` with the lamps full goes near white-out (stronger than main's
grey veil) and near black with the lamps off.

### Site materials (`structure_materials.js`, `seabed.js`)

Both install their own `onBeforeCompile`; `underwater_lighting.js` wraps it (calls it first, then adds the
water light paths) and appends to its program cache key (`structure-fouling-v5-1|water-optics-v3|false`), so
the fouling / seabed colour is applied to `diffuseColor` first and the water maths acts on the result. The flat
look in the first `*-third-optics.jpg` review shots had two other causes: the medium tier had been reduced to a
per-vertex depth-band tint without any texture read (#52, 13cf9fe), and the review tool took one render after
the app had metered its own camera. Medium fouling now breaks the tint up with a cheap two-octave value noise
(ALU only, no texture), and `browser_scene_review.py` lets exposure and white balance settle on the view.

## Above the water (`daylight.js`)

The scene's sun and hemisphere light belong to `daylight.js`. While the camera is below the surface (and in the
top-down map view) they keep exactly the values this model was calibrated with (`UNDERWATER_DAYLIGHT`: hemisphere
1.5, directional 1.6, pale blue); none of the underwater maths above changes. Above the water the same lights take
a daylight preset (`clear`, `overcast`; harbours and fresh water get overcast, `?sky=` overrides for reviews), a
sky dome and an open-sea surface replace the background and the flat surface, the exposure pass meters with a
fixed daylight gain and no grey-world white balance (`AutoExposurePass.metering`), `waterApply` adds aerial haze to
paths that are entirely above water (`uAirHaze`, zero whenever the camera is below), and a display-space grade
after `OutputPass` keeps yellow paint golden. Sun shadows (medium and up) are rendered only above water; below,
the shadow frustum is parked outside the world. Targets and before/after shots: `docs/design/daylight/README.md`.

## Observation photos

Eligibility is still computed by projection, range and raycasts in `observation_camera.js` and the backend;
nothing here reads pixels or moves vertices. The water background, surface (optics material), shafts and
particles carry `userData.observationIgnore`; the background and particles are also non-opaque by the
observation rules. `fogLimit` reads `scene.fog`, which the pipeline only changes for the duration of a
render and restores.

## Review tool

`python tools/browser_underwater_shots.py` (or through `run_browser_checks.py`) builds one-frame replays of
fixed vehicle poses from the real simulator and captures them in the real viewer; see
`docs/design/underwater-visuals/README.md`.
