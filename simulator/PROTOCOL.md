# qysim protocols

## Multiplayer protocol v2

The host owns all physics. A server supports up to eight named rooms, each with
three pilot seats. Each seat controls exactly one vehicle; a client-supplied
`vehicle_id` never grants control over another vehicle. The SDK TCP service stays
on loopback and controls the first vehicle in the `training` room.

After opening the viewer WebSocket, send:

```json
{"type":"join","room_id":"training","name":"Pilot","model_id":"x1","resume_token":null}
```

Room codes contain 1–32 ASCII letters, digits, underscores or hyphens. Missing
rooms are created. Supported model IDs are published in `world.vehicle_catalogue`.
A successful join replies:

```json
{"type":"session","protocol":2,"room_id":"training","player_id":"opaque-id","vehicle_id":"v1","resume_token":"private-token","generation":1,"is_host":true,"capacity":3}
```

Keep the resume token private and resend it to recover the same seat after a
disconnect. Disconnected seats remain reserved for 30 seconds. A replacement
connection invalidates the old connection's commands. Rejoining centres and locks
the controls; unlock explicitly after receiving the new session. The first pilot
is host; when they disconnect, host privileges pass to the next connected pilot.
The current host is always available as `state.room.host_id`.

Every RC packet carries a monotonically increasing integer `seq`, starting at
zero after each successful session handshake. RC heartbeat frequency should be
at least 5 Hz (the usual input stream remains 30 Hz). No valid input for 0.6 s
centres and locks that vehicle and cancels navigation. Connected local USB input
uses its existing 0.6 s watchdog instead.
After a failsafe lock, `state.input_latched` is true and `control_generation`
changes. Resynchronize controls and send a locked RC packet (`rc_lock:1`) to
acknowledge; only a subsequent explicit unlock is accepted. A delayed unlocked
heartbeat cannot automatically restart the vehicle.

```json
{"type":"rc","seq":0,"rc":{"right_ud":1600,"rc_lock":0}}
{"type":"model","model_id":"falcon"}
{"type":"operation","action":"arm","joints":[0,15,0,0],"grip":1}
```

Changing a model redeploys only the requesting pilot's vehicle in a locked state.
`operation` requests are handled by the vehicle's operations controller and reply
with `{"type":"operation_result","ok":true,"action":"..."}` or `ok:false` and a
`message`. Scenario changes, reset, pause and current overrides require the host.
Other vehicle commands from §2 apply only to the sender's seat. Errors are
`{"type":"error","code":"host_only|join_required|stale_input|session_replaced|invalid_command|instructor_override|controller_only","message":"..."}`.
`instructor_override` rejects a shared-scene command while an instructor supervises the room
(see the instructor section); `controller_only` rejects any non-RC message from an attached
controller bridge connection.
Clients which do not join can observe the default room but cannot issue commands.

To use a USB controller on a remote pilot's computer, download a pairing JSON
with `url`, `room_id` and `resume_token` from the pilot interface, then run
`python -m qysim.qirc_bridge --config pairing.json`. This attaches to the browser's
seat via `{"type":"attach_controller","room_id":"training","resume_token":"..."}`;
the reply is `controller_session`. Keep the browser open. The bridge uses its own
RC sequence, cannot issue scenario or operations commands, and has a 0.6 s input
watchdog. The browser cannot overwrite bridge axes. Pairing files contain private
seat credentials and should not be shared. The optional original controller
requires locally installed Android Platform Tools and USB authorization.

Successful scenario/reset/pause/current/model commands reply with
`{"type":"command_result","action":"reset","ok":true}`.

Each `state` retains the original top-level fields for the receiving pilot and adds:

```text
vehicle_id       runtime ID, v1–v3 (room-local)
model_id         vehicle design ID
vehicle          selected vehicle definition and geometry offsets
operations       arm state, inspection state and shared work objects
environment      authoritative fish-school states and localized silt clouds
tick             room physics tick
vehicles[]       every vehicle's state, plus id and owner_id
room             {id, host_id, capacity, players:[{id, vehicle_id, name, connected}]}
```

