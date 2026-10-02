"""Tests for the simulator-backed ``qysea`` mock (simulator/sdk_mock).

A qysim server is started as a subprocess on free ports; every test reloads the
``open_water`` scenario over the viewer WebSocket so tests are independent.

    cd simulator && python -m unittest tests.test_sdk_mock -v
"""

from __future__ import annotations

import inspect
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
MOCK_DIR = SIM_DIR / "sdk_mock"
sys.path.insert(0, str(MOCK_DIR))

from qysea.sdk import _client, _render  # noqa: E402
from qysea.sdk.manage import QY_Camera_Manage, QY_Rov_Manage, QY_RovController_Manage  # noqa: E402
from qysea.sdk.manage.QY_Camera_Manage import (  # noqa: E402
    QYCameraActionManage, QYCameraMediaStreamManage, QYCameraStorageFileManage, QyCameraInitManage)
from qysea.sdk.manage.QY_Rov_Manage import (  # noqa: E402
    QYRovNavigationManage, QYRovRealTimeStatusManage, QYRovVCCMManage, QyRovHighFreqRealTimeStatusManage)
from qysea.sdk.manage.QY_RovController_Manage import QYRovControllerManage  # noqa: E402
from qysea.sdk.manage.QY_SDK_Info_Manage import QYSDKInfoManage  # noqa: E402

M_PER_DEG_LAT = 6378137.0 * math.pi / 180.0


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until(pred, timeout: float, interval: float = 0.2):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = pred()
        if last:
            return last
        time.sleep(interval)
    return last


