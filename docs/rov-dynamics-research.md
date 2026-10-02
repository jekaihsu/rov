# ROV dynamics review — 2026-10-02

This is an implementation audit and a source record, not a certification of a Falcon or BlueROV2 digital twin. The catalogue explicitly marks all reconstructions and their hydrodynamics as estimated. No manufacturer calibration data has been supplied for this simulator's specific payload, tether or trim.

## Sources checked

- [Fossen: Marine Craft Model](https://www.fossen.biz/html/marineCraftModel.html): rigid-body and added-mass terms must be handled consistently; current enters through water-relative velocity. Its general equation is `M_RB νdot + C_RB(ν)ν + M_A νr_dot + C_A(νr)νr + D(νr)νr + g = τ`. With no external work, the Coriolis terms do no work. The current derivative must include coordinate rotation even when the inertial current is constant.
- [von Benzon et al., 2022, JMSE 10(12),1898](https://doi.org/10.3390/jmse10121898): experimentally checked BlueROV2 Heavy benchmark, including thruster dynamics and tether. Appendix A separates measured, CAD and estimated quantities. Representative values: mass 13.5 kg; rigid-body inertia `(0.26,0.23,0.37)` kg m²; translational added masses `(6.36,7.12,18.68)` kg; rotational added inertias `(0.189,0.135,0.222)` kg m²; CB `(0,0,-0.01)` m; translational linear damping `(13.7,0,33)` and quadratic damping `(141,217,190)` in corresponding SI units. These values concern that paper's vehicle and configuration. They are a candidate benchmark profile, not evidence for Falcon coefficients. [Publisher PDF](https://mdpi-res.com/d_attachment/jmse/jmse-10-01898/article_deploy/jmse-10-01898-with-cover.pdf?version=1701308762), [authors' simulator](https://github.com/ROV-Simulator/ROV-Simulator).
- [Blue Robotics T200 product data](https://bluerobotics.com/store/thrusters/t100-t200-thrusters/t200-thruster-r2-rp/): at 16 V, full forward/reverse thrust is 5.25/4.1 kgf. The two directions are unequal. [Official thruster guide](https://bluerobotics.com/learn/thruster-usage-guide/) gives the neutral/deadband and PWM ranges (forward above 1525 µs, reverse below 1475 µs, endpoints 1900/1100 µs).
- [Saab Seaeye Falcon](https://www.saabseaeye.com/solutions/underwater-vehicles/falcon): five thrusters, 60 kg standard vehicle, thrust forward/lateral/vertical 42/25/13 kgf, speed above 3 knots; auto depth and auto heading; optional DVL for station keeping and altimeter for auto altitude. The optional five-function arm skid is rated for 10 kg at full reach. The page does not provide complete added-mass, drag, motor transfer-function or trim data for the skid configuration.

## Audit of this repository

`simulator/qysim/physics.py` already uses a six-degree-of-freedom state, quaternion attitude, water-relative drag, buoyancy offset, thruster allocation and first-order motor response. Position integrates ground velocity exactly once; adding current again would be incorrect. `vehicles.py` correctly limits Falcon's independently commanded axes to surge/sway/heave/yaw while retaining passive roll/pitch dynamics. BlueROV2 Heavy has eight motors and six independent actuation axes. Neither topology alone validates the coefficients.

Before this change, inertial translation was `-M * (ω × v)` with elementwise diagonal `M`. For anisotropic added mass, moving `M` outside the cross product is not equivalent to momentum transport. The paired translational-added-mass moment was missing. A direct local reproduction for Heavy with `v=(1,.6,.2)`, `ω=(.3,.4,.5)` produced −0.528 W of spurious inertial power, independent of drag.

The catalogue's Heavy values remain estimates: combined inertia `(0.7,0.9,1.0)`, added mass `(7,10,13)`, CB height 0.055 m, symmetric 50 N motors. Its automatically derived quadratic translational damping is approximately `(58.19,131.42,297.5)`. This differs from the benchmark above, but differences alone do not justify replacing values without matching payload/geometry/voltage.

Falcon's current allocation gives approximately `(378.46,224.43,110)` N axis thrust. These correspond to about `(38.58,22.88,11.21)` kgf, below the published standard-vehicle figures. Current 110 N uniform motor authority, CG, GM, damping and motor time constants are not measured. In particular, a manipulator skid changes drag, mass, CG and trim. Do not silently scale the entire dynamics to a brochure maximum.

## Implemented correction

The inertial structure and the underactuated allocation objective were corrected; thrust limits, damping targets, motor time constants and buoyancy were not tuned. The allocator now minimizes error only in independently controlled axes. For Falcon, it preserves the actual roll/pitch moments induced by the below-CG horizontal thrusters instead of sacrificing requested horizontal force in an impossible attempt to cancel those moments. The full physical allocation matrix still generates all six wrench components.

For diagonal translational added mass `A`, combined rotational inertia `I`, ground velocity `v`, relative velocity `vr`, and angular velocity `ω`, the negative Coriolis wrench is now:

```text
F_C = -m (ω × v) - ω × (A vr)
M_C = -ω × (I ω) - vr × (A vr)
```

The translational equation also includes `A vc_dot`. With a locally frozen inertial current, `vc_dot = -ω × vc`. Angular relative velocity equals body angular velocity under the irrotational-current approximation. With still water, `v·F_C + ω·M_C = 0`. Scalar rigid-body mass has no translational coupling moment because `v × (m v) = 0`.

The world currently supplies a sampled current vector, not its material derivative. Current-field acceleration and spatial gradients are therefore still omitted. This is a documented approximation; the change does not claim full rotational-flow hydrodynamics. Euler time stepping also does not exactly conserve energy at finite step size, even with a zero-work continuous Coriolis wrench.

## Verification

`python -m unittest tests.test_inertial_dynamics tests.test_vehicles tests.test_core.TestPhysics tests.test_core.TestControl`

20 tests passed in 5.100 seconds at delivery. Five new checks cover 100 random anisotropic zero-work cases, the Newton–Euler rigid-body limit, the paired added-mass moment, a body moving with uniform current, and Falcon's attainable force with real passive moments retained.

The old open-loop X1 top-speed test failed after restoring the coupling (4.285 knots instead of the fitted 4.5 knots). It assumed independent translational axes despite buoyancy and attitude motion. It was replaced with an explicitly named one-axis drag-calibration force-balance check. That check is **not** experimental speed validation. Vehicle finite-state, quaternion, self-righting, drift and controller regressions remain. No claim is made that the revised whole vehicle exactly reproduces the brochure speed.

## Next calibration work, in priority order

1. Separate operator modes (manual thrust, attitude/heading stabilization, depth hold) and model capability limits. Releasing a manual stick should not silently imply position hold. Treat camera tilt separately from pitching a Falcon hull. Controller work is owned by the other agent.
2. Add a documented BlueROV2 benchmark parameter profile rather than overwrite all models. Keep rigid-body inertia and added inertia distinct, and support explicit damping coefficients instead of only deriving them from desired maximum speeds. Compare acceleration, coast-down and free-decay traces, not just terminal speed.
3. Fit T200 PWM-to-force curves at a specified voltage with forward/reverse asymmetry, deadband and lag. Match physical motor direction before introducing asymmetry: currently all horizontal positive axes are mathematically reoriented. Simply weakening every negative command would invent a vehicle-level directional bias. A normalized *force demand* should be converted to PWM by an inverse curve; it is not necessarily raw throttle.
4. Obtain real Falcon skid mass, inertia, CB/CG, thruster curve and tether data. Current arm reaction adds external wrench but does not fully update articulated inertia and buoyancy as the arm moves.
5. Measure tether payout, current, payload and battery/voltage during sea or tank trials. Fit one-axis step/coast-down tests and cross-axis turning tests separately. Validate held depth/heading and station-keeping drift with sensor noise and latency. Public data cannot establish these particular vehicle parameters.

No large datasets or binaries were downloaded for this review. Reference websites were read on 2026-10-02.