`world.vehicle` describes the receiver's model, `world.vehicle_catalogue` lists
available definitions, and `world` also carries authoritative terrain/habitat and
seed information. Render other pilots from `vehicles`, interpolate using server
time, and route the local camera/HUD to the session's `vehicle_id`. Sim time,
currents, ecology and free work objects advance once per room tick. Vehicle state,
tether, controller, camera, navigation and damage remain independent. Intervehicle
hull contacts currently use a simplified collision proxy; crossed tethers do not
simulate intervehicle knotting.

For LAN hosting use `--host 0.0.0.0`; the HTTP and viewer WebSocket listeners use
that interface, while SDK RPC remains on `127.0.0.1`. Internet deployments need
an HTTPS/WSS reverse proxy; room codes are grouping identifiers, not passwords.

Frames and units used everywhere:

* World: **NED** metres — x north, y east, z down (depth). Origin = scenario reference point on the sea surface.
* Body: **FRD** — x forward, y starboard, z down. Quaternion `q = [w, x, y, z]` rotates body → world.
* Angles on the wire are degrees unless a field name says otherwise. Speeds m/s unless suffixed `_kn`.
* To draw in three.js (Y up): `three = (east, -down, -north)` i.e. `(y, -z, -x)` of NED works with a
  right-handed scene where the camera looks along -Z = north. Any consistent mapping is fine.

## 1. SDK RPC (mock `qysea` package ⇄ server)

TCP, default `127.0.0.1:9760` (env `QYSIM_HOST`, `QYSIM_RPC_PORT`). One JSON object per line, both ways.

Request
```json
{"id": 7, "type": "sdk", "cls": "QYRovControllerManage", "method": "set_left_joystick_up_down", "args": [1600], "kwargs": {}}
```
Response
```json
{"id": 7, "ok": true, "result": <exactly what the real SDK method returns>}
{"id": 7, "ok": false, "error": "TypeError: ..."}
```

Other request types:

| type | extra fields | result |
|---|---|---|
| `ping` | – | `"pong"` |
| `state` | – | viewer state object (§3) |
| `camera_view` | optional `file_path` | `{pos, q, pose, visibility_m, silt, led, seabed_depth, obstacles, tether}` — everything needed to render a synthetic camera frame on the client. `pose` is the stored pose of a photo file (for `download_file`). |

`cls` is the real SDK class name (e.g. `QYRovRealTimeStatusManage`, `QyRovHighFreqRealTimeStatusManage`,
`QYRovNavigationManage`, `QYRovVCCMManage`, `QYRovParameterManage`, `QYRovCalibrationManage`,
`QYRovAddOnsManage`, `QYRovCheckManage`, `QYRovControllerManage`, `QYSDKInfoManage`, `QyCameraInitManage`,
`QYCameraWorkModeManage`, `QYCameraParameterManage`, `QYCameraActionManage`, `QYCameraStorageFileManage`,
`QYCameraSystemManage`). Unknown setters are accepted and remembered; unknown getters echo them.

Client-side responsibilities (things the server does not do):

* connection flags per object: `get_rov_status()` before `connect_to_rov()` →
  `{'status': 'error', 'status_code': '', 'text': 'Please connect ROV first', ...}` (real SDK text).
* `QyRovHighFreqRealTimeStatusManage.get_rov_status()` alternates `10hz`/`50hz` packets
  (send `"args": ["10hz"]` or `["50hz"]`).
* `QYCameraMediaStreamManage` (`capture_video`, `get_frame`, `get_w_h`, `show_video`, `close_video`):
  render frames locally from `camera_view`. `get_frame()` returns `(True, ndarray BGR uint8)`.
* `QYCameraStorageFileManage.download_file(camera_flag, file_path, dir_path)`: render the photo from the
  file's stored pose and write it as a JPEG named like the file into `dir_path`; `get_download_status`
  then returns text containing `successfully`.
* Connection failure to the server → return the SDK's own error shape with text `ConnectTimeout`.

## 2. Viewer WebSocket (browser ⇄ server)

`ws://127.0.0.1:8765`. The server sends JSON text frames:

* `{"type": "world", ...}` on connect and whenever the scenario or current changes (§4)
* `{"type": "state", ...}` ~30 Hz (§3)

The browser sends:

