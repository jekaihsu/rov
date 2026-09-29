# qysim protocols

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
catalogue [{key, name, brief}]  scenarios for a picker (includes "random")
objectives [...]      same shape as in score.objectives
thrusters [{name, pos [x,y,z] body FRD, axis [x,y,z]}]
```