class MockSDKTest(unittest.TestCase):
    server: subprocess.Popen

    @classmethod
    def setUpClass(cls):
        cls.rpc_port, cls.ws_port = free_port(), free_port()
        cls._env_backup = {k: os.environ.get(k) for k in ("QYSIM_HOST", "QYSIM_RPC_PORT")}
        os.environ["QYSIM_HOST"] = "127.0.0.1"
        os.environ["QYSIM_RPC_PORT"] = str(cls.rpc_port)
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "qysim.server", "--rpc-port", str(cls.rpc_port), "--ws-port", str(cls.ws_port),
             "--no-http", "--scenario", "open_water", "--seed", "1"],
            cwd=str(SIM_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if not wait_until(lambda: _client.get_client().ping(), 60.0):
            cls.server.kill()
            raise RuntimeError("qysim server did not start: " + cls.server.stderr.read().decode(errors="replace"))

    @classmethod
    def tearDownClass(cls):
        _client.get_client().close()
        cls.server.terminate()
        try:
            cls.server.wait(5)
        except subprocess.TimeoutExpired:
            cls.server.kill()
        for k, v in cls._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def setUp(self):
        os.environ["QYSIM_RPC_PORT"] = str(self.rpc_port)
        self.viewer({"type": "scenario", "key": "open_water", "seed": 1})

    def viewer(self, msg: dict) -> None:
        from websockets.sync.client import connect
        with connect(f"ws://127.0.0.1:{self.ws_port}") as ws:
            ws.send(json.dumps({"type": "join", "name": "SDK test fixture",
                                "resume_token": getattr(type(self), "viewer_token", None)}))
            while True:
                reply = json.loads(ws.recv())
                if reply.get("type") == "session":
                    type(self).viewer_token = reply["resume_token"]
                    break
            ws.send(json.dumps(msg))
            while True:
                reply = json.loads(ws.recv())
                if reply.get("type") == "command_result":
                    break
                if reply.get("type") == "error":
                    raise AssertionError(reply)
            ws.send(json.dumps({"type": "leave"}))
            while True:
                reply = json.loads(ws.recv())
                if reply.get("type") == "command_result" and reply.get("action") == "leave":
                    break

    def take_control(self, unlock=True) -> QYRovControllerManage:
        ctrl = QYRovControllerManage()
        self.assertEqual(ctrl.set_remote_control_status("ON")["status"], "ok")
        if unlock:
            self.assertIsNone(ctrl.set_rc_lock_button(0))
        return ctrl

    # ── API surface ────────────────────────────────────────────────────────
    def test_import_paths_and_signatures(self):
        import qysea
        from qysea.sdk.service import QY_RovStatus_Service  # noqa: F401  (vendor sample import)
        self.assertTrue(qysea.IS_QYSIM_MOCK)
        expected = {
            QY_Rov_Manage: ["QYRovParameterManage", "QYRovCalibrationManage", "QYRovRealTimeStatusManage",
                            "QYRovAddOnsManage", "QYRovCheckManage", "QyRovHighFreqRealTimeStatusManage",
                            "QYRovVCCMManage", "QYRovNavigationManage"],
            QY_RovController_Manage: ["QYRovControllerManage"],
            QY_Camera_Manage: ["QyCameraInitManage", "QYCameraWorkModeManage", "QYCameraParameterManage",
                               "QYCameraActionManage", "QYCameraMediaStreamManage", "QYCameraStorageFileManage",
                               "QYCameraSystemManage"],
        }
        for mod, names in expected.items():
            for n in names:
                self.assertTrue(inspect.isclass(getattr(mod, n)), n)
        sig = lambda f: str(inspect.signature(f))
        self.assertEqual(sig(QYRovNavigationManage.start_h_navi),
                         "(self, nav_type, lat, lng, depth=0, idnum=None, u_lat=0, u_lng=0)")
        self.assertEqual(sig(QYRovNavigationManage.start_v_navi),
                         "(self, scene, route_type, direction, length, start_depth, end_depth, interval, distance, "
                         "diameter=0.0)")
        self.assertEqual(sig(QYCameraMediaStreamManage.capture_video),
                         "(self, camera_flag='MAIN_CAMERA', stream_flag='SUB_STREAM')")
        self.assertEqual(sig(QYCameraStorageFileManage.get_file_list), "(self, camera_flag, start_num=0, end_num=5)")
        self.assertEqual(sig(QY_Rov_Manage.QYRovParameterManage.set_blind_detect_switch),
                         "(self, switch_status, detect_distance=None)")
        self.assertEqual(QYSDKInfoManage().get_sdk_info()["status"], "ok")

    # ── connection handling ───────────────────────────────────────────────
    def test_connect_flags(self):
        rt = QYRovRealTimeStatusManage()
        r = rt.get_rov_status()
        self.assertEqual((r["status"], r["text"]), ("error", "Please connect ROV first"))
        self.assertIn("Rov_Attitude_Angle", r)
        self.assertEqual(rt.connect_to_rov()["status"], "ok")
        s = rt.get_rov_status()
        self.assertEqual(s["status"], "ok")
        self.assertIsInstance(s["Depth"], float)
        self.assertIsNone(rt.disconnect_rov())
        self.assertEqual(rt.get_rov_status()["text"], "Please connect ROV first")
        # a second object has its own flag
        self.assertEqual(QYRovRealTimeStatusManage().get_rov_status()["text"], "Please connect ROV first")

        hf = QyRovHighFreqRealTimeStatusManage()
        r = hf.get_rov_status()
        self.assertEqual((r["status"], r["type"]), ("error", "status"))

    def test_server_unreachable_returns_sdk_error(self):
        os.environ["QYSIM_RPC_PORT"] = str(free_port())
        r = QYRovRealTimeStatusManage().connect_to_rov()
        self.assertEqual((r["status"], r["text"]), ("error", "ConnectTimeout"))
        r = QyRovHighFreqRealTimeStatusManage().connect_to_rov()
        self.assertEqual(r["data"], "ConnectTimeout")
        self.assertIsNone(QYRovControllerManage().set_left_joystick_up_down(1600))
        self.assertEqual(QYCameraMediaStreamManage().capture_video(), "Please check the ROV connection")

    def test_reconnects_after_socket_drop(self):
        _client.get_client().close()
        self.assertTrue(_client.get_client().ping())
        _client.get_client()._sock.close()        # simulate a dead connection under the client
        self.assertEqual(QYSDKInfoManage().get_sdk_info()["status"], "ok")

    # ── status ────────────────────────────────────────────────────────────
    def test_high_freq_alternates_packets(self):
        hf = QyRovHighFreqRealTimeStatusManage()
        self.assertEqual(hf.connect_to_rov()["status"], "ok")
        pkts = [hf.get_rov_status() for _ in range(6)]
        self.assertEqual([p["type"] for p in pkts], ["10hz", "50hz"] * 3)
        self.assertIn("velocity", pkts[0]["data"])
        self.assertIn("attitude", pkts[0]["data"])
        self.assertIn("quaternion", pkts[1]["data"])
        self.assertIsNone(hf.disconnect_rov())

    # ── control ───────────────────────────────────────────────────────────
    def test_remote_control_moves_rov(self):
        rt = QYRovRealTimeStatusManage()
        rt.connect_to_rov()
        ctrl = self.take_control()
        heading0 = rt.get_rov_status()["Compass"]
        ctrl.set_right_joystick_up_down(1900)          # ROV_USA: right stick up = forward
        fwd = wait_until(lambda: rt.get_rov_status()["QDVL"]["QDVL_Xspeed"] > 0.3, 8.0)
        self.assertTrue(fwd, "ROV did not move forward")
        ctrl.set_right_joystick_up_down(1500)
        ctrl.set_left_joystick_left_right(1900)        # yaw right
        turned = wait_until(lambda: (rt.get_rov_status()["Compass"] - heading0) % 360 > 20, 8.0)
        ctrl.set_left_joystick_left_right(1500)
        self.assertTrue(turned, "ROV did not turn")
        self.assertEqual(ctrl.set_remote_control_status("OFF")["status"], "ok")

    # ── navigation ────────────────────────────────────────────────────────
    def test_navigation_h_navi_reaches_target(self):
        nav = QYRovNavigationManage()
        self.assertEqual(nav.connect()["status"], "ok")
        self.assertEqual(nav.connect()["text"], "Already connected")
        self.assertEqual(nav.get_navigation_status()["status_code"], "201")
        lat0, lng0 = 22.5, 114.0
        r = nav.init_dr(lat0, lng0)
        self.assertEqual((r["status"], r["status_code"]), ("ok", "100"))
        ns = nav.get_navigation_status()
        self.assertEqual(ns["status_code"], "100")
        self.assertAlmostEqual(ns["lat"], lat0, places=5)
        data = nav.get_rov_data(["rov", "dvl"])
        self.assertIn("rov", data["data"])
        depth = data["data"]["rov"]["depth"]
        target_lat = lat0 + 4.0 / M_PER_DEG_LAT        # 4 m north

        ctrl = QYRovControllerManage()
        ctrl.set_remote_control_status("ON")           # SDK RC starts locked
        r = nav.start_h_navi("DVL", target_lat, lng0, depth=depth)
        self.assertEqual((r["status"], r["text"]), ("error", "ROV locked"))
        ctrl.set_rc_lock_button(0)
        self.assertEqual(nav.set_h_navi_settings(speed=1.0)["status"], "ok")
        r = nav.start_h_navi("DVL", target_lat, lng0, depth=depth)
        self.assertEqual(r["status"], "ok", r)
        self.assertEqual(nav.get_navigation_status()["auto_move_status"], 1)
        arrived = wait_until(
            lambda: nav.get_h_navi_status()["data"]["navigation_status"]["nav_status"] == 2, 60.0, 0.5)
        self.assertTrue(arrived, nav.get_h_navi_status())
        ns = nav.get_navigation_status()
        self.assertLess(abs(ns["lat"] - target_lat) * M_PER_DEG_LAT, 0.6)
        self.assertIsNone(nav.disconnect())

    # ── VCCM ──────────────────────────────────────────────────────────────
    def test_vccm_prechecks(self):
        vccm = QYRovVCCMManage()
        self.assertEqual(vccm.get_vccm_status()["text"], "VCCM not connected")
        ctrl = self.take_control(unlock=False)
        self.assertEqual(vccm.connect_vccm()["text"], "ROV locked")
        ctrl.set_rc_lock_button(0)
        ctrl.set_left_switch(1)                        # S mode
        self.assertEqual(vccm.connect_vccm()["text"], "Mode not A")
        ctrl.set_left_switch(0)
        self.assertEqual(vccm.connect_vccm()["status"], "ok")
        self.assertEqual(vccm.start_vccm()["status"], "ok")
        self.assertEqual(vccm.get_vccm_status()["vccm_status"], "running")
        self.assertEqual(vccm.pause_vccm()["status"], "ok")
        self.assertEqual(vccm.get_vccm_status()["vccm_status"], "pause")
        self.assertEqual(vccm.stop_vccm()["status"], "ok")
        self.assertIsNone(vccm.disconnect_vccm())

    # ── camera ────────────────────────────────────────────────────────────
    def test_camera_stream(self):
        self.assertEqual(QyCameraInitManage().camera_init("MAIN_CAMERA")["status"], "ok")
        cam = QYCameraMediaStreamManage()
        self.assertEqual(cam.get_frame(), "please run capture video")
        self.assertEqual(cam.get_w_h(), "please run capture video")
        self.assertEqual(cam.capture_video("main_camera"), "please pass in the correct camera type")
        self.assertEqual(cam.capture_video("MAIN_CAMERA", "X"), "please pass in the correct stream parameters")
        self.assertIs(cam.capture_video("MAIN_CAMERA", "SUB_STREAM"), True)
        self.assertEqual(cam.get_w_h(), "640.0 * 360.0")
        t0 = time.time()
        for _ in range(5):
            ok, frame = cam.get_frame()
        fps = 5 / (time.time() - t0)
        self.assertIs(ok, True)
        self.assertEqual((frame.shape, str(frame.dtype)), ((360, 640, 3), "uint8"))
        self.assertGreater(fps, 5.0)
        self.assertIsNone(cam.close_video())
        self.assertEqual(cam.close_video(), "please run capture video")

    def test_led_brightens_deep_frames(self):
        view = _client.get_client().camera_view()
        pose = {"n": 0.0, "e": 0.0, "depth": 20.0, "yaw": 0.0}
        view = {**view, "led": 0}
        dark = _render.render(view, pose=pose, osd=False, t_now=1.0).mean()
        lit = _render.render({**view, "led": 2}, pose=pose, osd=False, t_now=1.0).mean()
        shallow = _render.render(view, pose={**pose, "depth": 2.0}, osd=False, t_now=1.0).mean()
        self.assertGreater(lit, dark)
        self.assertGreater(shallow, dark)

    def test_photo_download_writes_jpeg(self):
        has_encoder = _render.cv2 is not None
        try:
            import PIL  # noqa: F401
            has_encoder = True
        except ImportError:
            pass
        act, st = QYCameraActionManage(), QYCameraStorageFileManage()
        self.assertEqual(st.get_download_status("MAIN_CAMERA")["text"], "No file downloaded")
        self.assertEqual(act.take_photo_normal("MAIN_CAMERA")["status"], "ok")
        files = st.get_file_list("MAIN_CAMERA")["text"]
        self.assertRegex(files, r"sd/DCIM/100MEDIA/SING\d{4}\.JPG;")
        info = st.get_file_info_list("MAIN_CAMERA", start_num=1, end_num=5)
        path = json.loads(info["text"])[0]["path"]
        self.assertEqual(info["text"][0]["path"], path)          # vendor-sample style indexing
        self.assertEqual(st.download_file("MAIN_CAMERA", "sd/DCIM/100MEDIA/NOPE.JPG", "/tmp")["status"], "error")
        out = tempfile.mkdtemp(prefix="qysim_dl_")
        try:
            r = st.download_file("MAIN_CAMERA", path, out)
            self.assertEqual((r["status"], r["text"]), ("ok", "Preparing to download file"))
            done = wait_until(lambda: (lambda t: t if ("successfully" in t or "error" in t) else None)(
                st.get_download_status("MAIN_CAMERA")["text"]), 20.0)
            if not has_encoder:
                self.assertIn("DownloadFile error", done)
                return
            self.assertIn("successfully", done)
            target = Path(out) / Path(path).name
            self.assertTrue(target.exists())
            self.assertEqual(target.read_bytes()[:2], b"\xff\xd8")
        finally:
            shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
