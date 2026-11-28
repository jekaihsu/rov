# Input layer

Open controller settings with F9, the sidebar button, or controller Back + Start.
D-pad up/down moves focus; left/right adjusts sliders and selects options; primary
button activates, secondary returns. Activate a binding field, release the navigation control, then move an axis or
press a button to capture a binding, or enter `a0`, `-a1`, `b7`, `b7~` (digital
threshold), or `b7,b6` (positive minus negative). Reset restores defaults.

## Binding table and contexts

`bindings.js` is the only place where default keys and gamepad sources are declared. Each row names an
action, its context and its sources. Contexts stack from low to high priority: `flight`, `orbit` (orbit
camera owns the right stick), `tool` (surface paint enabled), `dialogue` (campaign radio waiting for
confirmation) and `menu` (settings, collection and main menu; exclusive). Inside one context an input
belongs to one action; the only shared form is a short press (`tap`) plus a long press (`hold`, 650 ms)
on one button. When contexts stack, the highest one that binds an input owns it, and a button claimed when
it went down stays claimed until released. `node --test simulator/tests/test_bindings.mjs` fails when two
actions in one context share an input. Feature modules call `input.registerActions({name: {run, enabled}})`
with a name that has a row in the table; a context above `flight` is active while one of its registered
actions reports `enabled()`. On-screen hints (engineering drawer, pilot guide, HUD help card) are rendered
from the same table.

Defaults (standard mapping): A photo, B record (hold), X depth hold, Y lock, View tap A/S/C mode, View
hold engineering drawer, Menu tap light, Menu hold pause menu, L3 camera view, R3 tap assist level, R3 hold flight profile, D-pad
peek cards (up mission, left systems, right map, down keys), LB/RB and LT/RT wheels, View + Menu settings.
Keyboard: F assist (F sprays instead while surface paint is on), G profile, B gimbal, `[` `]` camera
pitch, Tab drawer, Esc pause menu, 1–4 peek cards, Enter confirms dialogue. During dialogue A confirms and holding B skips
the tutorial; neither reaches photo or record.

Keyboard layouts (`keyboard_layout.js`, fidelity item `keyboardLayout`, preset-neutral): `console` (the `real`
default) is the table above, where keys stand in for the hand controller's sticks and their meaning follows the
operation mode exactly like the controller. `game` (the `assisted` and Steam default) binds the pilot axes instead:
W/S forward/back, A/D strafe, Space/C up/down, Q/E turn, ↑/↓ pitch, T lock; the input layer turns each axis into the
stick channel that drives it in the current operation mode (`OPERATION_AXES`, mirrored from `qysim/rc.py` and
checked by `test_bindings.mjs`), so the RC packet and its PWM meanings are unchanged. Keys are rebound per layout in
the controller dialog (鍵盤按鍵: click, press the new key, Esc cancels); choices are saved in `rov.input.v1` under
`keys[layout]`, and a key already used in the same context is refused (`keyCollisions`). Help tables name stick
channels by what they do (前進／後退), not by the stick.

Switch-layout pads confirm on the right and go back on the bottom when the menu pair is at its defaults.
The photo and record actions always follow the same physical positions in flight.

Menu defaults (launch menu, pause menu, settings): D-pad or arrow keys and the left stick move focus, A / Enter
confirms, B / Esc goes back, LB / RB or Q / E switch tabs, the right stick turns the hangar turntable. These rows can be rebound and are read by `../menu/navigator.js`; the same sources drive the deck checklist. The editor itself retains the standard D-pad,
confirm and back controls for recovery. Clear a conflicting assignment before reusing its source.
Version 3 of the binding map retains custom flight bindings and initializes newly editable actions from the table.
Reset restores both layouts and controller bindings without removing device calibration.

Assist level and flight profile belong to the fidelity profile (`../fidelity.js`); the `real` preset starts
at assist 0. Both RC fields are omitted until telemetry advertises an assist object. Selecting the drone
preset also selects UAV_USA channel interpretation; current selects ROV_USA. No PWM meaning changes.

Unknown controllers use standard positional indices and can be calibrated (`input/calibrate.js`). In the wizard
move the first four requested controls in the positive directions (right/down/right/down),
then press each requested standard button. Release between steps. Extra axes and
buttons may be assigned to any requested control; optional buttons may be skipped.
The profile is saved under `rov.input.v1` → `custom[pad.id]`. Calibrate again when
changing driver/browser: SDL indices vary across platforms, especially hat switches.
The compact database contains Linux records and Windows overrides for the supported controller families. `devices.js` decodes their hat
descriptors (`h0.1` up, `.2` right, `.4` down, `.8` left: the stepped axis 9 that
Chromium reports on Windows/macOS, or the x/y axis pair after the plain axes on Linux)
and scales a bare full-range axis on a trigger slot to 0..1; calibrate a custom profile
when the live display still differs from the device. PlayStation pads (DualShock 4,
DualSense) that arrive without the standard mapping skip the database and use the raw
layouts in `playstation.js`, chosen from the id format; see
`docs/reference/playstation-controller.md`. Menu prompts name the shoulders and menu
buttons per family (`glyphs.js` `padNames`, e.g. L1/R1/Options). Compatibility notes: `research_notes/手把/compatibility.md`. Steam Input
partner setup: `docs/steam/steam-input.md`.

Browser preferences use `rov.input.v1`; desktop mirrors them in the existing
userData/preferences.json mechanism and restores them across dynamic server ports.
No settings are sent to the physics engine except optional assist/profile fields.

Run `node --test simulator/tests/*.mjs` and `python simulator/tools/browser_input_smoke.py`
from the repository root. The latter expects the implementation on :8080 and writes
1600×900 evidence under simulator/output/t02. Pass `--before-url URL` only when a
comparison server is available; it is not required for input regression checks. Hardware feel and vibration require physical testing.

## RC link and heartbeat

Controls are sampled on a 33 ms page timer (`createRcPump` in `rc_link.js`), never from the render loop. A
packet is forwarded when it changes and otherwise every 100 ms. The simulator socket itself lives in a worker
(`rc_worker.js`): slow software rendering keeps the page thread busy for longer than the server's 0.6 s input
failsafe, so the worker repeats the last forwarded packet whenever the wire has been silent for 150 ms. It does
so for at most 2 s after the page last spoke (`RC_TIMING.holdMs`); a page that stays frozen beyond that goes
silent and the server failsafe locks the vehicle as before. Packets sent outside the pump (hidden tab, collection
panel) cancel the repeat immediately, as does a hidden document. The worker assigns every RC `seq`, and hands
state snapshots to the page one at a time, keeping only the newest while the page is busy. Pages without module
workers, or whose `WebSocket` constructor has been replaced (test instrumentation), keep the socket on the page.
All timing rules are pure functions in `rc_scheduler.js`, covered by `simulator/tests/test_rc_scheduler.mjs`;
`simulator/tools/browser_slow_render_smoke.py` checks the behaviour in a real browser with a stalled page thread.
