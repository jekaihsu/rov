"""Mock of the ROV manage layer (parameters, calibration, status, add-ons, self-test,
high-frequency status, VCCM and navigation). Every call is forwarded to the qysim
simulator; see ``simulator/PROTOCOL.md``.
"""

import threading
import time

from qysea.sdk._client import Remote, fail_none, sdk_error


class QYRovParameterManage(Remote):
    """ROV parameters: stick mapping, curves, sonar/DVL switches, versions."""

    _CLS = "QYRovParameterManage"

    def set_rov_controller_operation(self, operation_mode):
        return self._call("set_rov_controller_operation", operation_mode)

    def set_throttle_curvature_and_limit(self, curvature, limitation):
        return self._call("set_throttle_curvature_and_limit", curvature, limitation)

    def get_throttle_curvature_and_limit(self):
        return self._call("get_throttle_curvature_and_limit")

    def set_rotate_curvature_and_limit(self, curvature, limitation):
        return self._call("set_rotate_curvature_and_limit", curvature, limitation)

    def get_rotate_curvature_and_limit(self):
        return self._call("get_rotate_curvature_and_limit")

    def set_V6P_led_scale(self, value):
        return self._call("set_V6P_led_scale", value)

    def get_V6P_led_scale(self):
        return self._call("get_V6P_led_scale")

    def set_distance_lock_switch(self, switch_status):
        return self._call("set_distance_lock_switch", switch_status)

    def set_altitude_lock_switch(self, switch_status):
        return self._call("set_altitude_lock_switch", switch_status)

    def set_blind_detect_switch(self, switch_status, detect_distance=None):
        return self._call("set_blind_detect_switch", switch_status, detect_distance)

    def set_V6P_laser_switch(self, switch_status):
        return self._call("set_V6P_laser_switch", switch_status)

    def set_rov_posture_original(self):
        return self._call("set_rov_posture_original")

    def get_rov_version(self):
        return self._call("get_rov_version")

    def get_wifi_version(self):
        return self._call("get_wifi_version")

    def get_rov_sn(self):
        return self._call("get_rov_sn")

    def set_qdvl_station_lock_switch(self, switch_status):
        return self._call("set_qdvl_station_lock_switch", switch_status)

    def get_qdvl_station_lock_switch(self):
        return self._call("get_qdvl_station_lock_switch")

    def set_microdvl_station_lock_switch(self, switch_status):
        return self._call("set_microdvl_station_lock_switch", switch_status)

    def get_microdvl_station_lock_switch(self):
        return self._call("get_microdvl_station_lock_switch")

    def set_microdvl_blind_detect_switch(self, switch_status, distance=0):
        return self._call("set_microdvl_blind_detect_switch", switch_status, distance)

    def get_microdvl_blind_detect_switch(self):
        return self._call("get_microdvl_blind_detect_switch")

    def set_microdvl_distance_lock_switch(self, switch_status):
        return self._call("set_microdvl_distance_lock_switch", switch_status)

    def get_microdvl_distance_lock_switch(self):
        return self._call("get_microdvl_distance_lock_switch")

    def set_microdvl_detection_range(self, range_mode):
        return self._call("set_microdvl_detection_range", range_mode)

    def get_microdvl_detection_range(self):
        return self._call("get_microdvl_detection_range")

    def set_microdvl_laser_switch(self, switch_status):
        return self._call("set_microdvl_laser_switch", switch_status)

    def get_microdvl_laser_switch(self):
        return self._call("get_microdvl_laser_switch")

    def set_microdvl_yaw(self, switch_status):
        return self._call("set_microdvl_yaw", switch_status)

    def get_microdvl_yaw(self):
        return self._call("get_microdvl_yaw")

    def set_qdvl_altitude_limit_switch(self, switch_status, distance=0):
        return self._call("set_qdvl_altitude_limit_switch", switch_status, distance)

    def get_qdvl_altitude_limit_switch(self):
        return self._call("get_qdvl_altitude_limit_switch")

    def set_qdvl_terrain_follow_switch(self, switch_status):
        return self._call("set_qdvl_terrain_follow_switch", switch_status)

    def get_qdvl_terrain_follow_switch(self):
        return self._call("get_qdvl_terrain_follow_switch")

    def set_qdvl_pitch_angle_limit(self, switch_status, angle=0):
        return self._call("set_qdvl_pitch_angle_limit", switch_status, angle)

    def get_qdvl_pitch_angle_limit(self):
        return self._call("get_qdvl_pitch_angle_limit")

    def set_qdvl_detection_range(self, range_mode):
        return self._call("set_qdvl_detection_range", range_mode)

    def get_qdvl_detection_range(self):
        return self._call("get_qdvl_detection_range")


