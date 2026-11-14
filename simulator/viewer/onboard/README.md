# Onboard camera look (T14b)

`camera_look.js` adds what the vehicle's own camera puts on the picture, in the onboard view only:

- mild radial lens distortion,
- low-light sensor noise (stronger in dark areas),
- a light block/compression look,
- centre-weighted auto-exposure that follows the scene with a ~0.9 s first-order lag (metered every 200 ms).

It is the `cameraLook` fidelity item, currently opt-in (off) in both presets and preset-neutral. A real feed has
these artefacts, so `real` should eventually turn it on, but with software WebGL the extra full-screen pass roughly
doubles the frame time at 1080p (measured about 380 ms -> 640-1040 ms per frame under swiftshader) and
`browser_menu_smoke.py` then lost its connection after launch. Other views always render the plain scene.

Not here, on purpose:

- **OSD / overlay text**: the HUD is being redesigned in the camera-OSD style elsewhere; this module draws no text.
- **Video delay**: already the `videoDelayMs` fidelity item (state buffer), so the branch's 0/80/150 ms setting
  was dropped.
- **Water optics** (attenuation, backscatter, fog): scene/fx territory, being reworked separately.

Photo capture (`capturePhoto`, expedition photos) keeps rendering the clean scene, so observation evidence and
the geometric checks in `observation_camera.js` are unaffected. Camera transforms are never modified.

All coefficients, response times and lens parameters are provisional presentation assumptions, not calibrated
camera, sensor or vehicle values. No third-party assets or dependencies are added.

TODO(fx pipeline): there is no `simulator/viewer/fx/` pipeline with a `setCameraPass` hook on main yet. When it
lands, register this module's pass through that hook and drop its own `render()`; until then app.js calls
`cameraLook.render()` in place of `renderer.render(scene, camera)`.
