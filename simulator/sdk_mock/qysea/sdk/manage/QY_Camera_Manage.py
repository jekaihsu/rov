"""Mock of the camera manage layer: init, work mode, parameters, actions, live stream,
SD-card files and system settings.

Live frames and downloaded photos are rendered locally from the simulator's
``camera_view`` (see ``qysea.sdk._render``); everything else is forwarded to the
simulator.

Environment:
    QYSIM_CAMERA_FPS   maximum live frame rate of ``get_frame`` (default 15)
"""

import json
import os
import sys
import threading
import time

from qysea.sdk import _render
from qysea.sdk._client import Remote, SimError, SimUnavailable, get_client, sdk_error

CAMERA_FLAGS = ("MAIN_CAMERA", "SUB_CAMERA", "V6P_QCAMERA", "W6_QCAMERA")
STREAM_SIZE = {"SUB_STREAM": (640, 360), "MAIN_STREAM": (1280, 720)}
PHOTO_SIZE, PHOTO_INTERNAL = (1920, 1080), (320, 180)
VIDEO_SIZE, VIDEO_FRAMES, VIDEO_FPS = (1280, 720), 20, 10.0


class QyCameraInitManage(Remote):
    """Camera initialisation (call once before other camera APIs)."""

    _CLS = "QyCameraInitManage"

    def camera_init(self, camera_flag):
        return self._call("camera_init", camera_flag)


class QYCameraWorkModeManage(Remote):
    """Camera work mode (video / photo variants)."""

    _CLS = "QYCameraWorkModeManage"

    def set_work_mode(self, camera_flag, mode):
        return self._call("set_work_mode", camera_flag, mode)

    def get_work_mode(self, camera_flag):
        return self._call("get_work_mode", camera_flag)


class QYCameraParameterManage(Remote):
    """Camera image parameters. The simulator stores them and echoes them back."""

    _CLS = "QYCameraParameterManage"

    def set_video_main_stream_resolution(self, camera_flag, mode, value):
        return self._call("set_video_main_stream_resolution", camera_flag, mode, value)

    def set_photo_resolution(self, camera_flag, mode, value):
        return self._call("set_photo_resolution", camera_flag, mode, value)

    def get_video_resolution(self, camera_flag, mode):
        return self._call("get_video_resolution", camera_flag, mode)

    def get_photo_resolution(self, camera_flag, mode):
        return self._call("get_photo_resolution", camera_flag, mode)

    def set_video_sub_stream_resolution(self, camera_flag, value):
        return self._call("set_video_sub_stream_resolution", camera_flag, value)

    def get_video_sub_stream_resolution(self, camera_flag):
        return self._call("get_video_sub_stream_resolution", camera_flag)

    def set_video_sub_stream_bitrate(self, camera_flag, value):
        return self._call("set_video_sub_stream_bitrate", camera_flag, value)

    def get_video_sub_stream_bitrate(self, camera_flag):
        return self._call("get_video_sub_stream_bitrate", camera_flag)

    def set_video_encode_type(self, camera_flag, mode, encode_type):
        return self._call("set_video_encode_type", camera_flag, mode, encode_type)

    def get_video_encode_type(self, camera_flag, mode):
        return self._call("get_video_encode_type", camera_flag, mode)

    def set_video_standard(self, camera_flag, value):
        return self._call("set_video_standard", camera_flag, value)

    def get_video_standard(self, camera_flag):
        return self._call("get_video_standard", camera_flag)

    def set_video_metering_mode(self, camera_flag, mode, value):
        return self._call("set_video_metering_mode", camera_flag, mode, value)

    def set_photo_metering_mode(self, camera_flag, mode, value):
        return self._call("set_photo_metering_mode", camera_flag, mode, value)

    def get_video_metering_mode(self, camera_flag, mode):
        return self._call("get_video_metering_mode", camera_flag, mode)

    def get_photo_metering_mode(self, camera_flag, mode):
        return self._call("get_photo_metering_mode", camera_flag, mode)

    def set_video_iso(self, camera_flag, mode, value):
        return self._call("set_video_iso", camera_flag, mode, value)

    def set_photo_iso(self, camera_flag, mode, value):
        return self._call("set_photo_iso", camera_flag, mode, value)

    def get_video_iso(self, camera_flag, mode):
        return self._call("get_video_iso", camera_flag, mode)

    def get_photo_iso(self, camera_flag, mode):
        return self._call("get_photo_iso", camera_flag, mode)

    def set_video_exposure(self, camera_flag, mode, value):
        return self._call("set_video_exposure", camera_flag, mode, value)

    def set_photo_exposure(self, camera_flag, mode, value):
        return self._call("set_photo_exposure", camera_flag, mode, value)

    def get_video_exposure(self, camera_flag, mode):
        return self._call("get_video_exposure", camera_flag, mode)

    def get_photo_exposure(self, camera_flag, mode):
        return self._call("get_photo_exposure", camera_flag, mode)

    def set_video_white_balance(self, camera_flag, mode, value):
        return self._call("set_video_white_balance", camera_flag, mode, value)

    def set_photo_white_balance(self, camera_flag, mode, value):
        return self._call("set_photo_white_balance", camera_flag, mode, value)

    def get_video_white_balance(self, camera_flag, mode):
        return self._call("get_video_white_balance", camera_flag, mode)

    def get_photo_white_balance(self, camera_flag, mode):
        return self._call("get_photo_white_balance", camera_flag, mode)

    def set_photo_shutter(self, camera_flag, mode, value):
        return self._call("set_photo_shutter", camera_flag, mode, value)

    def get_photo_shutter(self, camera_flag, mode):
        return self._call("get_photo_shutter", camera_flag, mode)

    def set_burst_rate(self, camera_flag, value):
        return self._call("set_burst_rate", camera_flag, value)

    def get_burst_rate(self, camera_flag):
        return self._call("get_burst_rate", camera_flag)