class QYRovCalibrationManage(Remote):
    """IMU / compass calibration steps and reboot."""

    _CLS = "QYRovCalibrationManage"

    def check_cal_status(self):
        return self._call("check_cal_status")

    def start_horizontal_gyro_acce_cal(self):
        return self._call("start_horizontal_gyro_acce_cal")

    def start_vertical_gyro_acce_cal(self):
        return self._call("start_vertical_gyro_acce_cal")

    def start_horizontal_mag_cal(self):
        return self._call("start_horizontal_mag_cal")

    def start_vertical_mag_cal(self):
        return self._call("start_vertical_mag_cal")

    def reboot_rov(self):
        return self._call("reboot_rov")


def _status_skeleton(status: str, code: str, text: str) -> dict:
    """``get_rov_status`` dict with every field present but empty (used for errors)."""
    acc = ("Manipulator_Status", "Water_Sampler_Status", "Mud_Sampler_Status", "DL_Status", "AL_Status",
           "SL_Status", "DL_AL_Status", "DL_SL_Status", "AL_SL_Status", "Laser_Status", "Laser_DL_Status",
           "Laser_AL_Status", "Laser_DL_AL_Status", "DVL_Status", "Image_Sonar_Status", "QCamera_Status",
           "pH_Sensor_Status", "Salt_Sensorr_Status", "NTU_Sensor_Status", "Do_Sensor_Status", "OPSS_Status",
           "Metal_Detector_Status")
    dvl = lambda p: {f"{p}_{k}": "" for k in ("Xspeed", "Yspeed", "Zspeed", "Altitude")}
    return {
        "status": status, "status_code": code, "text": text,
        "Battery": "Left: 0, Right: 0", "Temp": "", "Depth": "", "Compass": "",
        "Rov_Attitude_Angle": {"Pitch": "", "Yaw": "", "Roll": ""},
        "RC_Switch_Status": {k: "" for k in ("RC_Lock", "Depth_Keeping", "Record", "Photo", "Rov_Ctrl_Limit",
                                             "Rov_Operation_Mode", "Rov_Ctrl_Mode", "LED")},
        "Sonar_Application_Status": {k: "" for k in ("Laser_Status", "Distance_Lock_Status",
                                                     "Blind_Detect_Status", "Altitude_Lock_Status")},
        "Distance": "", "Altitude": "",
        "Accessories_Status": {k: "" for k in acc},
        "A50DVL": dvl("A50DVL"), "QDVL": dvl("QDVL"), "MicroDVL": dvl("MicroDVL"),
        "QCamDVL": {**dvl("QCamDVL"), "station_lock_status": "", "fpvc_status": "",
                    "installation_direction_status": "", "q_led_status": "", "q_laser_status": ""},
        "rov_type": "",
    }


class QYRovRealTimeStatusManage(Remote):
    """Low-rate status (poll every ~500 ms). ``connect_to_rov`` first."""

    _CLS = "QYRovRealTimeStatusManage"

    def __init__(self):
        self._connected = False

    def connect_to_rov(self):
        r = self._call("connect_to_rov")
        self._connected = isinstance(r, dict) and r.get("status") == "ok"
        return r

    def get_rov_status(self):
        if not self._connected:
            return _status_skeleton("error", "", "Please connect ROV first")
        return self._call("get_rov_status", on_fail=lambda text, code: _status_skeleton("error", code, text))

    def disconnect_rov(self):
        self._connected = False
        self._call("disconnect_rov", on_fail=fail_none)
        return None


class QYRovAddOnsManage(Remote):
    """Accessories (manipulator arm)."""

    _CLS = "QYRovAddOnsManage"

    def set_arm_status(self, status, speed=1):
        return self._call("set_arm_status", status, speed)


class QYRovCheckManage(Remote):
    """Self test."""

    _CLS = "QYRovCheckManage"

    def ego_self_test(self):
        return self._call("ego_self_test")


def _hf_error(text, code="408"):
    return {"status": "error", "status_code": code, "type": "status", "data": text}