| message | effect |
|---|---|
| `{"type":"rc","rc":{"left_ud":1500,...,"rc_lock":0,"keep_depth":1,"left_switch":1,"right_switch":0,"record":0,"photo":0}}` | physical RC state (any subset of keys). Channels are PWM 1000–2000 (1500 centre, `>1500` = up/right). Buttons are levels: `rc_lock` 1=locked, `record`/`photo` 1=pressed. `left_switch` 0/1/2 = A/S/C, `right_switch` 0/1/2 = LED. Send at ~30 Hz while input changes and at least every 0.5 s. |
| `{"type":"scenario","key":"random","seed":123}` | load a scenario (`seed` optional; optional `tide_start` selects the time of tide when the scenario has a tide, see "Ocean current model") |
| `{"type":"reset"}` | restart the current scenario |
| `{"type":"pause","value":true}` | pause / resume |
| `{"type":"payout","metres":5}` | pay out (+) / recover (−) tether |
| `{"type":"auto_payout","value":false}` | toggle automatic payout |
| `{"type":"operation_mode","value":"ROV_JPN"}` | ROV_USA/JPN/CHN, UAV_USA/JPN/CHN |
| `{"type":"current","surface_kn":2,"surface_dir":90,"mid_kn":1.5,"mid_dir":100,"bottom_kn":0.5,"bottom_dir":110,"turbulence":0.2}` | override current (directions = where water flows TO, degrees from north). Speeds are clamped to 0–5 kn, `turbulence` (streamwise turbulence intensity σu/U) to 0–0.3 |
| `{"type":"shaping","throttle_curvature":60,"throttle_limit":100,"rotate_curvature":60,"rotate_limit":100}` | stick curves |
| `{"type":"remote_release"}` | force SDK remote control OFF (give control back to the physical RC) |

Input-layer RC clients also send optional `assist` (0 manual, 1 velocity, 2 position assist) and
`profile` (`cine`, `normal`, `sport`). Omitted values retain the legacy manual/normal semantics.
The viewer takes both from its fidelity profile (`viewer/fidelity.js`): the `real` preset, which is
the default for internal training builds and the acceptance baseline, sends `assist:0`
(manual, stick is thrust) with `profile:"normal"`; only the optional `assisted` preset defaults to
`assist:2`. Clients MUST omit both fields unless the received `state.assist` is an object.
A host with flight assistance never rejects a packet because of these two fields: an `assist` that
is not 0, 1 or 2, or a `profile` that is not one of the three strings (including non-string values),
falls back to `0` / `"normal"` and the rest of the packet is applied. All other RC values must
still be finite numbers. Legacy hosts without `state.assist` reject string-valued RC fields,
including `profile`; the input layer does not modify physical PWM channel meanings.

Stick meaning depends on `operation_mode` (see `qysim/rc.py`); the viewer only sends raw channels.

## 3. State object (`type: "state"`)

```text
t                sim seconds            paused        bool
pos [n,e,d]      NED m                  q [w,x,y,z]   body→world
euler [roll,pitch,yaw_0_360] deg        vel [u,v,w]   body m/s
speed_kn         speed through water
thrust [6]       -1..1 per thruster (order = world.thrusters)
health [6]       0..1 thruster health (impact damage)
rc {...}         active RC (SDK when remote_control) — same keys as the rc message, plus the
                 requested `assist` (0/1/2) and `profile` (optional additions; `state.assist`
                 reports what the controller actually applies)
remote_control   bool (SDK has control; physical RC ignored)
operation_mode   str      ctrl_mode "A"/"S"/"C"   locked bool   keep_depth bool   depth_hold m|null
battery %        recording bool   photos int
current_here [n,e,d] m/s at the ROV     current_kn
tether {nodes [[n,e,d]...], length, max_length, tension_rov, tension_spool, tension_max (N),
        warn bool, broken bool, contact_nodes, snagged_on [names], wraps {obstacle: turns}, auto_payout}
events [{t, obstacle, speed, severity: touch|hard|severe, where}]   (last 12 impacts)
damage [{t, thruster, health}]
silt 0..1 (seabed silt cloud; reduce visibility)
nav {mode: IDLE|H_NAVI|V_NAVI|VCCM, nav_status, vccm, route [[n,e,d]...], route_i, target [n,e,d]|null}
score {score 0..100, elapsed, failed "", finished, current_index,
       objectives [{kind, label, point [n,e,d], radius, hold_s, done, progress 0..1, target}],
       penalties [{t, reason, points}], penalty_total}
log [{t, kind, text}]   (last 8 lines, Traditional Chinese)
```

