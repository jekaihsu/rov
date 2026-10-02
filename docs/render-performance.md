# Rendering and three-player performance

Changes preserve physics resolution and gameplay controls:

- Peer cable geometry updates only when a new snapshot arrives. Hull interpolation
  and rotor motion still update each display frame. A two-peer browser microbenchmark
  reduced 120 unchanged display frames from 240 cable rebuilds to 2. New node data
  still changes geometry. This measures that component, not whole-game FPS.
- Peer rotor updates reuse a quaternion instead of allocating one per rotor/frame.
- Wrap warning rings are reused while winding changes and disposed on world rebuild;
  previously each state discarded GPU geometry without disposing it.
- Up to 300 paint marks share one vertex-color mesh and one material. Geometry
  merges occur only after changes, retaining mark order and individual removal.
  Decal creation yields between projections after a 6 ms budget, with a 24-mark
  maximum per update. A single complex projection may exceed that budget.
- Auto render quality targets 60 FPS, lowers pixel ratio after sustained <50 FPS,
  and restores it slowly after sustained >58 FPS. Hardware hints select the initial
  ratio and bounds: integrated GPUs start at .85 and range .6–.9; entry GeForce MX
  starts at .85 and ranges .6–1; other discrete/unknown GPUs start at 1; software
  rendering starts at .6 and ranges .5–.75. A pixel budget also limits large
  viewports. These are conservative heuristics, not GPU rankings. It ignores
  hidden tabs, initial loading and recording.
- Fixed Performance, Standard and High modes remain available from the main menu.
  Existing saved preferences are respected. Standard is capped at one render pixel
  per CSS pixel; High permits up to two on high-DPI displays.
- FPS display uses the real frame interval, independently of the clamped animation
  timestep. Auto resolution cannot fix CPU bottlenecks or guarantee a frame rate.

Validation: `python simulator/tools/browser_fleet_perf.py` verifies packet gating,
geometry changes and adaptive downscale/recovery, recording suspension and fixed
quality preservation. Evidence is under `simulator/output/fleet-performance`.
`browser_menu_smoke.py` covers menu selection, scene/model/control application and
return to menu. Browser automation uses software rendering, so timings are not
a claim about the user's graphics card.

Backend profiling and its limits are in [physics-performance.md](physics-performance.md).

Local hardware inspection found i5-8250U, approximately 8 GB system RAM, Intel
UHD 620 and NVIDIA MX110. The browser validation's WebGL renderer reported UHD
620; the installed second GPU does not prove it is active. WebGL requests the
high-performance GPU as a hint, while the OS/browser still decides the device.
The UI reports the active WebGL classification; detection remains local.