class QyRovHighFreqRealTimeStatusManage(Remote):
    """High-rate status stream: each ``get_rov_status`` returns the next packet,
    alternating ``10hz`` (velocity/position/attitude) and ``50hz`` (IMU) packets."""

    _CLS = "QyRovHighFreqRealTimeStatusManage"
    PACKET_INTERVAL = 1.0 / 60.0          # real stream: 10 + 50 packets per second

    def __init__(self):
        self._connected = False
        self._next = "10hz"
        self._last = 0.0
        self._lock = threading.Lock()

    def connect_to_rov(self):
        r = self._call("connect_to_rov", on_fail=_hf_error)
        self._connected = isinstance(r, dict) and r.get("status") == "ok"
        return r

    def get_rov_status(self):
        if not self._connected:
            return _hf_error("Please try again or check rov connect", "")
        with self._lock:                  # behave like a blocking stream read
            wait = self._last + self.PACKET_INTERVAL - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            which = self._next
            self._next = "50hz" if which == "10hz" else "10hz"
            self._last = time.monotonic()
        return self._call("get_rov_status", which, on_fail=_hf_error)

    def disconnect_rov(self):
        self._connected = False
        self._call("disconnect_rov", on_fail=fail_none)
        return None


class QYRovVCCMManage(Remote):
    """Vertical cruise (VCCM)."""

    _CLS = "QYRovVCCMManage"

    def connect_vccm(self):
        return self._call("connect_vccm")

    def disconnect_vccm(self):
        self._call("disconnect_vccm", on_fail=fail_none)
        return None

    def start_vccm(self):
        return self._call("start_vccm")

    def pause_vccm(self):
        return self._call("pause_vccm")

    def resume_vccm(self):
        return self._call("resume_vccm")

    def stop_vccm(self):
        return self._call("stop_vccm")

    def get_vccm_status(self):
        return self._call("get_vccm_status", on_fail=lambda text, code: sdk_error(
            text, code, vccm_status="IDLE", vccm_error="", cruise_speed=0, cruise_distance=0))


def _nav_fail(**extra):
    return lambda text, code: sdk_error(text, code, **extra)


class QYRovNavigationManage(Remote):
    """Navigation: DR, sensor data, horizontal (H_NAVI) and facade (V_NAVI) auto-navigation."""

    _CLS = "QYRovNavigationManage"

    def __init__(self):
        self._connected = False

    def connect(self):
        if self._connected:
            return {"status": "ok", "status_code": "200", "text": "Already connected"}
        r = self._call("connect")
        self._connected = isinstance(r, dict) and r.get("status") == "ok"
        return r

    def disconnect(self):
        self._connected = False
        self._call("disconnect", on_fail=fail_none)
        return None

    def init_dr(self, lat=None, lng=None):
        return self._call("init_dr", lat, lng, on_fail=_nav_fail(lat=0, lng=0, yaw=0))

    def get_navigation_status(self):
        return self._call("get_navigation_status", on_fail=_nav_fail(
            lat=0, lng=0, yaw=0, dr_ver=0, auto_move_status=0, auto_move_lm=None))

    def get_rov_data(self, req_types=None):
        return self._call("get_rov_data", req_types, on_fail=_nav_fail(data={}))

    def start_h_navi(self, nav_type, lat, lng, depth=0, idnum=None, u_lat=0, u_lng=0):
        return self._call("start_h_navi", nav_type, lat, lng, depth, idnum, u_lat, u_lng,
                          on_fail=_nav_fail(idnum=0, lat=lat, lng=lng, depth=depth, nav_status=0))

    def stop_h_navi(self):
        return self._call("stop_h_navi")

    def set_h_navi_settings(self, accuracy=None, speed=None):
        return self._call("set_h_navi_settings", accuracy, speed)

    def get_h_navi_status(self):
        return self._call("get_h_navi_status", on_fail=_nav_fail(data={}))

    def start_v_navi(self, scene, route_type, direction, length, start_depth, end_depth, interval, distance,
                     diameter=0.0):
        return self._call("start_v_navi", scene, route_type, direction, length, start_depth, end_depth,
                          interval, distance, diameter)

    def stop_v_navi(self):
        return self._call("stop_v_navi")

    def pause_v_navi(self):
        return self._call("pause_v_navi")

    def resume_v_navi(self):
        return self._call("resume_v_navi")
