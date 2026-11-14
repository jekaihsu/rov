# Underwater optics: fixed-position review shots

Rework of T07 (#26) after its review: the lit wreck at 32 m had gone almost black, the water above the
horizon was a hard black band and the lamp-lit seabed blew out. The pipeline structure is taken from #26
(`task/T07-visuals`, merged into this branch); the light model, auto-exposure, water background, surface
and particles are new. How it works and every assumption: `simulator/viewer/fx/README.md`.

All shots: real viewer (`index.html`), onboard camera, `quality=medium`, 1600×900, device scale factor 1,
JPEG. Each is a one-frame replay built from the real simulator (scenario world + a vehicle placed at a fixed
pose); no teleport command, no fixture scene. HUD and training markers are the app's own.

```bash
cd simulator
python tools/browser_underwater_shots.py --url http://127.0.0.1:8080 --out OUT --frames 4 --query "quality=medium&beautify=0"
python tools/browser_underwater_shots.py --url http://127.0.0.1:8080 --out OUT --frames 4 --query "quality=medium&beautify=1"
```

`before/` is `main` at `afc3319` (the branch base) with the same tool and poses.

| Shot | Scenario, pose | Before (main) | After, real | After, beautify |
|---|---|---|---|---|
| Shallow reef | `coral_reef`, 12.5 m, 1.5 m off the sand, coral 2.9 m ahead, lamps off, visibility 18 m | [before](before/reef.jpg) | [real](real/reef.jpg) | [beautify](beautify/reef.jpg) |
| Seagrass | `seagrass_meadow`, 7.6 m, 1.4 m off the bottom, lamps off, visibility 12 m | [before](before/seagrass.jpg) | [real](real/seagrass.jpg) | [beautify](beautify/seagrass.jpg) |
| Harbour | `harbor_inspection`, 8 m, pile A 2 m ahead, lamps level 1, visibility 7 m | [before](before/harbour.jpg) | [real](real/harbour.jpg) | [beautify](beautify/harbour.jpg) |
| Wreck, lamps 1 | `korean_castle`, 25 m, hull plating about 2.3 m ahead, lamps level 1 | [before](before/wreck-lit-1.jpg) | [real](real/wreck-lit-1.jpg) | [beautify](beautify/wreck-lit-1.jpg) |
| Wreck, lamps 2 | same pose, lamps level 2 | [before](before/wreck-lit-2.jpg) | [real](real/wreck-lit-2.jpg) | [beautify](beautify/wreck-lit-2.jpg) |
| Wreck, lamps off | same pose, lamps off | [before](before/wreck-dark.jpg) | [real](real/wreck-dark.jpg) | [beautify](beautify/wreck-dark.jpg) |

The wreck shots are at 25 m, not 32 m: the 32 m figure is the seabed; the hull side at the bow section is
reachable at 2-3 m stand-off only at mid-height. The first inspection objective's stand-off point turned out
to look into open water in the rendered model, so a pose checked against the server's distance field and the
rendered hull was used instead.

Camera auto-exposure at capture (from `real/shots.json`; `exposure` is the adapted gain, `target` what
the meter asks for, clamped to 0.3-400):

| Shot | Metered luminance (linear) | Target | Exposure at capture |
|---|---|---|---|
| Reef | 5.8e-3 | 30.9 | 30.9 |
| Seagrass | 7.5e-3 | 24.0 | 24.0 |
| Harbour | 4.7e-3 | 38.2 | 40.5 |
| Wreck, lamps 1 | 2.0e-3 | 91.2 | 105.9 |
| Wreck, lamps 2 | 3.5e-3 | 51.8 | 64.2 |
| Wreck, lamps off | 9.7e-5 | 400 (clamped) | 400 |

The capture advances only 4 frames per shot (software rendering here takes 3-40 s per frame), so the two
lit wreck shots were still 15-25 % above their settled exposure when captured; the lamp 1 / lamp 2 pair
therefore looks almost the same. That is also what a camera with auto-exposure does: the second lamp
level lowers the gain (target 91 -> 52), it does not make the picture twice as bright.

## Notes against the target look

- **Water colour / background (review item 2).** Every view direction now shows the in-scatter integral
  for an infinite ray (`b E(z) / (c - Kd u)`), drawn as a full-screen background and used as the end
  point of every surface's water path, so distant sand and the background meet without a seam and the
  reef/seagrass water is blue-green, not black. Reef (18 m visibility) reads cyan-blue, harbour (7 m)
  and the wreck site (10 m) green, which matches the per-channel model (coastal water absorbs blue
  through dissolved/particulate matter). Self-critique: the shallow shots are now *too* even and
  saturated cyan; contrast between sand and water is low and the seagrass blades are barely visible at
  3-5 m. The before image had more local contrast (but a dark, unlit look and a seam at the horizon).
- **Per-channel extinction.** Daylight reaching 12.5 m has lost almost all red (reef coral reads
  cyan-grey); the lamp-lit hull at 2.3 m keeps some warm/brown fouling colour but is still green-dominated,
  because lamp -> hull -> camera is 4.6 m of water (red transmission about 4 %, green about 11 %).
  Footage (below) says true colours only come back within 0.3-1 m, so this is consistent; the task text's
  "1-3 m with real colours" is optimistic for 10 m water. Beyond about visibility everything ends in the
  water colour (harbour pile edges, wreck edges).
- **Lamps (review items 1 and 3).** Lamps now use inverse-square falloff (decay 2), a soft 120° flood
  and extinction both ways; auto-exposure meters the frame and `OutputPass` tone-maps once. The lit wreck
  is no longer black (main had a blown-out disc with a hard edge in a black frame; #26 had it almost
  black) and the harbour pile is no longer a white column; both show the falloff from the beam centre.
- **Backscatter.** Lamp backscatter is a per-pixel integral (visible as the lighter veil in the beam
  direction in harbour and around the wreck hot spot) plus instanced point particles lit by the lamps.
  The particles are visible in the lit wreck shots as small specks; in daylight shots there are few.
- **Deep, lamps off.** At 25 m with the lamps off the exposure hits its 400 limit and the frame is dark
  green with only the hull's edges readable. With the hull filling the frame there is little open water
  to silhouette it against, so "silhouettes" is only weakly demonstrated by this pose.
- **Beautify** (`?beautify=1`, fidelity item `waterBeautify`; the HUD's fidelity chip shows 自訂 because
  it exceeds the real preset): faint sun shafts in the reef shot (top right), caustic bands on the sand,
  a gentle vignette; nothing changes in the deep shots except the vignette. With it off nothing remains.
- **Observation photos:** unchanged geometry; see `simulator/viewer/fx/README.md`.

## Comparison with real small-ROV footage

`research_notes/洋流與波浪對ROV作業/real_dive_footage.md` §8 (Bilibili footage of FIFISH V6-family and other
small ROVs; not X1, colours from re-encoded video, ±10 per channel):

| Footage target (§8) | Simulator now | Agreement |
|---|---|---|
| 8. Same water 4 -> 15 m: R and B drop to about 1/3, G nearly unchanged; open sea cyan R≈15, G≈B≈190 | Sampled from the JPEGs (20 px boxes): reef water background (0, 120, 134), sun-lit sand near the camera (56, 188, 181); seagrass water (0, 132, 126); harbour water (41, 121, 92); wreck site lamps off (0, 44, 27). In 10 m coastal water blue falls about as fast as green (yellow-substance absorption), giving green | Hue of the sea water matches (R near zero, G ≈ B); the horizontal background is about 35 % darker than the footage cyan, the sand matches it. Coastal/harbour water is green. The lake case (G stays, B and R drop) needs a lake water type, which the scenarios do not have |
| 9. White balance changes the look more than depth | No white-balance model: the camera is fixed at the lamps' white | **Not done.** A camera white-balance setting (Auto / fixed 5500 K) belongs in the camera pass (T14b) |
| 10. Visibility: sea 6-10 m, lake 1-1.5, harbour 1-2, turbid river 0.3-1 | Taken from scenario data: harbour scenario is 7 m, wreck 10 m, reef 18 m | Harbour scenario is clearer than the footage says; that is scenario data, not changed here |
| 11. True colours only within about 0.3-1 m under lights | Hull at 2.3 m is still green-dominated with a little warm colour; colour returns fully only very close | Consistent |
| 12. Lit night: 500-1000 point particles per 720p frame, about 0.3 % of frame width; daylight about 50; streaks when moving | 1024 / 2048 / 4096 particles (medium/high/ultra) in a 4 m box around the camera, 0.12-0.3 % of frame width, lit by the lamps; daylight shots show few. Not counted in the shots | Order of magnitude and size yes; **motion streaks not done** (particles are static points per frame) |
| 13. Lamp cone visible from outside in turbid water | The backscatter integral draws the beam in third-person views; the app's old additive cones are hidden while optics are on | Not captured here (all shots are onboard) |
| 7. Near the surface the dome breaks the surface and blows out for 0.2-0.4 s | Not modelled | **Not done** (belongs to the surface-crossing / camera work) |

## Low tier cost

`quality=performance` (the low tier) does not install the pipeline: `installUnderwaterPipeline` returns
`null`, `renderer.render` is not wrapped, materials keep the original depth shader and the lamps keep their
legacy falloff. Measured anyway, same real-viewer replay frames, 1600×900, software GL on a 4-core machine
with load average 40-70 from other jobs (so only gross regressions would show):

| Seconds per frame (`quality=performance`) | main run 1 | branch run 1 | main run 2 | branch run 2 |
|---|---|---|---|---|
| Harbour | 1.70 | 1.33 | 1.55 | 1.03 |
| Wreck, lamps 1 | 7.60 | 6.45 | 4.24 | 6.26 |

No consistent difference; the spread between runs of the same tree is larger than between trees.

`python tools/run_browser_checks.py browser_fleet_perf` (PASS in both trees; it measures peer cable and
state-buffer work, not rendering, so it is unaffected by this change):

| | main | branch |
|---|---|---|
| peer cables, unoptimised path, 120 frames | 48.8 ms | 107.9 ms |
| peer cables, optimised path, 120 frames | 1.4 ms | 1.5 ms |
| state buffer mean / median / p95 per frame | 0.22 / 0.1 / 0.3 ms | 0.21 / 0.1 / 0.5 ms |
| adaptive resolution: reduced width / low scale | 640 / 50 % | 640 / 50 % |

The unoptimised-path number is the script's deliberately slow reference loop and swings with machine load.

The optics tiers (medium and up, and `auto` until its first slow sample) cost a full-screen half-float
scene target, the exposure passes (a 32×18 meter, a 1×1 adaptation, one full-screen apply), the
background quad, 8×2 lamp-backscatter samples per shaded pixel and the instanced particles. In software
GL here the medium-tier capture frames took 0.6-1.8× the time of main's (shots.json; noisy). Not measured on a GPU.

## Not done / known gaps

- The shots were taken on a heavily loaded machine with software GL (3-40 s per frame), 4 frames each.
  Nothing here was looked at on a real GPU; frame time of the optics tiers on integrated graphics is
  unmeasured. The `auto` tier falls back to the legacy look on its first slow sample.
- Unlit helpers (objective wire spheres, flow particles, current arrow) are divided by the exposure so
  they keep their designed brightness; the app's flow particles are white dots and are far more visible
  than the simulated suspension in daylight. They are a training aid that already existed.
- Lamp-to-daylight ratio, phase factors and the exposure range are tuned on these six shots; they are
  assumptions (listed in `simulator/viewer/fx/README.md`), not measurements.
- Not done: white balance, motion streaks for particles, surface-break blow-out, Snell's window was not
  captured in any of the six poses (none looks up).
