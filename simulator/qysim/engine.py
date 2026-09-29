"""Simulator engine: one object owning the whole simulated ROV system.

Per step:  input source (physical RC or SDK remote) -> operation-mode mapping ->
autopilot (H_NAVI / V_NAVI / VCCM) -> flight controller -> tether + contact ->
6-DOF physics -> battery, camera, scoring.

``sdk_call(cls, method, args, kwargs)`` implements every public method of the
QYSea OpenSDK manage layer with the same return formats; the mock ``qysea``
package forwards to it over a local socket.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from . import scenarios as sc_mod
from .controller import FlightController
from .navigation import GeoFrame, Navigator, wrap_pi
from .physics import KNOT, THRUSTERS, Vehicle, q_from_euler, q_rot
from .rc import OPERATION_MODES, RCState, Shaping, ctrl_mode, pilot_command
from .tether import GLAND_BODY, Tether
from .world import World

MOTOR_FIELDS = {  # self-test field -> thruster index (see physics.THRUSTERS)
    "motor_left_front": 0, "motor_right_front": 1, "motor_left_rear": 2,
    "motor_right_rear": 3, "motor_left_middle": 4, "motor_right_middle": 5,
}
LED_LABEL = {0: "OFF", 1: "1", 2: "2"}


def ok(text="Success", code="200", **extra) -> dict:
    return {"status": "ok", "status_code": code, "text": text, **extra}


def err(text, code="400", **extra) -> dict:
    return {"status": "error", "status_code": code, "text": text, **extra}


@dataclass
class CameraState:
    work_mode: str = "NORMAL_VIDEO_MODE"
    params: dict = field(default_factory=dict)
    recording_since: float | None = None
    files: list = field(default_factory=list)      # dicts: path, name, size, time, create_time, pose
    counter: int = 1


class Simulator:
    def __init__(self, scenario: str = "open_water", seed: int | None = None, rate_hz: float = 100.0):
        self.dt = 1.0 / rate_hz
        self.rng = np.random.default_rng(seed)
        self.load_scenario(scenario, seed)

    # ── setup ─────────────────────────────────────────────────────────────
    def load_scenario(self, key: str, seed: int | None = None) -> None:
        sc = sc_mod.build(key, seed)
        self.scenario = sc
        self.t = 0.0
        self.paused = False
        self.world = World(sc.seabed_depth)
        self.world.obstacles = list(sc.obstacles)
        self.world.current = sc.current
        self.geo = GeoFrame()
        self.vehicle = Vehicle()
        self.vehicle.seabed_depth = sc.seabed_depth
        self.vehicle.s.pos = np.array(sc.start_pos, float)
        self.vehicle.s.q = q_from_euler(0.0, 0.0, math.radians(sc.start_heading_deg))
        self.health = np.ones(len(THRUSTERS))
        self.controller = FlightController(self.vehicle)
        self.nav = Navigator(self.geo)
        self.rc_physical = RCState()
        self.rc_sdk = RCState()
        self.remote_control = False
        self.operation_mode = "ROV_USA"
        self.shaping = Shaping()
        self.camera = CameraState()
        self.battery = 100.0
        self.dvl_switches: dict = {}
        self.arm = "close"
        gland = self.vehicle.s.pos + q_rot(self.vehicle.s.q, GLAND_BODY)
        self.tether = Tether(self.world, np.array(sc.spool_pos, float), gland, sc.tether_length)
        if sc.prewrap:
            self._prewrap(sc.prewrap)
        # let the cable take its natural shape in the current before the clock starts
        self.tether.settle(2.0, self.vehicle.s.pos, self.vehicle.s.q)
        self.scorer = sc_mod.Scorer(sc)
        self._prev_buttons = {"record": 0, "photo": 0}
        self.damage_events: list[dict] = []
        self.log: list[dict] = []
        self._log("scenario", f"載入情境 {sc.name}")

    def _prewrap(self, cfg: dict) -> None:
        """Lay the cable around a pile: spool -> helix (~``turns``) -> ROV, ending on the ROV's side
        of the pile so the last run never passes through it."""
        pile = next(o for o in self.world.obstacles if o.name == cfg["pile"])
        c = np.asarray(pile.p0, float)
        r = pile.radius + 0.08
        d = float(cfg.get("depth", 10.0))
        turns = float(cfg.get("turns", 1.0))
        spool = np.asarray(self.scenario.spool_pos, float)
        gland = self.vehicle.s.pos + q_rot(self.vehicle.s.q, GLAND_BODY)
        a0 = math.atan2(spool[1] - c[1], spool[0] - c[0])
        a1 = math.atan2(gland[1] - c[1], gland[0] - c[0])
        sweep = 2 * math.pi * math.floor(turns) + (a1 - a0) % (2 * math.pi)
        pts = [spool, np.array([c[0] + r * 1.5 * math.cos(a0), c[1] + r * 1.5 * math.sin(a0), d - 1.0])]
        n = 64
        for k in range(1, n + 1):
            a = a0 + sweep * k / n
            pts.append(np.array([c[0] + r * math.cos(a), c[1] + r * math.sin(a), d - 1.0 + 1.0 * k / n]))
        pts.append(gland)
        self.tether.layout(pts)

    def _log(self, kind: str, text: str) -> None:
        self.log.append({"t": round(self.t, 2), "kind": kind, "text": text})
        self.log = self.log[-200:]

    # ── derived state ─────────────────────────────────────────────────────
    @property
    def rc(self) -> RCState:
        return self.rc_sdk if self.remote_control else self.rc_physical

    @property
    def yaw(self) -> float:
        return self.vehicle.euler[2]

    @property
    def depth(self) -> float:
        return float(self.vehicle.s.pos[2])

    def latlng(self) -> tuple[float, float]:
        p = self.vehicle.s.pos
        return self.geo.to_geo(p[0], p[1])

    # ── main step ─────────────────────────────────────────────────────────
    def step(self, dt: float | None = None) -> None:
        if self.paused:
            return
        dt = dt or self.dt
        v, s = self.vehicle, self.vehicle.s
        rc = self.rc
        locked = rc.rc_lock == 1 or self.tether.broken
        mode = ctrl_mode(rc)
        pilot = pilot_command(rc, self.operation_mode, self.shaping)
        keep_depth = bool(rc.keep_depth)
        self._buttons(rc)

        heading = None
        if not locked and (self.nav.mode != "IDLE" or self.nav.hold is not None):
            out = self.nav.step(dt, s.pos, self.yaw, v.world_velocity(), pilot, v.p.vmax[0])
            if out is not None:
                pilot = {**{k: 0.0 for k in ("surge", "sway", "heave", "roll", "pitch", "yaw")}, **out.cmd}
                heading = out.heading
                if out.depth is not None:
                    keep_depth = True
                    self.controller.depth_hold = out.depth
                    pilot["heave"] = 0.0
                mode = "A"

        self.world.current.step_gust(dt, self.rng)
        v.current_ned = self.world.current.at(self.depth, self.world.seabed_depth)
        thr = self.controller.update(dt, pilot, mode, locked, keep_depth, heading) * self.health
        w_tether = self.tether.step(dt, self.t, s.pos, s.q, v.world_velocity())
        n_events = len(self.world.events)
        w_contact = self.world.vehicle_contact(self.t, s.pos, s.q, s.vel, s.omega)
        v.step(dt, thr, w_tether + w_contact)
        self.world.step(dt)
        self._damage(n_events)

        load = float(np.mean(np.abs(s.thrust))) / v.p.thruster_max
        self.battery = max(0.0, self.battery - dt * (0.004 + 0.05 * load ** 1.5))
        self.t += dt
        self.scorer.update(dt, self)

    def _buttons(self, rc: RCState) -> None:
        for name in ("record", "photo"):
            val = getattr(rc, name)
            if val and not self._prev_buttons[name]:
                if name == "photo":
                    self._take_photo()
                else:
                    if self.camera.recording_since is None:
                        self._start_record()
                    else:
                        self._stop_record()
            self._prev_buttons[name] = val

    # thruster index by (hull zone, side) for impact damage
    _ZONE_THRUSTER = {("front", "port"): 0, ("front", "stbd"): 1, ("rear", "port"): 2,
                      ("rear", "stbd"): 3, ("mid", "port"): 4, ("mid", "stbd"): 5}

    def _damage(self, first_new: int) -> None:
        """A severe impact damages the thruster nearest the impact point (55% of remaining thrust)."""
        for ev in self.world.events[first_new:]:
            if ev.severity != "severe":
                continue
            zone = ev.where.split("-")[0]
            side = ev.where.split("-")[1] if "-" in ev.where else ("stbd" if self.rng.random() < 0.5 else "port")
            idx = self._ZONE_THRUSTER[(zone, side)]
            self.health[idx] = max(0.2, self.health[idx] * 0.55)
            name = THRUSTERS[idx][0]
            self.damage_events.append({"t": ev.t, "thruster": name, "health": round(float(self.health[idx]), 2)})
            self._log("damage", f"{name} 受損，推力剩 {self.health[idx] * 100:.0f}%")

    # ── camera ─────────────────────────────────────────────────────────────
    def _new_file(self, prefix: str, ext: str, duration: int = 0) -> dict:
        n = self.camera.counter
        self.camera.counter += 1
        name = f"{prefix}{n:04d}.{ext}"
        lat, lng = self.latlng()
        f = {"path": f"sd/DCIM/100MEDIA/{name}", "name": name, "size": 3_400_000 if ext == "JPG" else 45_000_000,
             "time": duration, "create_time": time.strftime("%Y/%m/%d %H:%M:%S"),
             "pose": {"n": float(self.vehicle.s.pos[0]), "e": float(self.vehicle.s.pos[1]),
                      "depth": self.depth, "yaw": math.degrees(self.yaw) % 360, "lat": lat, "lng": lng}}
        self.camera.files.append(f)
        return f

    def _take_photo(self) -> dict:
        f = self._new_file("SING", "JPG")
        self._log("photo", f"拍照 {f['name']} @ {self.depth:.1f} m")
        return f

    def _start_record(self) -> None:
        self.camera.recording_since = self.t
        self._log("record", "開始錄影")

    def _stop_record(self) -> None:
        if self.camera.recording_since is None:
            return
        dur = int(self.t - self.camera.recording_since)
        self.camera.recording_since = None
        f = self._new_file("NORM", "MP4", dur)
        self._log("record", f"停止錄影 {f['name']} ({dur}s)")

    # ── telemetry in SDK formats ───────────────────────────────────────────
    def sdk_status(self) -> dict:
        roll, pitch, yaw = self.vehicle.euler
        rc = self.rc
        s = self.vehicle.s
        fwd = q_rot(s.q, np.array([1.0, 0, 0]))
        down = q_rot(s.q, np.array([0, 0, 1.0]))
        dist = self.world.raycast(s.pos + fwd * 0.4, fwd, 50.0)
        alt = self.world.raycast(s.pos + down * 0.2, down, 100.0)
        vb = s.vel
        dvl = lambda p: {f"{p}_Xspeed": round(float(vb[0]), 3), f"{p}_Yspeed": round(float(vb[1]), 3),
                         f"{p}_Zspeed": round(float(vb[2]), 3), f"{p}_Altitude": round(alt, 2)}
        bat = int(round(self.battery))
        return {
            "status": "ok", "status_code": "", "text": "Success",
            "Battery": f"Left: {bat}, Right: {bat}",
            "Temp": int(round(26 - 0.15 * self.depth)),
            "Depth": round(self.depth, 2),
            "Compass": int(round(math.degrees(yaw) % 360)),
            "Rov_Attitude_Angle": {"Pitch": int(round(math.degrees(pitch))), "Yaw": int(round(math.degrees(yaw) % 360)),
                                   "Roll": int(round(math.degrees(roll)))},
            "RC_Switch_Status": {"RC_Lock": "lock" if rc.rc_lock else "unlock",
                                 "Depth_Keeping": "ON" if rc.keep_depth else "OFF",
                                 "Record": "ON" if rc.record else "OFF", "Photo": "ON" if rc.photo else "OFF",
                                 "Rov_Ctrl_Limit": "Custom" if self.shaping.custom else "Normal",
                                 "Rov_Operation_Mode": self.operation_mode, "Rov_Ctrl_Mode": ctrl_mode(rc),
                                 "LED": LED_LABEL.get(rc.right_switch, "OFF")},
            "Sonar_Application_Status": {"Laser_Status": "ON" if str(self.dvl_switches.get(
                                             "QYRovParameterManage.microdvl_laser_switch", "OFF")).upper() in ("ON", "TRUE", "1") else "OFF",
                                         "Distance_Lock_Status": "OFF", "Blind_Detect_Status": "OFF",
                                         "Altitude_Lock_Status": "OFF"},
            "Distance": round(dist, 2), "Altitude": round(alt, 2),
            "Accessories_Status": {k: "OffLine" for k in (
                "Manipulator_Status", "Water_Sampler_Status", "Mud_Sampler_Status", "DL_Status", "AL_Status",
                "SL_Status", "DL_AL_Status", "DL_SL_Status", "AL_SL_Status", "Laser_Status", "Laser_DL_Status",
                "Laser_AL_Status", "Laser_DL_AL_Status", "Image_Sonar_Status", "QCamera_Status", "pH_Sensor_Status",
                "Salt_Sensorr_Status", "NTU_Sensor_Status", "Do_Sensor_Status", "OPSS_Status", "Metal_Detector_Status")}
                                  | {"DVL_Status": "OnLine"},
            "A50DVL": {f"A50DVL_{k}": "" for k in ("Xspeed", "Yspeed", "Zspeed", "Altitude")},
            "QDVL": dvl("QDVL"),
            "MicroDVL": dvl("MicroDVL"),
            "QCamDVL": {**{f"QCamDVL_{k}": "" for k in ("Xspeed", "Yspeed", "Zspeed", "Altitude")},
                        "station_lock_status": 0, "fpvc_status": 0, "installation_direction_status": 0,
                        "q_led_status": 0, "q_laser_status": 0},
            "rov_type": "X1",
        }

    def hf_status(self, which: str) -> dict:
        s = self.vehicle.s
        roll, pitch, yaw = self.vehicle.euler
        ts = int(time.time() * 1000)
        if which == "50hz":
            specific = s.accel - q_rot(np.array([s.q[0], -s.q[1], -s.q[2], -s.q[3]]), np.array([0, 0, 9.81]))
            return {"status": "ok", "status_code": "", "type": "50hz", "data": {
                "timestamp": ts,
                "acceleration": {k: round(float(val), 2) for k, val in zip("xyz", specific)},
                "gyroscope": {k: round(math.degrees(float(val)), 2) for k, val in zip("xyz", s.omega)},
                "quaternion": {k: float(val) for k, val in zip("wxyz", s.q)},
                "depth": int(round(self.depth * 100))}}
        lat, lng = self.latlng()
        return {"status": "ok", "status_code": "", "type": "10hz", "data": {
            "timestamp": ts,
            "velocity": {k: int(round(float(val) * 100)) for k, val in zip("xyz", s.vel)},
            "longitude": lng, "latitude": lat,
            "attitude": {"pitch": round(math.degrees(pitch), 2), "roll": round(math.degrees(roll), 2),
                         "yaw": round(math.degrees(yaw) % 360, 2)},
            "depth": int(round(self.depth * 100))}}

    # ── SDK dispatch ──────────────────────────────────────────────────────
    def sdk_call(self, cls: str, method: str, args: list, kwargs: dict):
        fn = getattr(self, f"_sdk_{cls}__{method}", None)
        if fn is None:
            return self._sdk_generic(cls, method, args, kwargs)
        return fn(*args, **kwargs)

    def _sdk_generic(self, cls, method, args, kwargs):
        """Setters without simulated effect are accepted and remembered; getters echo them back."""
        key = f"{cls}.{method[4:] if method.startswith(('set_', 'get_')) else method}"
        store = self.camera.params if cls.startswith("QYCamera") or cls.startswith("QyCamera") else self.dvl_switches
        if method.startswith("set_"):
            store[key] = args[-1] if args else kwargs
            return ok()
        if method.startswith("get_"):
            val = store.get(key)
            return ok(str(val) if val is not None else "Default")
        return ok()

    # QYRovControllerManage — set_* return None like the real SDK
    def _sdk_QYRovControllerManage__set_remote_control_status(self, status):
        on = str(status).upper() in ("ON", "TRUE", "1")
        if on and not self.remote_control:
            # take over with the physical RC's current switches, sticks centred
            self.rc_sdk = RCState(**{**self.rc_physical.as_dict(), "left_ud": 1500, "left_lr": 1500,
                                     "right_ud": 1500, "right_lr": 1500, "left_wave": 1500, "right_wave": 1500})
        self.remote_control = on
        self._log("sdk", f"遠端控制 {'ON（實體遙控器停用）' if on else 'OFF（交還遙控器）'}")
        return ok()

    def _rc_set(self, attr, value):
        if attr in ("left_ud", "left_lr", "right_ud", "right_lr", "left_wave", "right_wave"):
            self.rc_sdk.set_channel(attr, value)
        else:
            setattr(self.rc_sdk, attr, int(value))
        return None

    def _sdk_QYRovControllerManage__set_left_joystick_up_down(self, value): return self._rc_set("left_ud", value)
    def _sdk_QYRovControllerManage__set_left_joystick_left_right(self, value): return self._rc_set("left_lr", value)
    def _sdk_QYRovControllerManage__set_right_joystick_up_down(self, value): return self._rc_set("right_ud", value)
    def _sdk_QYRovControllerManage__set_right_joystick_left_right(self, value): return self._rc_set("right_lr", value)
    def _sdk_QYRovControllerManage__set_left_wave_left_right(self, value): return self._rc_set("left_wave", value)
    def _sdk_QYRovControllerManage__set_right_wave_left_right(self, value): return self._rc_set("right_wave", value)
    def _sdk_QYRovControllerManage__set_rc_lock_button(self, value): return self._rc_set("rc_lock", value)
    def _sdk_QYRovControllerManage__set_keep_depth_button(self, value): return self._rc_set("keep_depth", value)
    def _sdk_QYRovControllerManage__set_left_switch(self, value): return self._rc_set("left_switch", value)
    def _sdk_QYRovControllerManage__set_right_switch(self, value): return self._rc_set("right_switch", value)
    def _sdk_QYRovControllerManage__set_record_button(self, value): return self._rc_set("record", value)
    def _sdk_QYRovControllerManage__set_photo_button(self, value): return self._rc_set("photo", value)

    # QYRovParameterManage
    def _sdk_QYRovParameterManage__set_rov_controller_operation(self, operation_mode):
        if operation_mode not in OPERATION_MODES:
            return err("Please pass in the correct parameters")
        self.operation_mode = operation_mode
        return ok()

    def _sdk_QYRovParameterManage__set_throttle_curvature_and_limit(self, curvature, limitation):
        self.shaping.throttle_curvature, self.shaping.throttle_limit, self.shaping.custom = int(curvature), int(limitation), True
        return ok()

    def _sdk_QYRovParameterManage__get_throttle_curvature_and_limit(self):
        return ok(f"curvature={self.shaping.throttle_curvature}, limitation={self.shaping.throttle_limit}")

    def _sdk_QYRovParameterManage__set_rotate_curvature_and_limit(self, curvature, limitation):
        self.shaping.rotate_curvature, self.shaping.rotate_limit, self.shaping.custom = int(curvature), int(limitation), True
        return ok()

    def _sdk_QYRovParameterManage__get_rotate_curvature_and_limit(self):
        return ok(f"curvature={self.shaping.rotate_curvature}, limitation={self.shaping.rotate_limit}")

    def _v6p_only(self, *a, **k):
        return err("Wrong ROV model or parameter")

    _sdk_QYRovParameterManage__set_V6P_led_scale = _v6p_only
    _sdk_QYRovParameterManage__get_V6P_led_scale = _v6p_only
    _sdk_QYRovParameterManage__set_distance_lock_switch = _v6p_only
    _sdk_QYRovParameterManage__set_altitude_lock_switch = _v6p_only
    _sdk_QYRovParameterManage__set_blind_detect_switch = _v6p_only
    _sdk_QYRovParameterManage__set_V6P_laser_switch = _v6p_only

    def _sdk_QYRovParameterManage__set_rov_posture_original(self):
        _, _, yaw = self.vehicle.euler
        self.controller.q_hold = q_from_euler(0.0, 0.0, yaw)
        return ok()

    def _sdk_QYRovParameterManage__get_rov_version(self): return ok("X1-SIM 1.2.1")
    def _sdk_QYRovParameterManage__get_wifi_version(self): return ok("RC-WIFI-SIM 1.0")
    def _sdk_QYRovParameterManage__get_rov_sn(self): return ok("X1SIM00001")

    # QYRovCalibrationManage
    def _sdk_QYRovCalibrationManage__check_cal_status(self):
        if getattr(self, "_cal_until", 0.0) > self.t:
            return ok("Calibration in progress")
        return ok("Cal Done" if getattr(self, "_cal_started", False) else "Not calibration status")

    def _start_cal(self):
        self._cal_started, self._cal_until = True, self.t + 5.0
        return ok()

    _sdk_QYRovCalibrationManage__start_horizontal_gyro_acce_cal = _start_cal
    _sdk_QYRovCalibrationManage__start_vertical_gyro_acce_cal = _start_cal
    _sdk_QYRovCalibrationManage__start_horizontal_mag_cal = _start_cal
    _sdk_QYRovCalibrationManage__start_vertical_mag_cal = _start_cal

    def _sdk_QYRovCalibrationManage__reboot_rov(self):
        self.rc_physical.rc_lock = self.rc_sdk.rc_lock = 1
        self._log("sdk", "ROV 重新開機（電機上鎖）")
        return ok()

    # QYRovAddOnsManage
    def _sdk_QYRovAddOnsManage__set_arm_status(self, status, speed=1):
        self.arm = str(status)
        return ok()

    # QYRovCheckManage
    def _sdk_QYRovCheckManage__ego_self_test(self):
        data = {"temp": 31, "humi": 22, "mos_temp": 38, "exit_upper": 0, "exit_lower": 0,
                "network_5v": 1, "network_3v3": 1, "network_switch": 1, "network_plc": 1, "network_current": 1,
                "spi_flash_comm": 1, "spi_flash_ctrl": 1, "leak": 1, "led_left": 1, "led_right": 1,
                "press": 1, "mag": 1, "six_axis": 1, "temp_humi_temp": 1, "temp_humi_humi": 1, "temp_humi_mos": 1,
                "battery_l_status": 1 if self.battery > 5 else 0, "battery_r_status": 1 if self.battery > 5 else 0,
                "bat_leak_l": 1, "bat_leak_r": 1}
        for fname, idx in MOTOR_FIELDS.items():
            data[fname] = 1 if self.health[idx] > 0.6 else 0
        return {"status": "ok", "status_code": "200", "text": data}

    # QYSDKInfoManage
    def _sdk_QYSDKInfoManage__get_sdk_info(self): return ok("QY_SDK_SIM_V1.2.1")

    # QYRovRealTimeStatusManage / QyRovHighFreqRealTimeStatusManage
    def _sdk_QYRovRealTimeStatusManage__connect_to_rov(self): return ok()
    def _sdk_QYRovRealTimeStatusManage__get_rov_status(self): return self.sdk_status()
    def _sdk_QYRovRealTimeStatusManage__disconnect_rov(self): return None

    def _sdk_QyRovHighFreqRealTimeStatusManage__connect_to_rov(self):
        return {"status": "ok", "status_code": "", "type": "status", "data": "Success"}

    def _sdk_QyRovHighFreqRealTimeStatusManage__get_rov_status(self, which="10hz"):
        return self.hf_status(which)

    def _sdk_QyRovHighFreqRealTimeStatusManage__disconnect_rov(self): return None

    # QYRovNavigationManage
    def _sdk_QYRovNavigationManage__connect(self): return ok("Success", "200")
    def _sdk_QYRovNavigationManage__disconnect(self): return None

    def _sdk_QYRovNavigationManage__init_dr(self, lat=None, lng=None):
        if (lat is None) != (lng is None):
            return err("Please pass in the correct parameters", "400", lat=0, lng=0, yaw=0)
        if self.nav.mode != "IDLE":
            return err("ROV busy", "202", lat=0, lng=0, yaw=0)
        self.nav.init_dr(self.vehicle.s.pos, lat, lng)
        la, ln = self.latlng()
        return {"status": "ok", "status_code": "100", "text": "", "lat": la, "lng": ln,
                "yaw": round(math.degrees(self.yaw) % 360, 2)}

    def _sdk_QYRovNavigationManage__get_navigation_status(self):
        base = {"lat": 0, "lng": 0, "yaw": 0, "dr_ver": 1, "auto_move_status": 0, "auto_move_lm": None}
        if not self.nav.dr_initialized:
            return {"status": "error", "status_code": "201", "text": "Position not initialized", **base}
        la, ln = self.latlng()
        ams = {"H_NAVI": 1, "V_NAVI": 2}.get(self.nav.mode, 0)
        lm = None
        if self.nav.mode == "V_NAVI":
            lm = {"index": self.nav.route_i, "total": len(self.nav.route), **self.nav.v_params}
        return {"status": "ok", "status_code": "100", "text": "", "lat": la, "lng": ln,
                "yaw": round(math.degrees(self.yaw) % 360, 2), "dr_ver": 1,
                "auto_move_status": ams, "auto_move_lm": lm}

    def _sdk_QYRovNavigationManage__get_rov_data(self, req_types=None):
        types = req_types or ["rov", "gps", "dvl", "uqps", "micro_dvl", "usbl"]
        roll, pitch, yaw = self.vehicle.euler
        la, ln = self.latlng()
        s = self.vehicle.s
        alt = self.world.raycast(s.pos, q_rot(s.q, np.array([0, 0, 1.0])), 100.0)
        wv = self.vehicle.world_velocity()
        data = {}
        if "rov" in types:
            data["rov"] = {"depth": round(self.depth, 2), "temperature": round(26 - 0.15 * self.depth, 1),
                           "altitude": round(alt, 2), "yaw": round(math.degrees(yaw) % 360, 2),
                           "pitch": round(math.degrees(pitch), 2), "roll": round(math.degrees(roll), 2),
                           **{k: float(v) for k, v in zip("wxyz", s.q)},
                           "endurance": round(self.battery / 100 * 5000, 0),
                           "power": {"type": "battery", "battery_cap_1": int(self.battery), "battery_cap_2": int(self.battery)}}
        if "gps" in types:
            online = self.depth < 0.3
            data["gps"] = {"online": online, "lat": la if online else 0.0, "lng": ln if online else 0.0, "alt": 0.0,
                           "hdop": 0.9 if online else 99.0, "status": 1 if online else 0,
                           "time": int(time.time() * 1000), "satellite_num": 14 if online else 0}
        if "dvl" in types:
            data["dvl"] = {"online": True, "lat": la, "lng": ln, "alt": round(alt, 2),
                           "x": round(float(s.pos[0]), 2), "y": round(float(s.pos[1]), 2),
                           "vx": round(float(wv[0]), 3), "vy": round(float(wv[1]), 3), "mileage": 0.0,
                           "accuracy": 0.5, "position_valid": self.nav.dr_initialized,
                           "beams": {f"d{i}": round(alt / math.cos(math.radians(22.5)), 2) for i in range(1, 5)}}
        for k in ("uqps", "micro_dvl", "usbl"):
            if k in types:
                data[k] = {"online": False}
        return {"status": "ok", "status_code": "200", "text": "", "data": data}

    def _sdk_QYRovNavigationManage__start_h_navi(self, nav_type, lat, lng, depth=0, idnum=None, u_lat=0, u_lng=0):
        base = {"idnum": 0, "lat": lat, "lng": lng, "depth": depth, "nav_status": 0}
        if str(nav_type).upper() != "DVL":
            return err("Please pass in the correct parameters", "400", **base)
        if self.rc.rc_lock:
            return err("ROV locked", "400", **base)
        if not self.nav.dr_initialized:
            return err("Position not initialized", "201", **base)
        if self.nav.mode == "V_NAVI":
            return err("V_NAVI running", "202", **base)
        self.nav.start_h(float(lat), float(lng), float(depth), self.world.seabed_depth, idnum)
        self._log("nav", f"H_NAVI → {lat:.6f},{lng:.6f} depth {depth}")
        return {"status": "ok", "status_code": "200", "text": "Success", "idnum": self.nav.idnum,
                "lat": lat, "lng": lng, "depth": depth, "nav_status": 1}

    def _sdk_QYRovNavigationManage__stop_h_navi(self):
        self.nav.stop()
        return ok()

    def _sdk_QYRovNavigationManage__set_h_navi_settings(self, accuracy=None, speed=None):
        if speed is not None:
            self.nav.speed = max(0.05, float(speed))
        if accuracy is not None:
            self.nav.accuracy = float(accuracy)
        return ok()

    def _sdk_QYRovNavigationManage__get_h_navi_status(self):
        dist = None
        if self.nav.target is not None:
            dist = round(math.hypot(self.nav.target.n - self.vehicle.s.pos[0], self.nav.target.e - self.vehicle.s.pos[1]), 2)
        return ok(data={
            "float_up_calibrate": {"status": 0},
            "v_navi": {"running": self.nav.mode == "V_NAVI", "index": self.nav.route_i, "total": len(self.nav.route),
                       "paused": self.nav.paused,
                       "status_msg": ("paused" if self.nav.paused else "running") if self.nav.mode == "V_NAVI"
                       else ("finished" if self.nav.nav_status == 2 else "idle")},
            "navigation_status": {"nav_status": self.nav.nav_status, "idnum": self.nav.idnum, "distance": dist,
                                  "mode": self.nav.mode}})

    def _sdk_QYRovNavigationManage__start_v_navi(self, scene, route_type, direction, length, start_depth,
                                                 end_depth, interval, distance, diameter=0.0):
        if self.rc.rc_lock:
            return err("ROV locked")
        if self.nav.mode == "H_NAVI":
            return err("H_NAVI running", "202")
        if str(scene).upper() not in ("GENERAL", "BRIDGE", "TANK") or str(route_type).upper() not in ("LONGITUDINAL", "LATERAL") \
                or str(direction).upper() not in ("LEFT", "RIGHT") or float(interval) <= 0:
            return err("Please pass in the correct parameters")
        self.nav.start_v(self.vehicle.s.pos, self.yaw, scene, route_type, direction, float(length),
                         float(start_depth), float(end_depth), float(interval), float(distance), float(diameter))
        self._log("nav", f"V_NAVI {scene}/{route_type}/{direction} {start_depth}→{end_depth} m, {len(self.nav.route)} 航點")
        return ok()

    def _sdk_QYRovNavigationManage__stop_v_navi(self):
        self.nav.stop()
        return ok()

    def _sdk_QYRovNavigationManage__pause_v_navi(self):
        self.nav.paused = True
        return ok()

    def _sdk_QYRovNavigationManage__resume_v_navi(self):
        self.nav.paused = False
        return ok()

    # QYRovVCCMManage
    def _vccm_precheck(self):
        if self.rc.rc_lock:
            return err("ROV locked")
        if ctrl_mode(self.rc) != "A":
            return err("Mode not A")
        if self.battery < 10:
            return err("Battery low")
        if np.any(self.health < 0.6):
            return err("Motor error")
        return None

    def _sdk_QYRovVCCMManage__connect_vccm(self):
        e = self._vccm_precheck()
        if e:
            return e
        self.nav.vccm_connected = True
        return ok()

    def _sdk_QYRovVCCMManage__disconnect_vccm(self):
        self.nav.vccm_connected = False
        if self.nav.mode == "VCCM":
            self.nav.mode = "IDLE"
        self.nav.vccm_status = "IDLE"
        return None

    def _vccm_cmd(self, status):
        if not self.nav.vccm_connected:
            return err("VCCM not connected", "404")
        e = self._vccm_precheck() if status == "running" else None
        if e:
            self.nav.vccm_error = e["text"]
            return e
        self.nav.vccm_status = status
        self.nav.vccm_error = ""
        if status in ("running", "pause"):
            self.nav.mode = "VCCM"
            self.nav.paused = status == "pause"
        else:
            self.nav.mode, self.nav.paused = "IDLE", False
            self.nav.cruise_speed_dm = 0
        return ok()

    def _sdk_QYRovVCCMManage__start_vccm(self):
        self.nav.cruise_distance_m = 0.0
        return self._vccm_cmd("running")

    def _sdk_QYRovVCCMManage__pause_vccm(self): return self._vccm_cmd("pause")
    def _sdk_QYRovVCCMManage__resume_vccm(self): return self._vccm_cmd("running")
    def _sdk_QYRovVCCMManage__stop_vccm(self): return self._vccm_cmd("IDLE")

    def _sdk_QYRovVCCMManage__get_vccm_status(self):
        if not self.nav.vccm_connected:
            return {"status": "error", "status_code": "404", "text": "VCCM not connected", "vccm_status": "IDLE",
                    "vccm_error": "", "cruise_speed": 0, "cruise_distance": 0}
        return {"status": "ok", "status_code": "200", "text": "Success", "vccm_status": self.nav.vccm_status,
                "vccm_error": self.nav.vccm_error, "cruise_speed": self.nav.cruise_speed_dm,
                "cruise_distance": int(round(self.nav.cruise_distance_m * 10))}

    # Camera
    def _sdk_QyCameraInitManage__camera_init(self, camera_flag): return ok()

    def _sdk_QYCameraWorkModeManage__set_work_mode(self, camera_flag, mode):
        self.camera.work_mode = str(mode)
        return ok()

    def _sdk_QYCameraWorkModeManage__get_work_mode(self, camera_flag): return ok(self.camera.work_mode)

    def _sdk_QYCameraActionManage__start_record(self, camera_flag="MAIN_CAMERA"):
        if self.camera.recording_since is not None:
            return err("Recording already")
        self._start_record()
        return ok()

    def _sdk_QYCameraActionManage__stop_record(self, camera_flag="MAIN_CAMERA"):
        self._stop_record()
        return ok()

    def _sdk_QYCameraActionManage__get_record_status(self, camera_flag="MAIN_CAMERA"):
        if self.camera.recording_since is None:
            return ok("Non recording status")
        return ok(f"Recorded duration: {int(self.t - self.camera.recording_since)}s")

    def _sdk_QYCameraActionManage__take_photo_normal(self, camera_flag="MAIN_CAMERA"):
        self._take_photo()
        return ok()

    def _sdk_QYCameraActionManage__take_photo_during_recording(self, camera_flag="MAIN_CAMERA"):
        if self.camera.recording_since is None:
            return err("Non recording status")
        self._take_photo()
        return ok()

    def _sdk_QYCameraStorageFileManage__get_sd_info(self, camera_flag):
        used = sum(f["size"] for f in self.camera.files) // 1_000_000
        return ok(f"sd_state=SDOK; total=121911 MB; used={used} MB")

    # file indices count from the newest file, as in the SDK docs (index 0 / 1 = newest)
    def _sdk_QYCameraStorageFileManage__get_file_list(self, camera_flag, start_num=0, end_num=5):
        files = self.camera.files[::-1][int(start_num):int(end_num) + 1]
        return ok("".join(f["path"] + ";" for f in files))

    def _sdk_QYCameraStorageFileManage__get_file_info_list(self, camera_flag, start_num=1, end_num=5):
        import json
        files = self.camera.files[::-1][max(0, int(start_num) - 1):int(end_num)]
        return ok(json.dumps([{"path": f["path"], "name": f["name"], "size": str(f["size"]), "time": str(f["time"]),
                               "create": f["create_time"], "create_time": f["create_time"]} for f in files]))

    # QYCameraSystemManage
    def _sdk_QYCameraSystemManage__get_camera_time(self, camera_flag): return ok(time.strftime("%Y%m%d%H%M%S"))
    def _sdk_QYCameraSystemManage__get_camera_version(self, camera_flag): return ok("20260520-SIM")

    def _sdk_QYCameraSystemManage__format_sd(self, camera_flag):
        self.camera.files = []
        return ok()

    def _sdk_QYCameraSystemManage__factory_reset(self, camera_flag):
        self.camera.params = {}
        self.camera.work_mode = "NORMAL_VIDEO_MODE"
        return ok()

    def _sdk_QYCameraStorageFileManage__get_file_count(self, camera_flag):
        return ok(str(len(self.camera.files)))

    def _sdk_QYCameraStorageFileManage__get_single_file_info(self, camera_flag, file_path):
        f = next((f for f in self.camera.files if f["path"] == file_path), None)
        if f is None:
            return err("File not found", "404")
        return ok(f"size={f['size']}; time={f['time']}; create_time={f['create_time']}")

    def _sdk_QYCameraStorageFileManage__delete_single_file(self, camera_flag, file_path):
        n = len(self.camera.files)
        self.camera.files = [f for f in self.camera.files if f["path"] != file_path]
        return ok() if len(self.camera.files) < n else err("File not found", "404")

    def file_pose(self, file_path: str) -> dict | None:
        f = next((f for f in self.camera.files if f["path"] == file_path), None)
        return f["pose"] if f else None

    # ── viewer ─────────────────────────────────────────────────────────────
    def viewer_state(self) -> dict:
        s = self.vehicle.s
        roll, pitch, yaw = self.vehicle.euler
        rc = self.rc
        cur = self.vehicle.current_ned
        return {
            "t": round(self.t, 2), "paused": self.paused,
            "pos": [round(float(x), 3) for x in s.pos], "q": [round(float(x), 5) for x in s.q],
            "euler": [round(math.degrees(roll), 1), round(math.degrees(pitch), 1), round(math.degrees(yaw) % 360, 1)],
            "vel": [round(float(x), 3) for x in s.vel],
            "speed_kn": round(float(np.linalg.norm(s.vel - q_rot(np.array([s.q[0], -s.q[1], -s.q[2], -s.q[3]]), cur))) / KNOT, 2),
            "thrust": [round(float(x) / self.vehicle.p.thruster_max, 3) for x in s.thrust],
            "health": [round(float(h), 2) for h in self.health],
            "rc": rc.as_dict(), "remote_control": self.remote_control, "operation_mode": self.operation_mode,
            "ctrl_mode": ctrl_mode(rc), "locked": bool(rc.rc_lock), "keep_depth": bool(rc.keep_depth),
            "depth_hold": None if self.controller.depth_hold is None else round(self.controller.depth_hold, 2),
            "battery": round(self.battery, 1), "recording": self.camera.recording_since is not None,
            "photos": sum(1 for f in self.camera.files if f["name"].endswith("JPG")),
            "current_here": [round(float(x), 3) for x in cur],
            "current_kn": round(float(np.linalg.norm(cur)) / KNOT, 2),
            "tether": self.tether.state(),
            "events": [e.__dict__ for e in self.world.events[-12:]],
            "damage": self.damage_events[-6:],
            "silt": round(self.world.silt, 2),
            "nav": {"mode": self.nav.mode, "nav_status": self.nav.nav_status, "vccm": self.nav.vccm_status,
                    "route": [[w.n, w.e, w.depth] for w in self.nav.route][:400], "route_i": self.nav.route_i,
                    "target": None if self.nav.target is None else [self.nav.target.n, self.nav.target.e, self.nav.target.depth]},
            "score": self.scorer.as_dict(),
            "log": self.log[-8:],
        }

    def world_description(self) -> dict:
        return {**self.world.as_dict(), "scenario": self.scenario.summary(),
                "spool": list(self.scenario.spool_pos), "start_pos": list(self.scenario.start_pos),
                "catalogue": sc_mod.catalogue(),
                "objectives": [o.as_dict() for o in self.scenario.objectives],
                "thrusters": [{"name": n, "pos": list(p), "axis": list(a)} for n, p, a in THRUSTERS]}

    # ── viewer commands ───────────────────────────────────────────────────
    def apply_viewer_rc(self, msg: dict) -> None:
        for k, val in msg.items():
            if k in ("left_ud", "left_lr", "right_ud", "right_lr", "left_wave", "right_wave"):
                self.rc_physical.set_channel(k, val)
            elif k in ("rc_lock", "keep_depth", "record", "photo", "left_switch", "right_switch"):
                setattr(self.rc_physical, k, int(val))