class QYCameraActionManage(Remote):
    """Record / photo actions."""

    _CLS = "QYCameraActionManage"

    def start_record(self, camera_flag="MAIN_CAMERA"):
        return self._call("start_record", camera_flag)

    def stop_record(self, camera_flag="MAIN_CAMERA"):
        return self._call("stop_record", camera_flag)

    def get_record_status(self, camera_flag="MAIN_CAMERA"):
        return self._call("get_record_status", camera_flag)

    def take_photo_during_recording(self, camera_flag="MAIN_CAMERA"):
        return self._call("take_photo_during_recording", camera_flag)

    def take_photo_normal(self, camera_flag="MAIN_CAMERA"):
        return self._call("take_photo_normal", camera_flag)


_NOT_CAPTURING = "please run capture video"
_NO_X = "On Linux, 'show_video' funtion uses X, so the following must be true: An X server must be running."


class QYCameraMediaStreamManage:
    """Live video: ``capture_video`` then loop ``get_frame`` -> ``(True, BGR ndarray)``;
    ``close_video`` when done. Frames are synthesised from the simulator scene."""

    def __init__(self):
        self._size = None
        self._lock = threading.Lock()
        self._last = 0.0
        self._fps = max(1.0, float(os.environ.get("QYSIM_CAMERA_FPS", "15")))

    def capture_video(self, camera_flag="MAIN_CAMERA", stream_flag="SUB_STREAM"):
        if camera_flag not in CAMERA_FLAGS:
            return "please pass in the correct camera type"
        if stream_flag not in STREAM_SIZE:
            return "please pass in the correct stream parameters"
        if not get_client().ping():
            return "Please check the ROV connection"
        self._size = STREAM_SIZE[stream_flag]
        self._last = 0.0
        return True

    def get_frame(self):
        size = self._size
        if size is None:
            return _NOT_CAPTURING
        with self._lock:                  # pace like a real stream: block until the next frame slot
            wait = self._last + 1.0 / self._fps - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
        try:
            view = get_client().camera_view()
        except (SimUnavailable, SimError):
            return False, None
        return True, _render.render(view, size[0], size[1])

    def get_w_h(self):
        if self._size is None:
            return _NOT_CAPTURING
        return f"{float(self._size[0])} * {float(self._size[1])}"

    def show_video(self):
        if self._size is None:
            return _NOT_CAPTURING
        cv2 = _render.cv2
        if cv2 is None or (sys.platform.startswith("linux") and not os.environ.get("DISPLAY")):
            return _NO_X
        window = "QYSim camera"
        try:
            while self._size is not None:
                got = self.get_frame()
                if not (isinstance(got, tuple) and got[0] is True):
                    break
                cv2.imshow(window, got[1])
                if cv2.waitKey(1) & 0xFF == 27:           # Esc
                    break
        except cv2.error:
            return _NO_X
        finally:
            try:
                cv2.destroyWindow(window)
            except Exception:
                pass
        return None

    def close_video(self):
        if self._size is None:
            return _NOT_CAPTURING
        self._size = None
        return None


class _JsonText(str):
    """JSON text of a file list that can also be indexed like the decoded list
    (``text[0]['path']``) as some vendor samples do. ``json.loads(text)`` still works."""

    def __new__(cls, text, items):
        obj = super().__new__(cls, text)
        obj._items = items
        return obj

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._items[key]
        return str.__getitem__(self, key)


