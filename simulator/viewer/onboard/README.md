# Onboard camera look (T14b)

`camera_look.js` adds what the vehicle's own camera puts on the picture, in the onboard view only:

- mild radial lens distortion,
- sensor noise that scales with the camera gain chosen by `fx/exposure.js` (more gain, more grain; deep water
  with the lamps off is grainy, a lamp-lit close-up is clean),
- a light block/compression look.

It is the underwater optics pipeline's camera pass (`fx/pipeline.js` `setCameraPass`, see `fx/README.md`):
input and output are linear and already exposed, it runs after `AutoExposurePass` and before the beautify
finish and `OutputPass`. It does not meter or tone-map. **Auto-exposure belongs to `fx/exposure.js` alone**;
the branch's own ~0.9 s exposure loop was dropped. That value was an assumption, not footage (the research
report states that no quantified AE convergence exists), so `exposure.js`'s lag was not changed.

The low / performance tiers have no pipeline and the optics fallback renders the legacy look, so neither has a
camera look. Other views always skip it.

## Fidelity

`cameraLook` (toggle): on in `real` (a real feed has these artefacts), off in `assisted`; turning it off is
marked as exceeding the real vehicle.

Cost, measured with `python tools/browser_onboard_smoke.py --size 1920x1080 --frames 10` (optics tier
`quality=medium`, swiftshader, machine load about 17, frames synchronised with a pixel read):

| run | look off | look on | change |
|---|---|---|---|
| 1 | 1621 ms | 2195 ms | +35 % |
| 2 | 1846 ms | 1850 ms | +0 % |
| 3 | 1451 ms | 1602 ms | +10 % |
| 4 | 1591 ms | 1742 ms | +9 % |
| 5 | 1316 ms | 1468 ms | +12 % |

Median +10 %, below the +30 % limit, so `real` defaults to on. (On software GL the `auto` tier starts in the
legacy look, so most automated checks never run the pass.)

## Not here, on purpose

- OSD / overlay text: the HUD (`hud/osd.js`) owns it.
- Video delay: the `videoDelayMs` fidelity item (state buffer).
- Water optics, exposure, backscatter, particles, silt: `fx/`.

All coefficients are provisional presentation assumptions, not calibrated camera, sensor or X1 lens values (the
report notes distortion is model specific: flat port pincushion versus wide dome barrel; X1 is unknown). Photo
eligibility is geometric (`observation_camera.js`) and camera transforms are never modified.