## 4. World object (`type: "world"`)

```text
seabed_depth m
obstacles [ {type:"cylinder", name, p0 [n,e,d], p1 [n,e,d], radius, kind: pile|monopile|jacket_leg|brace|mast}
          | {type:"box", name, center [n,e,d], half [hx,hy,hz], yaw_deg, kind: hull|wreck}      (hx along heading yaw_deg)
          | {type:"wall", name, point [n,e,d], normal_deg, width, top, kind: wall} ]              (vertical face; extends from `top` down to the seabed)
current {surface_kn, surface_dir, mid_kn, mid_dir, bottom_kn, bottom_dir, turbulence, tide?}
                      (turbulence = streamwise intensity σu/U; optional tide object only when the scenario
                      has one; see "Ocean current model" below)
scenario {key, name, brief, seed, visibility_m, time_limit_s, tether_length}
spool [n,e,d]         tether spool / deployment point on the surface
start_pos [n,e,d]     ROV start position (the viewer's deployment intro ends here)
catalogue [{key, name, brief}]  scenarios for a picker (includes "random")
objectives [...]      same shape as in score.objectives
thrusters [{name, pos [x,y,z] body FRD, axis [x,y,z]}]
```

### Optional flight assistance

RC packets may include `assist` (0 manual, 1 ground velocity, 2 ground position
hold) and `profile` (`cine`, `normal`, `sport`). Each packet defaults to 0 and
`normal` when omitted; unsupported values (wrong type or out of range) use those defaults
without rejecting the packet. Internal USB samples
and attached controller bridge packets merge axes into the selected assistance
settings instead of reverting omitted metadata. Complete browser RC packets keep
the documented manual defaults. SDK remote control
and active navigation bypass assistance. Depth keeping retains vertical priority.
A/C interpret velocity in heading-aligned horizontal coordinates; S uses body axes.
All translation sticks must be within 0.02 and ground speed below 0.05 m/s to
capture a position. Any translation stick outside that threshold releases it.
The simulator currently assumes bottom lock only at 0.1–100 m bottom altitude
with finite ground velocity. Outside this window assistance falls back to manual,
clears history, and reacquires only when the simulated lock is valid again.
This common simulated window is provisional: it is not a calibrated model of
any vehicle's sensor, bottom material, DVL drift, or hardware loss-of-lock policy.
Lock, failsafe, disconnect and remote takeover clear assistance history.

`state.assist` contains `level`, `profile`, `holding`, `limited`, `speed_limit`
([surge, sway, heave], m/s) and `yaw_rate_limit` (degrees/s). `limited` reports
requested motor saturation including coupled translation/attitude demands.
It cannot guarantee position holding in currents exceeding available thrust.
Translation force demand is capped at the same per-axis authority as manual full
stick; assistance never increases motor limits. Integral and reference histories
rotate with the control frame so their world direction remains consistent.
`profile` reports the requested valid profile even in manual/locked mode.
Manual thrust control remains the default, on the host and in the viewer's `real` fidelity
preset, and is compared byte-for-byte against its frozen pre-assistance implementation. Velocity and position assistance are
optional simulator features, not claims about real vehicle defaults.

Profile parameters scale with vehicle specifications rather than a model ID:

| Profile | Speed / nominal axis vmax | Acceleration / (authority / effective mass) | Jerk / acceleration (s⁻¹) | Yaw / nominal wmax | Stick exponent |
|---|---:|---:|---:|---:|---:|
| cine | 0.30 | 0.10 | 12 | 0.30 | 2.0 |
| normal | 0.52 | 0.35 | 20 | 0.50 | 1.5 |
| sport | 0.70 | 0.90 | 30 | 0.75 | 1.0 |

Yaw acceleration is bounded to the profile yaw limit per second. Existing RC
curvature/limits apply before the profile exponent. The S-curve reference integrates
bounded jerk and acceleration; a velocity PI with nominal still-water drag feedforward
produces force. Integration during velocity tracking waits for settling to avoid
learning command transients; position holding may integrate persistent current error.
Both integrators are bounded and frozen when motor allocation saturates.