_downloads: dict = {}                    # camera_flag -> status text
_downloads_lock = threading.Lock()


def _set_download(flag, text):
    with _downloads_lock:
        _downloads[flag] = text


def _download_worker(flag, file_path, target, view, pose):
    _set_download(flag, "File downloading")
    try:
        if file_path.upper().endswith((".JPG", ".JPEG")):
            img = _render.render(view, *PHOTO_SIZE, internal=PHOTO_INTERNAL, pose=pose)
            _render.write_jpeg(target, img)
        else:
            t0 = time.time()
            frames = [_render.render(view, *VIDEO_SIZE, pose=pose, t_now=t0 + i / VIDEO_FPS)
                      for i in range(VIDEO_FRAMES)]
            _render.write_video(target, frames, VIDEO_FPS)
        mb = os.path.getsize(target) / 1048576.0
        _set_download(flag, f"File downloaded successfully, file_size: {mb:.2f} MB")
    except Exception as e:                # report like the SDK, never raise in the worker
        _set_download(flag, f"DownloadFile error: {type(e).__name__}: {e}")


class QYCameraStorageFileManage(Remote):
    """SD-card files. ``download_file`` renders the file's stored pose into ``dir_path``
    (JPEG for photos, a short MP4 for videos when OpenCV is available)."""

    _CLS = "QYCameraStorageFileManage"

    def get_sd_info(self, camera_flag):
        return self._call("get_sd_info", camera_flag)

    def get_file_list(self, camera_flag, start_num=0, end_num=5):
        return self._call("get_file_list", camera_flag, start_num, end_num)

    def get_file_info_list(self, camera_flag, start_num=1, end_num=5):
        r = self._call("get_file_info_list", camera_flag, start_num, end_num)
        if isinstance(r, dict) and r.get("status") == "ok" and isinstance(r.get("text"), str):
            try:
                items = json.loads(r["text"])
            except ValueError:
                items = None
            if isinstance(items, list):
                r["text"] = _JsonText(r["text"], items)
        return r

    def get_file_count(self, camera_flag):
        return self._call("get_file_count", camera_flag)

    def get_single_file_info(self, camera_flag, file_path):
        return self._call("get_single_file_info", camera_flag, file_path)

    def download_file(self, camera_flag, file_path, dir_path):
        if camera_flag not in CAMERA_FLAGS or not isinstance(file_path, str) or not file_path \
                or not isinstance(dir_path, str) or not dir_path:
            return sdk_error("Please pass in the correct parameters", "400")
        try:
            view = get_client().camera_view(file_path)
        except SimUnavailable as e:
            return sdk_error(e.kind, "408")
        except SimError as e:
            return sdk_error(f"SimulatorError: {e}", "500")
        pose = view.get("pose")
        if not pose:
            return sdk_error("Please pass in the correct parameters", "400")
        try:
            os.makedirs(dir_path, exist_ok=True)
        except OSError:
            return sdk_error("Dir creation failed", "400")
        target = os.path.join(dir_path, os.path.basename(file_path))
        _set_download(camera_flag, "Preparing to download file")
        threading.Thread(target=_download_worker, args=(camera_flag, file_path, target, view, pose),
                         name="qysim-download", daemon=True).start()
        return {"status": "ok", "status_code": "200", "text": "Preparing to download file"}

    def get_download_status(self, camera_flag):
        if camera_flag not in CAMERA_FLAGS:
            return sdk_error("Please pass in the correct parameters", "400")
        with _downloads_lock:
            text = _downloads.get(camera_flag, "No file downloaded")
        if text.startswith("DownloadFile error"):
            return sdk_error(text, "500")
        return {"status": "ok", "status_code": "200", "text": text}

    def delete_single_file(self, camera_flag, file_path):
        return self._call("delete_single_file", camera_flag, file_path)


class QYCameraSystemManage(Remote):
    """Camera system: factory reset, SD format, time, version, watermarks."""

    _CLS = "QYCameraSystemManage"

    def factory_reset(self, camera_flag):
        return self._call("factory_reset", camera_flag)

    def format_sd(self, camera_flag):
        return self._call("format_sd", camera_flag)

    def get_camera_time(self, camera_flag):
        return self._call("get_camera_time", camera_flag)

    def get_camera_version(self, camera_flag):
        return self._call("get_camera_version", camera_flag)

    def time_stamp_switch(self, camera_flag, status):
        return self._call("time_stamp_switch", camera_flag, status)

    def logo_stamp_switch(self, camera_flag, status):
        return self._call("logo_stamp_switch", camera_flag, status)
