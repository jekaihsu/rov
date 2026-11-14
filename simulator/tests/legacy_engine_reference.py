"""Frozen pre-sensor-layer engine paths (main 22ece2a), used only for same-runtime bitwise regression.

``LegacySimulator`` replays the step, controller wiring and every telemetry method exactly as they read
before the shared sensor layer existed. Tests run it next to the current ``Simulator`` with sensor
imperfections disabled and require identical bytes.
"""

from __future__ import annotations

import math
import time

import numpy as np

from qysim.engine import LED_LABEL, Simulator, err
from qysim.mission_modes import ensure_mission
from qysim.expedition import ensure_expedition
from qysim.physics import KNOT, q_rot
from qysim.rc import ctrl_mode, pilot_command
from tests.legacy_sensor_controller_reference import FlightController as LegacyController


class LegacySimulator(Simulator):
    def load_scenario(self, key, seed=None, *, shared_world=None):
        super().load_scenario(key, seed, shared_world=shared_world)
        self.controller = LegacyController(self.vehicle)

    def step(self, dt: float | None = None, *, update_world: bool = True) -> None:
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
        assist = 0 if self.remote_control else rc.assist
        if not locked and (self.nav.mode != "IDLE" or self.nav.hold is not None):
            out = self.nav.step(dt, s.pos, self.yaw, v.world_velocity(), pilot, v.p.vmax[0])
            if out is not None:
                assist = 0
                pilot = {**{k: 0.0 for k in ("surge", "sway", "heave", "roll", "pitch", "yaw")}, **out.cmd}
                heading = out.heading
                if out.depth is not None:
                    keep_depth = True
                    self.controller.depth_hold = out.depth
                    pilot["heave"] = 0.0
                mode = "A"

        self.last_pilot = pilot                    # final command (pilot or autopilot), for recordings
        if update_world:
            self.world.current.step_gust(dt, self.current_rng)
        v.current_ned = self.world.current.sample(s.pos, self.world.seabed_depth, self.t)
        operation_wrench = self.operations.step(dt)
        keep_depth = keep_depth or self.operations.altitude is not None
        v.seabed_depth = self.world.depth_at(s.pos)
        # Provisional simulated bottom-lock window, not a calibrated sensor model.
        altitude = v.seabed_depth - s.pos[2]
        dvl_valid = bool(0.1 <= altitude <= 100.0 and np.all(np.isfinite(v.world_velocity())))
        thr = self.controller.update(dt, pilot, mode, locked, keep_depth, heading, assist,
                                     rc.profile, dvl_valid=dvl_valid) * self.health
        w_tether = self.tether.step(dt, self.t, s.pos, s.q, v.world_velocity())
        n_events = len(self.world.events)
        w_contact = self.world.vehicle_contact(self.t, s.pos, s.q, s.vel, s.omega,
                                               vehicle_id=self.vehicle_id,
                                               hull_spheres=[(centre, self.vehicle.definition.hull_radius)
                                                             for centre in self.vehicle.definition.hull_centres])
        v.step(dt, thr, w_tether + w_contact + self.tool_wrench + operation_wrench)
        if update_world:
            self.world.step(dt, vehicles=[{"id": self.vehicle_id, "pos": s.pos, "vel": v.world_velocity()}])
            from qysim.operations import step_objects
            step_objects(self.world, dt, self.t)
        self._damage(n_events)

        load = float(np.mean(np.abs(s.thrust))) / v.p.thruster_max
        self.battery = max(0.0, self.battery - dt * (0.004 + 0.05 * load ** 1.5))
        self.t += dt
        self.scorer.update(dt, self)
        ensure_mission(self).update(self, dt)
        if self.world.mission_run.mode == "expedition":
            ensure_expedition(self).update(self, dt)

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

    def viewer_state(self) -> dict:
        s = self.vehicle.s
        roll, pitch, yaw = self.vehicle.euler
        rc = self.rc
        cur = self.vehicle.current_ned
        return {
            "vehicle_id": self.vehicle_id, "model_id": self.model_id,
            "appearance": dict(self.appearance),
            "paint_marks": list(self.world.paint_marks),
            "input_latched": self.input_latched, "control_generation": self.control_generation,
            "vehicle": self.vehicle.definition.public(),
            "environment": self.world.environment_state(),
            "operations": self.operations.state(),
            "mission": ensure_mission(self).state(self),
            "expedition": ensure_expedition(self).state(self) if ensure_mission(self).mode == "expedition" else None,
            "t": round(self.t, 2), "paused": self.paused,
            "pos": [round(float(x), 3) for x in s.pos], "q": [round(float(x), 5) for x in s.q],
            "euler": [round(math.degrees(roll), 1), round(math.degrees(pitch), 1), round(math.degrees(yaw) % 360, 1)],
            "vel": [round(float(x), 3) for x in s.vel],
            "speed_kn": round(float(np.linalg.norm(s.vel - q_rot(np.array([s.q[0], -s.q[1], -s.q[2], -s.q[3]]), cur))) / KNOT, 2),
            "thrust": [round(float(x) / self.vehicle.p.thruster_max, 3) for x in s.thrust],
            "health": [round(float(h), 2) for h in self.health],
            "rc": rc.as_dict(), "remote_control": self.remote_control, "operation_mode": self.operation_mode,
            "ctrl_mode": ctrl_mode(rc), "locked": bool(rc.rc_lock), "keep_depth": bool(rc.keep_depth),
            "assist": self.controller.assist_state(),
            "depth_hold": None if self.controller.depth_hold is None else round(self.controller.depth_hold, 2),
            "battery": round(self.battery, 1), "recording": self.camera.recording_since is not None,
            "photos": sum(1 for f in self.camera.files if f["name"].endswith("JPG")),
            "current_here": [round(float(x), 3) for x in cur],
            "current_kn": round(float(np.linalg.norm(cur)) / KNOT, 2),
            "tether": self.tether.state(),
            "events": [e.__dict__ for e in self.world.events if getattr(e, "vehicle_id", "default") == self.vehicle_id][-12:],
            "damage": self.damage_events[-6:],
            "silt": round(self.world.silt_at(s.pos), 2),
            "nav": {"mode": self.nav.mode, "nav_status": self.nav.nav_status, "vccm": self.nav.vccm_status,
                    "route": [[w.n, w.e, w.depth] for w in self.nav.route][:400], "route_i": self.nav.route_i,
                    "target": None if self.nav.target is None else [self.nav.target.n, self.nav.target.e, self.nav.target.depth]},
            "score": ensure_mission(self).score_state(self),
            "log": self.log[-8:],
        }