Still-water acceptance bounds (optional assistance, not hardware specifications):
cine reaches 90% forward speed and brakes below 0.05 m/s within 2.0 s;
normal within 1.2 s for each, at most 0.6 m braking, at most 5% overshoot and
less than 3 cm reverse travel; sport reaches 90% within 0.9 s and brakes within
1.0 s. Cine is slower than normal, which is slower than sport. These bounds do
not guarantee performance under contact, tether loading or arbitrary attitude.
All vehicle parameters, especially unmeasured model-specific values, remain
provisional; see `docs/reference/real-rov-research.md`.

## Optional campaign layer

Rooms may publish `state.campaign`: `chapter`, `index`, `node`, `status`,
`objective`, `dialogue` (bounded radio history), `completed`, `rewards`, `results`,
`checkpoint`, `unlocks` (earned vehicle/sticker IDs), `next_story`, and `chapters`. Existing clients can ignore this entire field.
Each `chapters` entry carries `id`, `title`, `requires`, `placeholder`, `outline`, `category`
(`story` or `incident`) and `order`. The list is sorted by category (`story` first) and then by `order`.
`next_story` is the id of the first playable, unfinished `story` chapter (or `null`): a client that
auto-starts the campaign must use only `story` chapters. `incident` chapters are standalone drills that
start only through an explicit `campaign_start` with their `chapter` id.
The default is idle; existing mission modes and SDK semantics are unchanged.

Host-only operation actions (reply: `operation_result` with `ok` and `action`):

* `campaign_start`: optional `chapter` (default `prologue`), `course` (default false), `resume` (default false; starts at the saved checkpoint in a freshly loaded scene).
  Loads the chapter scene and the existing mission engine; unavailable/locked chapters fail.
* `campaign_advance`: acknowledges the current dialogue only. Cannot bypass a condition.
* `campaign_skip`: ends the run; skipping the prologue unlocks the first assignment without a rating/reward.
* `campaign_restore`: optional `save` containing local `completed`, `rewards`, `results`, `checkpoint`.
  Accepted only outside an active run. This is local training progress, not trusted competitive entitlement.

Only the starting host's vehicle satisfies tutorial conditions; mission objectives use the
existing shared mission engine. All pilots receive the same narrative state. Seat reconnects
retain the room instance. `course:true` runs the same script without dialogue pauses.
A viewer stores local progress in its existing `rov.*` preferences and exports results as JSON.
Campaign files reserve nullable `voice` on dialogue nodes for later audio assets.

## Optional instructor preview (T17, draft)

Internal installations may set `QYSIM_INSTRUCTOR_CODE` in the server environment.
Unset/empty disables the instructor feature entirely: every `instructor_join` is refused
(`invalid_command`, "instructor authentication failed"), including one with an empty or
missing code. It does not turn authentication off. Never put the code in URLs, source files,
reports or logs. Use WSS on untrusted networks. Open
`/instructor/instructor.html`; an optional `?ws_port=8792` selects a nondefault WS port.
Steam backend packaging excludes the instructor directory.

An instructor sends `{"type":"instructor_join","room_id":"training","code":"<private>"}`.
The room must already exist. Successful authentication replies
`{"type":"instructor_session","room_id":"training"}` and streams the existing
fleet state without reserving a player or vehicle. No additional state fields are
required. Credentials are not echoed. A pilot connection cannot become an instructor.
An authenticated instructor connection accepts only `type:"instructor"` messages:

* `action:"inject"`, `kind:"thruster"|"battery"|"current"|"visibility"|"freeze"`,
  optional `vehicle_id:"v1"`, `strength:0..1` (default 1), `duration` (0 < seconds <= 3600,
  default 10), `index` (thruster index, default 0).
  Thruster strength reduces existing health; battery strength reduces existing charge.
  Current and visibility affect the **whole room** through existing current/scene parameters.
  Current strength maps to a 0..4 kn **surface** speed: the existing layer profile is multiplied (its
  shape, shear and bed layer are kept; still water ramps in a 1 : 0.8 : 0.4 profile) and the change
  follows a raised-cosine ramp. Optional `ramp_s` (30..120 s, default 60) sets the ramp time and
  optional `rotate_deg` (-180..180, default 0) turns all layers over the ramp like a turning tide.
  On expiry or cancel the profile ramps back over the same time.
  Visibility retains at least 0.1 m. Other overrides restore saved values on expiry.
  Overlapping overrides of the same kind/scope are rejected.
  Optional `cancel_start` (finite simulation timestamp) instead restores and ends the active
  injection matching `kind`, `vehicle_id` and its exact `start`; other overrides are untouched.
  A stale/nonmatching timestamp is rejected. Omit it to retain normal injection behavior.
  Freeze uses the individual simulator pause while the room override clock keeps advancing.
