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
A client that has not joined may send the optional, read-only
`{"type":"room_query","room_id":"training"}` (used by the launch menu's multiplayer screen). The reply is
`{"type":"room_info","room_id":"training","exists":true,"capacity":3,"scenario":"open_water","mission":"free_explore",
"players":[{"name":"Pilot","model_id":"x1","connected":true,"host":true}]}`; `scenario` and `mission` are omitted
when `exists` is false. The query never creates a room and never returns resume tokens. Older servers answer it with
`join_required`.

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
                 (`silt_clouds`, legacy shape); optional `silt_puffs` and `turbidity`, see §4a
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
| `{"type":"payout","metres":5}` | legacy: move the deployed length by +/− metres. Since the reel model the change is no longer instant: the reel pays out at the tender feed rate or hauls in at the motor rate until the target is reached, then resumes its previous mode (`state.tether.reel.target_length`) |
| `{"type":"auto_payout","value":false}` | legacy toggle: `true` = reel mode `auto` (constant-tension controller), `false` = reel mode `hold` (brake on, fixed length, as before) |
| `{"type":"reel","command":"pay_out"}` | optional, new: tender / reel rate command — `free` (drum turns freely; the vehicle drags tether off against bearing drag), `hold` (brake on; slips above the brake holding force), `pay_out` (tender hand-feeds tether), `haul_in` (powered haul-in with a line-pull cap; stalls against a snag), `auto` (constant-tension controller). Unknown commands are rejected with `invalid_command`. Clients send it only when `state.tether.reel` is present. |
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
battery %        (always 100 for tether-powered vehicles; see `power`)   recording bool   photos int
current_here [n,e,d] m/s at the ROV     current_kn
flow_field {seq, t, origin [n,e,d], step [m,m,m], size [nx,ny,nz], cm_s [...], tide?}   (optional, see
           "Ocean current model"; top level only, not inside `vehicles`)
tether {nodes [[n,e,d]...], length, max_length, tension_rov, tension_spool, tension_max (N),
        warn bool, broken bool, contact_nodes, snagged_on [names], wraps {obstacle: turns}, auto_payout,
        optional additions (absent on older hosts):
        reel {mode: free|hold|pay_out|haul_in|auto, speed m/s (+ out), stalled bool,
              target_length m|null, tension_n},
        turns            net vehicle heading turns put into the tether (+ = clockwise seen from above),
        snags [{name, point [n,e,d], held bool, since s, hold_n, tension_n}]   hooked snag points,
        chafe 0..1       worst segment chafe work / provisional limit,
        working_load_n, gland_working_load_n   rated working loads behind `warn`,
        break_reason     null | "gland" | "cable" | "chafe"}
```

Tether notes (since the reel / physical-stiffness model; see `docs/reference/tether-validation.md`):

* `nodes` no longer has a fixed count: payout adds nodes at the spool end and long tethers merge
  spool-side segments. Clients must not assume 41 nodes.
* `tension_rov` and `tension_max` are the highest values of any solver substep in the tick.
* `warn` now means the rated working load is exceeded: half the breaking strength on any segment, or
  half the termination (gland) strength at the vehicle end. It used to be a fixed 250 N. The scorer
  still deducts 10 points per over-tension episode.
* Server-side `Tether.events` (not streamed) record `tether_break` with `where` (`gland`, `cable` or `chafe`),
  `tether_snag`, `tether_snag_released` and `reel_stall`; clients read the state fields above.
* `auto_payout` is `true` only in reel mode `auto`. A new host starts in reel mode `free`.

```text
events [{t, obstacle, speed, severity: touch|hard|severe, where}]   (last 12 impacts)
damage [{t, thruster, health}]
silt 0..1 (seabed silt cloud; reduce visibility). Defined as 1 − effective/base visibility at the
     vehicle (sediment share of the beam attenuation); 0 in clear water, approaches 1 in a silt-out.
turbidity {mg_l, visibility_m, c}   optional: suspended sediment (mg/L) at the onboard camera, the
     black-target visibility there (m, = 4.8 / c, no floor) and the beam attenuation c (1/m)
sensors {...}    optional: what the vehicle's own instruments report (see "Optional sensor layer")
nav {mode: IDLE|H_NAVI|V_NAVI|VCCM, nav_status, vccm, route [[n,e,d]...], route_i, target [n,e,d]|null}
score {score 0..100, elapsed, failed "", finished, current_index,
       objectives [{kind, label, point [n,e,d], radius, hold_s, done, progress 0..1, target}],
       penalties [{t, reason, points}], penalty_total}
log [{t, kind, text}]   (last 8 lines, Traditional Chinese)
```

### Optional `power`: tether power budget / battery

`state.power` (and each fleet entry) is an optional addition; existing fields keep their meaning.

```text
power {type: tether|battery, available_w W|null, demand_w W, thruster_w W, lights_w W,
       limited bool, scale 0..1, tripped bool, cutoff bool, lights_on bool,
       voltage_v V|null, soc %|null}
```

* `type:"tether"` (X1 and the larger catalogue vehicle): no battery and no drain. Thrusters
  (power ~ thrust^1.5), lights and a fixed electronics load share `available_w`. When the demand
  exceeds it, every thruster command is scaled by the same factor (`scale`, `limited:true`), so all
  thrusters together cannot reach their individual maxima. `tripped` (instructor `power_trip`)
  removes all thrust and lights and drops the vehicle link until reset. The legacy `battery` field
  stays at 100 so old clients see a full, non-draining value. An instructor `battery` injection on a
  tether vehicle lowers `available_w` (supply sag) instead.
* `type:"battery"`: the existing state-of-charge drain is unchanged. At 0% motors and lights are
  cut off (`cutoff:true`) and re-enabled above 2%. `voltage_v` is a linear 4S estimate.
* `lights_on:false` means the lamps are unpowered even though `rc.right_switch` is on.

SDK compatibility: `QYRovNavigationManage.get_rov_data` `rov.power` keeps exactly
`{type:"battery", battery_cap_1, battery_cap_2}` for battery vehicles. Tether vehicles report
`type:"tether"` (a new value), `battery_cap_1`/`battery_cap_2` = 100 and `endurance` = 5000 (the
legacy full-charge value; a tether vehicle has no endurance limit), plus optional `available_w`,
`demand_w`, `limited`, `tripped`. Clients that only read the battery percentages keep working and
see a full supply. `get_rov_status` reports `Battery: "Left: 100, Right: 100"` and the self-test
battery flags stay healthy for tether vehicles. All wattages are provisional engineering
assumptions (X1 supply power, light wattage and thruster current are unpublished); see
`qysim/power.py` for each value's source.

### Optional `thermal` and `leak`

```text
thermal {motor_c (hottest thruster), mos_c (motor drivers), housing_c, in_water bool, dry_run_s,
         warnings [dry_run|motor_hot|electronics_hot]}
leak {detected bool}
```

A first-order model: heat follows electrical load, cooling is strong in water and weak in air.
`dry_run` is raised after 30 s of running thrusters out of water (vendor rule; the vehicle is out
of water only in a deck state, `on_deck` server-side, which current scenarios never use). Sustained
full thrust in water reaches `motor_hot` after several minutes. Warnings only, no derating. Each new
warning is also written to `log` (kind `thermal`). Thresholds are provisional assumptions.
`QYRovCheckManage.ego_self_test` now reports the modelled `temp` (housing) and `mos_temp` instead of
the constants 31 / 38 (the model starts at those values in 26 °C surface water) and `leak: 0` while a
leak is detected (1 = dry, unchanged otherwise).

### Optional `link`: simulated vehicle communications link

`state.link` (and each fleet entry) describes the *simulated* tether link between topside and
the vehicle. It is a training fault model and is separate from the simulator's own network
watchdog (0.6 s input timeout, latch and resync described above), which is unchanged.
Clients that ignore the field behave exactly as before. The link is `healthy` unless a scenario
(`Scenario.link`, server-side) or an instructor injection changes it; nothing degrades on its own.

```text
link {state: healthy|degraded|lost, phase: connected|lost|reconnecting, cause: comms|power|null,
      quality 0..1, video_lag_s, video_frozen bool, artefact 0..1, telemetry_hz number|null,
      failsafe_action: disarm|depth_hold|surface, failsafe: null|disarm|depth_hold|surface,
      failsafe_in s|null, reconnect_in s|null, rearm_required bool}
```

* `degraded`: commands still reach the vehicle. `video_lag_s` grows toward a cap (5 s at full
  severity), `video_frozen` is true during periodic freeze episodes (about 5 s every 20 s at full
  severity), `artefact` is the compression-artefact level and `telemetry_hz` the reduced telemetry
  rate (`null` means unchanged).
* `lost` (`phase:"lost"`): no command reaches the vehicle; it keeps executing the last command
  it received. After `failsafe_delay_s` (default 3 s) it applies `failsafe_action`: `disarm`
  (default; the same latched lock as the network failsafe, `input_latched` and a new
  `control_generation`), `depth_hold` (holds the depth at the moment of the failsafe) or
  `surface` (ascends through the depth-hold loop). Video is frozen and telemetry stops
  (`telemetry_hz: 0`). A loss caused by a power trip disarms immediately.
* `reconnecting`: the link has been restored and the modem re-establishes for `reconnect_s`
  (default 30 s); `state` is still `lost`. Afterwards the vehicle is locked again and
  `rearm_required` stays true until the pilot sends a locked packet and then an unlocked one.
  A `depth_hold`/`surface` failsafe keeps running until that re-arm.

Viewer presentation: `video_lag_s` is added to the video delay, a frozen link holds the last
rendered picture (onboard camera) and the last vehicle pose, and onboard telemetry read-outs are
released at `telemetry_hz`. Defaults are provisional (an open-source sub autopilot's failsafe
options and 3 s pilot-input timeout, a ~30 s reconnect figure from an earlier vehicle's vendor FAQ,
field reports of 4–5 s lag and 5 s/20 s freezes; sources in
`research_notes/感測器_揚沙_通訊/comms_and_power.md`); none are X1 measurements. SDK RPC telemetry is not affected by the simulated link.

## 4. World object (`type: "world"`)

```text
seabed_depth m
obstacles [ {type:"cylinder", name, p0 [n,e,d], p1 [n,e,d], radius, kind: pile|monopile|jacket_leg|brace|mast|...}
          | {type:"box", name, center [n,e,d], half [hx,hy,hz], yaw_deg, kind: hull|wreck|...}      (hx along heading yaw_deg)
          | {type:"wall", name, point [n,e,d], normal_deg, width, top, kind: wall|quay}          (vertical face; extends from `top` down to the seabed)
          | {type:"snag", name, point [n,e,d], radius, height, kind: snag, item: rock|boulder|debris|rope}
                                (optional: small snaggable seabed item standing on `point`; clients that do not know the type may skip it)
          | {type:"ship_hull", name, center [n,e,d], yaw_deg, length, beam, draft, top, kind: hull}   (optional, see below)
          | {type:"model", ...} ]
current {surface_kn, surface_dir, mid_kn, mid_dir, bottom_kn, bottom_dir, turbulence, tide?}
                      (turbulence = streamwise intensity σu/U; optional tide object only when the scenario
                      has one; see "Ocean current model" below)
scenario {key, name, brief, seed, visibility_m, time_limit_s, tether_length,
          biome, seabed_type, bnl_height_m, bnl_mg_l,       (the last three optional, see §4a)
          water_type}       (optional: oceanic | coastal | shelf | harbour | fresh_clear; the optical water
                            type the viewer colours the water with, loosely after Jerlov's classes; default
                            from the biome: reef oceanic, seagrass coastal, harbor harbour, fresh water
                            fresh_clear, otherwise shelf. Presentation only: physics and visibility_m are
                            unchanged; clients that do not know it use their generic water.)
spool [n,e,d]         tether spool / deployment point on the surface
start_pos [n,e,d]     ROV start position (the viewer's deployment intro ends here)
catalogue [{key, name, brief}]  scenarios for a picker (includes "random")
objectives [...]      same shape as in score.objectives
thrusters [{name, pos [x,y,z] body FRD, axis [x,y,z]}]
```

Structure details (optional, added with the dressed inspection sites). Clients that only know the three
original shapes keep working: details are ordinary `cylinder`/`box` obstacles, and `kind` values they do not
know can be drawn with a default colour.

* Detail kinds on `cylinder`: `anode`, `anode_strap` (jacket legs), `transition_piece`, `boat_landing`, `j_tube`,
  `cable_protection`, `scour_rock` (buried horizontal capsules forming the rock berm round a monopile),
  `fender`, `bollard`, `toe_rock` (quays), `debris_pipe`, `bilge_keel`, `shaft`, `propeller` (ship hulls).
  On `box`: `mudmat`, `ladder`, `tyre`, `debris_block`, `deck`, `rudder`. Wrap counts (`tether.wraps`) only
  count primary members (`pile`, `monopile`, `jacket_leg`, `brace`, `mast`), not these fittings.
* `wall` with `kind:"quay"` is a harbour quay (concrete face); other walls (e.g. the training pool) keep `wall`.
* `ship_hull` replaces the old hull `box` in the hull scenarios: a flat-bottomed hull with round bilges, a bow
  taper with raked stem and a counter stern over the propeller aperture. `center` is midships on the waterline,
  `yaw_deg` the bow heading, `top` the deck (negative = above water). The exact proportions and the signed
  distance are in `qysim/world.py` (`ship_hull_params`, `ship_hull_local_sdf`) and mirrored in
  `viewer/structure_sdf.js`. The propeller, rudder and bilge keels are separate obstacles named
  `<hull name> propeller ...`, `<hull name> rudder`, `<hull name> bilge keel ...`.
* Seabed fittings taller than about 0.2 m (scour and toe rock, mud mats, tyres, blocks, pipes, cable protection)
  carry the tether snag model's `snag_hold` on the host, like `snag` items and the Korean Castle wreck; they are
  ordinary obstacles in the world message. Fittings that sit in the near-bed layer (scour and toe rock, cable
  protection, seabed debris, mud mats) and small attachments (anode straps, propeller blades) make no wake in
  the structure flow; a `ship_hull` gives the box-like lee shelter of its hull envelope.

### 4a. Sediment and turbidity (optional fields)

The host simulates thruster-induced silt (`qysim/silt.py`): each thruster jet is followed along its
world axis, eroding the bed only above the seabed type's critical shear, and the sediment is carried
as mass-conserving Gaussian puffs that settle by grain class, drift with the current and spread.
All coefficients are provisional (see `docs/reference/silt-validation.md`).

```text
world.scenario.seabed_type   fluff | mud | silt | sand | gravel | rock   (rock never erodes)
world.scenario.bnl_height_m  e-folding height of a near-bed turbid layer (0 = none)
world.scenario.bnl_mg_l      extra suspended sediment at the bed from that layer, mg/L
state.environment.silt_puffs [[n, e, d, sigma_h, sigma_v, peak_mg_l], ...]   up to 64, strongest first
state.environment.turbidity  {seabed_type, c_water, k_m2_per_g, bnl_height_m, bnl_mg_l}
```

A client may reconstruct the concentration anywhere as the sum over puffs of
`peak * exp(-(dn²+de²)/(2 sigma_h²)) * (exp(-dd²/(2 sigma_v²)) + exp(-dd_img²/(2 sigma_v²)))`, where
`dd_img` is measured from the puff's mirror image below the seabed, plus
`bnl_mg_l * exp(-altitude / bnl_height_m)`. Beam attenuation is `c = c_water + k_m2_per_g * C`
(C in mg/L = g/m³) and black-target visibility is `4.8 / c`. `c_water` is `4.8 / visibility_m`.
`silt_clouds` keeps its old keys (`pos`, `strength` 0..1, `radius`, `age`, `source`) for the strongest
24 puffs. Clients that ignore the new fields keep working.

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
That window is the ideal-sensor path. With the default realistic sensor layer the lock
comes from the DVL model instead (see "Optional sensor layer"), and position and velocity
feedback use the DVL-derived estimates rather than truth.
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

## Optional sensor layer

Every measurement a consumer reads passes through `qysim/sensors.py`: the flight controller (heading,
depth and position hold), the SDK autopilots and dead reckoning, SDK telemetry and `state.sensors`.
The realistic layer is the default. `QYSIM_SENSORS=ideal` in the server environment (or
`Simulator(sensor_config=SensorConfig(ideal=True))`) turns every imperfection off; that path is compared
byte-for-byte with a frozen copy of the pre-layer engine (`tests/test_sensors.py`). All values below are
provisional and labelled with their sources in `qysim/sensors.py`; none is an X1 measurement.

`state.sensors` (optional; clients must tolerate its absence):

```text
ideal bool              true when imperfections are off (values are then truth)
heading deg 0-360       estimated heading (gyro + magnetometer fusion, steel deviation)
depth m                 pressure depth (zero offset, density setting, 2 mm quantisation, noise)
altitude m|null         altimeter: nearest echo in a 25 deg cone; null = no echo or blind zone
altitude_blind bool     true when the nearest echo is inside the 0.3 m blind zone (realistic layer only)
range m|null            forward echo sounder, same cone model; range_blind as above
dvl {status: locked|coasting|lost, reason: null|too_high|too_low|slope|vegetation|silt|aeration|mud|
     pool|range|fault|window, altitude m|null, ground_speed_kn kn|null (null while lost)}
pos_est [n,e,d]         dead-reckoned position (DVL velocity x estimated heading; frozen while lost;
                        reset to the GPS fix at the surface)
realigned_t s|null      time of the last "yaw re-aligned" jump of the heading estimator
faults [kind]           active instructor sensor faults
```

Existing fields keep their meaning: `pos`, `q`, `euler`, `vel`, `speed_kn`, `current_here` and
`current_kn` remain physics truth (they drive rendering and replay). The viewer's real fidelity preset
shows `state.sensors` instead of them; the `truthTelemetry` fidelity item (exceeds the real vehicle, on in
`assisted`) restores the truth presentation. Position and velocity assistance require DVL bottom lock:
while `dvl.status` is `lost` the controller falls back to manual exactly as with the old window.

SDK telemetry with the realistic layer (shapes unchanged): `Depth`, `Compass`, attitude `Yaw`, the
50 Hz quaternion and depth, the 10 Hz velocity, latitude/longitude and yaw, and `get_rov_data` /
`get_navigation_status` / `init_dr` positions use the estimates above. `Accessories_Status.DVL_Status`
is `"OnLine"` while bottom lock holds and `"OffLine"` while it is lost; `QDVL`/`MicroDVL` speeds read
0.0 while lost. `Altitude`/`Distance` read the echo sounders, with the maximum range (100 / 50 m) for
no echo and 0.3 for an echo inside the blind zone. `get_rov_data.dvl` adds optional `velocity_valid`
(bool) and `lock` (status string), sets `position_valid` false while lock is lost, and reports per-beam
slant ranges (0.0 for a beam without return). Pitch, roll, `Temp` and power fields are unchanged.

Scenarios may name `water` (`salt` default, `fresh` for the pool) and `seabed_type`
(`sand`, `mud`, `rock`, `pool`; default from the biome). The depth sensor's density setting defaults to
the site's water.

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
  or a sensor fault `kind:"compass"|"depth_sensor"|"dvl"|"altimeter"` (realistic sensor layer only;
  rejected with `ValueError` when the host runs ideal sensors). Sensor faults change only what the
  vehicle measures: `compass` adds up to 60 deg of deviation (strength x 60) treated as a strong
  anomaly, `depth_sensor` drifts the reading by strength x 0.02 m/s and snaps back on expiry, `dvl`
  forces loss of bottom lock, `altimeter` makes each ping a false short echo or a dropout with
  probability = strength.
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
* Optional vehicle-system kinds (same `vehicle_id`, `strength`, `duration`, `cancel_start` rules,
  per-vehicle scope; see the optional `link`, `power`, `thermal`/`leak` state sections):
  `video_delay` (adds `strength` × 5 s of video lag, no freezes), `video_freeze` (holds the video),
  `link_degrade` (degraded link with severity `strength`), `comms_loss` (link lost; on expiry the
  reconnect starts), `power_trip` (all thrust, lights and the link drop and the vehicle disarms
  immediately; on expiry power returns and the link reconnects), `leak` (leak alarm, self-test
  `leak: 0`) and `overheat` (adds `strength` × 50 °C to motor and driver readings). `comms_loss`
  accepts optional `failsafe` (`disarm`|`depth_hold`|`surface`), `failsafe_delay` and `reconnect`
  (0..600 s) for that injection only. `freeze` remains a physics pause, unrelated to `video_freeze`.
  On a tether-powered vehicle a `battery` injection lowers the supply power instead of a charge.
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

This draft does **not** yet implement tether snags, sensor faults, lighting
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
  1.2 m leg). Small snaggable seabed items (`type:"snag"`) add no wake; the bed roughness covers them.
  Boxes (hulls, caissons) and wreck meshes get a lee shelter (−70 % right behind,
  decaying over three body sizes) and an upstream blocking zone (−50 %); walls block the normal
  component and slow the flow in a 2 m wall layer. Flow is zero inside solids. These are
  provisional engineering approximations, not CFD.
* **Fluid acceleration**: the vehicle feels (displaced mass + added mass) × dv_c/dt and each tether
  node ρ·A·l·a + Ca·ρ·A·l·a_normal (Froude-Krylov plus the tether's normal added mass, Ca = 1 as MoorDyn),
  applied inside every tether solver substep. dv_c/dt is the finite-difference
  rate of the sampled flow along the path, low-passed (50 ms) and clipped at 3 m/s²; a neutral body
  therefore follows an oscillating flow with amplitude ratio ≈ 1, and steady flow is unchanged.
* **Hull sampling**: the engine samples the flow at the CG and six hull points (bow, stern, port,
  starboard, top, bottom); differences from the CG flow add a linearised drag force and torque, so
  wake edges and shear yaw or pitch the vehicle. Uniform flow gives exactly the old result.
  `current_here` stays the CG value.
* `World.current_at(point, t)` / `World.current_at_many(points, t)` return this **full local flow**
  (ambient + structures); the vehicle, tether nodes, silt, fish and work objects use it.
* `CurrentProfile.sample(position, seabed, t)` / `sample_many(...)` keep their signatures and return
  the **ambient** flow only (no structures, nominal seabed). `t` is accepted for compatibility; the field is evaluated at the
  profile clock that `step_gust(dt)` advances once per tick.
* **Viewer cues** (`state.flow_field`, optional): the host samples `World.current_at_many` on a
  5 × 5 × 2 grid around the selected vehicle (6 m spacing; the two levels 3 m above and below it,
  kept inside the water column) every 0.5 s of simulation time. `cm_s` holds integer cm/s,
  `[n, e, d]` per point, in index order `((i·ny + j)·nz + k)` with i along north, j east, k down.
  `seq` increases with every new grid; the same grid repeats in the states in between (about
  600 bytes, ≈ 5 % of a state). `tide` is `{factor, stage: flood|ebb|slack, minutes_to_slack}` when
  the scenario has a tide (`minutes_to_slack` is null for rotary tides). Viewers interpolate it
  trilinearly (clamped at the edges) and blend successive grids over 0.5 s
  (`viewer/flow_field.js`); drifting particles and kelp/seagrass sway use it, so they move with the
  same gusts, tide and wakes that push the vehicle. Clients that ignore it keep working; hosts
  that do not send it leave the viewer on its mean-profile fallback.

## Optional `state.tether_ops` (T21)

Older clients may ignore this object; absent means no cable operations feedback. It is an observer of the
tether solver (`qysim/tether_ops.py`) and applies no force.

* `turns` is the solver's net vehicle heading turns (`state.tether.turns`); `torque_nm` is the restoring yaw
  moment the solver applies for it (GJ × twist angle / deployed length, see the tether notes in §3).
  `twist_warning` is true beyond ±2 turns: a console / tender warning only, not an extra force.
* `events` is a rolling list of 20 `{id, code, metres?, mode?}` radio messages; codes are `length` (5 m bucket
  changes in either direction), `tension` (rated working load exceeded, same as `tether.warn`), `structure`
  (cable touching a structure), `twist`, `snag` (a recovery episode starts), `released`, `reel` (reel mode
  changed to `mode`: free|hold|pay_out|haul_in|auto) and `stall` (powered haul-in stalled).
* An episode starts when the solver reports a snag hook (`tether.snags`) or a wrap of at least a quarter turn
  (`tether.wraps`). `snag` is null or `{name, kind: snag|wrap, returned, tightening}`. Tightening accumulates
  vehicle-end load above the termination's rated working load (`tether.gland_working_load_n`).
* `result` is null or `{score, peak_n, elapsed, returned, correct, kind}` for the last episode. High scores
  need facing and returning to the cable point first, then unwinding in the reverse sense (wraps) or backing
  out until the hook lets go (snags); peak vehicle-end load relative to its working load and elapsed seconds
  reduce the score. Broken cables score zero.
* `slack_seconds` counts excess paid length over the direct span > 10 m; `taut_seconds` counts time with
  `tether.warn`. `discipline_score` (0–100) deducts one point per excess-slack second and two per warn second.

All thresholds and score weights are provisional training assumptions. Reel commands are unchanged (`payout`,
`auto_payout`, `reel`, controlling player only). Clump weights and a separately authorized multiplayer
tether-hand role are not yet supported.

## Optional procedure (T23)

`{ "type":"procedure", "action":"begin" }` opts this vehicle into the full deployment procedure.
Without it, existing SDK/RC behavior is unchanged. Subsequent actions are `check` (`key` in ordered
`seals, connector, trim, power, communication, camera, lights, thrusters, instruments, unlock`),
`test` (`index`, zero-based two-second diagnostic pulse), `skip`, `tender`, `lower`
(`point:"upstream"`), `water_confirm`, `recover`, `rinse`, `inspect`, `save` (`notes`).
Invalid progression returns the existing error envelope; accepted actions return `procedure_result`.
`state.procedure` (present only while this vehicle has opted in; absent otherwise) adds phase, checked keys, tests, dry time, penalty, events, elapsed time, peak depth,
peak cable length and notes. Physics enforces locked flight outside `diving`, including SDK input.
`state.score.procedure_penalty` is optional. Skips have a seeded 35% per-check fault probability
(training assumption); missing communication checks may cause control loss and forced cable recovery.
Recovery rate and wave modulation are provisional training approximations, not measured vessel limits.

## Optional forward imaging sonar (simulator extension)

Viewer sends `{"type":"operation","action":"sonar_subscribe","enabled":true,"range_m":30,
"noise":0.02,"multipath":0.05}`. Range: 2–50 m; noise and multipath: 0–1.
Defaults shown above. Disable with `enabled:false`; disconnect clears the subscription.
Only the subscribed connection receives `state.sonar`, refreshed at 5 Hz independently
of physics. Each frame contains Unix `timestamp`, `range_m`, `fov_deg:120`, `beams:256`,
`distance_m`, `intensity` (unsigned 8-bit integers), and `ghost_m` arrays.
Beam indices run from -60° (port) to +60° (starboard), relative to body forward.
Distances are slant ranges in metres; range limit means no return. First surfaces occlude
later targets. `ghost_m` is a weak synthetic multipath return (range limit means none).
Noise, attenuation, target sizes and multipath are illustrative training assumptions,
not measurements of a specific instrument. This is a horizontal slice, without elevation resolution.
The SDK RPC `{"type":"sonar_latest"}` reads the latest subscribed primary vehicle frame,
or null before any scan. It does not enable scanning or change existing SDK calls.

## Optional simulator vision extension

Viewer message `{"type":"vision_results","detections":[{"cls":"coral","score":1,"box":[0.1,0.2,0.3,0.4]}]}`
reports normalized top-left xywh boxes. Reports are untrusted client assistance, never scoring authority.
RPC `{"type":"vision_results"}` reads the primary simulator vehicle's latest report with `age_s`;
after one second, returns `{"available":false,"detections":[]}`. Requires an active reporting viewer.
This is not a native SDK interface and is not aligned to the mock SDK's separately synthesized BGR frames.
Python extension: `QYCameraMediaStreamManage.get_sim_detections()`.

G7 adds optional `embedded: true` to `snag` obstacles whose geometry is already drawn by a scene GLB.
It suppresses only the duplicate procedural visual; collision and tether snag semantics are unchanged.
Absent means the existing standalone visual. Authored snag metadata uses the FieldMesh local frame;
`point`, `radius`, `height`, `hold_n` and `item` map to `SnagFeature`. `direction` describes the source
feature tangent; small sphere capsules sample angled features without changing the vertical capsule API.
