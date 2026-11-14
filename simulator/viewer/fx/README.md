# Scene optics and camera integration

`installUnderwaterPipeline(renderer)` is idempotent. It returns null in low quality
until a higher quality is selected, leaving renderer.render entirely untouched. Its screen render hook covers
normal frames, `render_movie.js`, recordings and synchronous photo rendering.
Offscreen targets bypass the composer; recursive composer renders bypass the hook.
The composer is allocated only when a screen effect is requested and tracks actual
drawing-buffer dimensions, including automatic resolution changes.

Real mode is the default. `?beautify=1`, or
`renderer.userData.underwaterPipeline.setEnhancements(true)`, enables a subtle
vignette, provisional shallow caustics and sun shafts. `false` disables all three. Scene absorption
and lamp backscatter remain in real mode; disabling beauty does not clear water.
The existing fog/visibility training aid remains independent.

T14b may call `setCameraPass(pass)` to insert its pass after scene rendering and
before scene finishing and `OutputPass`. The caller owns the pass and should
update its camera-dependent uniforms and `enabled` flag for onboard/observer
views. Replace/remove it with `setCameraPass(null)`, then dispose it at the caller.
Pass input/output is linear light; OutputPass owns ACES/output transfer. Do not
add a second tone-map pass. No lens distortion, sensor noise, latency, droplets or
codec artifacts are added here, to avoid competing camera implementations.

Quality API accepts `performance` (existing name) / `low`, `medium`, `high`,
`ultra`, and `auto`. The existing menu is unchanged in this task; `?quality=low`
and `?quality=ultra` are aliases available at launch. Low keeps the existing
lighting/fog shader and has no extra draw calls or composer targets. Medium,
high and ultra use 384, 1024 and 2048 GPU instanced near-field particles.
Automatic quality first suppresses screen post-processing on a slow sample;
subsequent slow samples lower resolution. Camera passes are also suppressed in
low/automatic fallback, so T14b must account for this quality contract.

RGB extinction and scattering coefficients, particle dimensions/density and
caustic patterns are visualization assumptions, not measured water-type or
vehicle specifications. Sunlight travels from surface to object; lamp light
travels lamp-to-object; both return to the camera through wavelength-dependent
extinction. Distinct scatter and extinction coefficients are an approximation,
not an implementation claim of the research paper's calibrated image model.

Observation eligibility is still computed by projection, range and raycasts in
`observation_camera.js` and backend geometry. These modules never read pixels or
change target geometry. The existing visibility eligibility estimate is retained.

The underwater surface uses an analytic Snell window with moving normals. Reflection
is approximated by local water colour, without an extra scene reflection render.

Remaining T07 work before acceptance: surface-crossing
transition coordination with T14b and full app camera
capture/performance on an integrated GPU. Current screenshot fixtures freeze the
world and use shared Environment/material modules; they are not driving proof.

Silt particles use the authoritative silt state; near-surface wake bubbles use
propeller thrust and vehicle depth. Their lifetime/density is provisional.

High/ultra use a small procedural, dim underwater reflection cube. No external
asset or npm dependency is added; the existing three.js MIT license covers addons.

High/ultra also add millimetre-scale procedural surface-normal detail; no
collision meshes or observation target geometry changes.

Sun shafts are an optional shallow billboard scattering approximation; they
fade over depth and do not claim volumetric occlusion or measured water optics.