* `action:"pause", value:true|false`; `action:"reset"`; `action:"scenario", key:"..."`.
  Reset archives assessment evidence and clears overrides.
* `action:"return", vehicle_id:"v1"` redeploys the model locked at its normal start.
* `action:"reference"`, optional `vehicle_id`, `phase` (`descent`, `transit`, `hover`,
  `orbit`, `dock`), `reference` containing optional NED `target`, `path_start`,
  `heading` degrees, `depth`, `distance`, `speed_min`, `speed_max` in SI units.
  Optional `limits` supplies both `still` and `current`, each with positive tolerances
  `path`, `heading`, `depth`, `hover`, `distance`, `speed`.
* `action:"report", vehicle_id:"v1"` returns `type:"training_report"`, `report` and
  prior `archive` reports. Other successes reply `type:"instructor_result", action, ok:true`.

While a supervisor is connected or an override is active, pilot commands that change the
shared scene are rejected (`instructor_override`): `scenario`, `reset`, `pause`, `current`,
`model`, and the operations `campaign_start` (it reloads the scene) and `mission_mode`.
Everything a pilot does to their own vehicle keeps working: RC, `payout`, `auto_payout`,
`operation_mode`, `shaping`, `remote_release` and all other operations (arm, photos,
`campaign_advance`, `mission_photo`, ...). The instructor's credentials never grant an SDK seat.
Existing clients omitting this entire optional extension retain their current behavior.

Evidence is sampled at 1 Hz of unpaused simulation time, only while a supervisor is connected
or an override is active; an unsupervised room records nothing. Each vehicle keeps its most
recent 3600 samples and the archive keeps the newest 16 reports. Reports retain a five-phase
matrix, split by current/no-current samples, with RMS, min/max, outside-tolerance
fraction and provisional green/yellow/red assessment, plus command variance,
zero crossings, reversals, collisions, tension, wraps, completion and trajectory.
Reports optionally include `supervision: {phase, reference, active, world}`. `reference` is keyed
by vehicle ID; `world` contains the supervised room’s existing obstacle/objective descriptions
(the initial unauthenticated world can belong to another room). `active` contains the public
injection fields (`kind`, `vehicle_id`, `scope`,
`strength`, `start`, `end`, `reaction_s`, optional thruster `index`), never saved originals or controls.
Use report `elapsed` as the simulation clock for countdowns; refresh reports to observe expiry,
other instructors and resets. Clients must tolerate this field being absent.
Empty phases remain null. References default to deployment location/depth, current
heading, zero stand-off and speed 0..0.5 m/s; instructors should explicitly set them.
Path error measures distance to the finite reference segment in the horizontal plane.
Grades use both RMS and outside-time fraction; all limits are **暫定** and require
company baseline flights. Reaction means first changed control packet after injection,
not a validated successful recovery. Completion/failure automatically archives a report;
reset archives interrupted dives. JSON, CSV and browser print-to-HTML/PDF are available.

This draft does **not** yet implement tether snags, sensor or video faults, lighting
faults, per-student POV rendering, course scheduling/aggregate grades, SDK measurement
fault adapters or permanent report storage. It is not ready for training acceptance.

## Ocean current model

The host is authoritative for the water flow; the viewer only displays it. `current_here` (§3) is the
full local flow at the vehicle. The ambient flow is the three-layer mean profile plus turbulence:

* **Turbulence** is a smooth, anisotropic, spatially varying field (`qysim/flow.py`,
  `TurbulenceField`): σu = `turbulence` × local mean speed, cross-stream and vertical σ in the ratio
  1 : 0.7 : 0.5 (Islay 1 : 0.75 : 0.55). Its integral length is about half the water depth (2–15 m), and
  it is advected with the depth-averaged current, so the integral time is ≈ 0.92 L/U and points one
  length scale apart are correlated by ≈ 0.4. It advances once per tick and its time derivative does
  not depend on the step size. All values are provisional simulator assumptions (see
  `docs/reference/current-validation.md`).
