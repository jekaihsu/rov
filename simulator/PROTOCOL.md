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
{"type":"session","protocol":2,"room_id":"training","player_id":"opaque-id","vehicle_id":"v1","resume_token":"private-token","generation":1,"is_host":true,"capacity":4}
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
`{"type":"error","code":"host_only|join_required|stale_input|session_replaced|invalid_command","message":"..."}`.
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
vehicle_id       runtime ID, v1–v4 (room-local)
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
| `{"type":"scenario","key":"random","seed":123}` | load a scenario (`seed` optional) |
| `{"type":"reset"}` | restart the current scenario |
| `{"type":"pause","value":true}` | pause / resume |
| `{"type":"payout","metres":5}` | pay out (+) / recover (−) tether |
| `{"type":"auto_payout","value":false}` | toggle automatic payout |
| `{"type":"operation_mode","value":"ROV_JPN"}` | ROV_USA/JPN/CHN, UAV_USA/JPN/CHN |
| `{"type":"current","surface_kn":2,"surface_dir":90,"mid_kn":1.5,"mid_dir":100,"bottom_kn":0.5,"bottom_dir":110,"turbulence":0.2}` | override current (directions = where water flows TO, degrees from north) |
| `{"type":"shaping","throttle_curvature":60,"throttle_limit":100,"rotate_curvature":60,"rotate_limit":100}` | stick curves |
| `{"type":"remote_release"}` | force SDK remote control OFF (give control back to the physical RC) |

Stick meaning depends on `operation_mode` (see `qysim/rc.py`); the viewer only sends raw channels.

## 3. State object (`type: "state"`)

```text
t                sim seconds            paused        bool
pos [n,e,d]      NED m                  q [w,x,y,z]   body→world
euler [roll,pitch,yaw_0_360] deg        vel [u,v,w]   body m/s
speed_kn         speed through water
thrust [6]       -1..1 per thruster (order = world.thrusters)
health [6]       0..1 thruster health (impact damage)
rc {...}         active RC (SDK when remote_control) — same keys as the rc message
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
current {surface_kn, surface_dir, mid_kn, mid_dir, bottom_kn, bottom_dir, turbulence}
scenario {key, name, brief, seed, visibility_m, time_limit_s, tether_length}
spool [n,e,d]         tether spool / deployment point on the surface
start_pos [n,e,d]     ROV start position (the viewer's deployment intro ends here)
catalogue [{key, name, brief}]  scenarios for a picker (includes "random")
objectives [...]      same shape as in score.objectives
thrusters [{name, pos [x,y,z] body FRD, axis [x,y,z]}]
```
