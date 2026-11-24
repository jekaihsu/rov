ROV-01 MuJoCo cable inspection

Run from this folder: python3 sim.py
Rebuild MJCF from original geometry: python3 build_model.py
Dependencies: mujoco==3.17.0, numpy, scipy, Pillow, imageio, imageio-ffmpeg.
imageio and imageio-ffmpeg are installed locally in .deps; no system packages changed.
No assets are downloaded; all geometry is original MJCF primitives.

Coordinate conventions
- Original vehicles.py positions and force directions are copied without changes.
- Source body frame is FRD (+x forward, +y right, +z down).
- Initial quaternion (0,1,0,0) rotates FRD into the z-up world.
- Sites use identity local rotation; actuator gear contains the exact source axis.
- Source T1-T4 include -0.36 z components and are not pure horizontal 45-degree vectors.
- Commands and CSV values are signed actuator force coefficients, approximately N
  (source axes are preserved even though their lengths are not exactly unity).

Physics and mission
- 12 kg rigid body, diagonal inertia (0.38,0.65,0.72) kg m^2.
- Buoyancy is weight + 2 N at body position (0,0,-0.085) m.
- Buoyancy uses xfrc_applied with the equivalent COM moment r cross F.
- Relative-fluid linear and quadratic drag in body axes; angular drag included.
- Umbilical spatial tendon connects fixed world (9,0,10) to body (-0.20,0,-0.22).
  It has 11 m slack length, 3 N/m stiffness and 1.5 N s/m damping.
  This is a lumped elastic straight tether: distributed sag/drag are not modeled.
- Cable radius 0.025 m, center z=0.035 m. Target CG z=1.06 m, exactly
  1 m above cable top, with y=0. Target speed ramps to 0.3 m/s over 3 s.
- Current world +y = 0.75 knots = 0.3858333333 m/s.
- Translation PID and attitude PID plus drag/buoyancy feedforward; full-rank
  6x6 wrench allocation, +/-45 N clipping, 80 ms motor response.
- Physics 200 Hz, CSV and video 20 Hz. Metrics use every physics sample,
  including initial transients; positive depth_err means the CG is too deep.
- EGL is default; renderer creation failure retries OSMesa in a fresh process.

Outputs: out/rov01_cable.mp4, out/shot_10.png, out/shot_30.png,
out/shot_50.png, out/thrust.csv, out/summary.json.
Hydrodynamic and tether coefficients are engineering estimates, not a validated
physical vehicle identification. Frame colors are only #06B6D4 and #1E293B;
lighting naturally produces shaded pixel values.