* **Near-bed profile**: the bottom layer value applies at 0.1 × depth (1–3 m) above the bed; below it the
  speed follows the log law ln(h/z0)/ln(h_ref/z0) (it used to fall linearly over the last metre).
  `World.current_at` measures h from the local terrain (reef and seagrass relief), with z0 from the
  biome (assumed bed types, Soulsby 1990 values: harbour mud 0.02 cm, temperate/seagrass rippled sand
  0.6 cm, reef rock 3 cm; gravel 0.3 cm). Optional `CurrentProfile.z0` overrides it.
* **Tide** (optional `current.tide`; absent = steady profile, today's behaviour). The layer speeds and
  directions are the flood flow at factor 1. Fields (all optional):
  `kind` `"rectilinear"`|`"rotary"`, `m2` (0–2, default 1) and `m2_phase_deg`, `s2` (0–1, default 0)
  and `s2_phase_deg`, `flood_dir` (rotate the profile so the surface floods toward it), `ebb_dir`
  (default reversed), `ebb_ratio` (0–2, default 1), `minor_ratio` (rotary, 0–1), `residual` (−1..1,
  non-tidal part of the factor), `time_scale` (default 1 = real time; >1 only for classroom
  demonstrations) and `start`: `"peak_flood"` (default), `"slack_before_ebb"`, `"peak_ebb"`,
  `"slack_before_flood"` or hours after peak flood. Factor = m2·cos(ωM2·τ+φ) + s2·cos(ωS2·τ+φ) +
  residual with the 12.42 h M2 period; a rectilinear factor below zero is ebb; a rotary tide adds
  `minor_ratio`·(sine terms) across the flood axis, turning clockwise, and never reaches slack.
  A pure M2 tide reproduces the NOAA Table 4A slack windows (≈ 23.8 min below 0.1 kn at a 1 kn
  maximum, ≈ 5.9 min at 4 kn).
* **Time-of-tide selector**: `{"type":"scenario",...,"tide_start":"slack_before_flood"}` (or hours,
  −13..13) starts a tidal scenario at that stage; host `current` messages also accept
  `"tide":{...}` (replace; `null` removes it) and `"tide_start"`. Invalid values are rejected with
  `invalid_command` and change nothing. Scenarios without a tide ignore `tide_start` on load.
* The former 18 % travelling sine "local flow" pattern (fixed 1 m/s drift toward 37.6°, independent of
  the real current) was removed; spatial variation now comes from the turbulence field.
* **Structures** (`StructureFlow`): around every non-habitat cylinder (piles, monopiles, jacket legs,
  braces, masts; any orientation, using the flow normal to the axis) the host adds a potential-flow
  doublet (stagnation upstream, up to 2U at the shoulders), a Gaussian wake (centreline deficit
  1/(1 + x/3D): ≈ 40 % at 5 D, ≈ 13 % at 20 D, ignored past 40 D) and alternating transverse
  vortex shedding at St = 0.2 (period D / 0.2U, ≈ 30 s for a 6 m pile in 1 m/s, ≈ 6 s for a
  1.2 m leg). Boxes (hulls, caissons) and wreck meshes get a lee shelter (−70 % right behind,
  decaying over three body sizes) and an upstream blocking zone (−50 %); walls block the normal
  component and slow the flow in a 2 m wall layer. Flow is zero inside solids. These are
  provisional engineering approximations, not CFD.
* **Fluid acceleration**: the vehicle feels (displaced mass + added mass) × dv_c/dt and each tether
  node ρ·A·l·(2 a_normal + a_axial) (Ca = 1 normal, as MoorDyn). dv_c/dt is the finite-difference
  rate of the sampled flow along the path, low-passed (50 ms) and clipped at 3 m/s²; a neutral body
  therefore follows an oscillating flow with amplitude ratio ≈ 1, and steady flow is unchanged.
* `World.current_at(point, t)` / `World.current_at_many(points, t)` return this **full local flow**
  (ambient + structures); the vehicle, tether nodes, silt, fish and work objects use it.
* `CurrentProfile.sample(position, seabed, t)` / `sample_many(...)` keep their signatures and return
  the **ambient** flow only (no structures, nominal seabed). `t` is accepted for compatibility; the field is evaluated at the
  profile clock that `step_gust(dt)` advances once per tick.
