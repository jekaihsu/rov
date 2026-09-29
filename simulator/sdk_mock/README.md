# qysea mock (simulator-backed SDK)

A pure-Python stand-in for the QYSea OpenSDK `qysea` package. It has the same modules, classes and
method signatures as `qysea.sdk.manage.*` (V1.2.1) and forwards every call to the qysim simulator.
Existing tools run unchanged as long as they import this `qysea` instead of the vendor one.
Only numpy is required. OpenCV (`opencv-python-headless`) or Pillow is needed to write downloaded photos.
OpenCV also gives smoother frames, the OSD line, `show_video` and MP4 downloads.

## Use it

```bash
cd simulator && python -m qysim.server            # SDK RPC on 127.0.0.1:9760
export PYTHONPATH=/path/to/rov/simulator/sdk_mock  # Windows: set PYTHONPATH=...\simulator\sdk_mock
python my_tool.py                                  # from qysea.sdk.manage.QY_Rov_Manage import ...
```

Tools that locate the SDK themselves (`rov_gamepad.py`, `sdk_tester.py` walk up from their own folder
to the first directory containing `qysea/sdk`, then `os.chdir` there) will pick the **vendor** SDK
if they sit inside the vendor tree. Run them from outside the vendor tree (then PYTHONPATH applies).
You can also put a `qysea` symlink or copy of `sdk_mock/qysea` next to the tool.
`qysea.IS_QYSIM_MOCK` is `True` so code can tell the two apart.

## Environment

| variable | default | meaning |
|---|---|---|
| `QYSIM_HOST` | `127.0.0.1` | simulator host |
| `QYSIM_RPC_PORT` | `9760` | simulator SDK RPC port |
| `QYSIM_TIMEOUT` | `3.0` | seconds to wait for a reply (then `ReceiveTimeout`) |
| `QYSIM_CAMERA_FPS` | `15` | max live frame rate of `get_frame()` |

## Behaviour notes

- If the simulator is unreachable, the SDK error value is returned (no exception).
  Examples: `{'status': 'error', 'status_code': '408', 'text': 'ConnectTimeout'}`, or
  `"Please check the ROV connection"` from `capture_video`. The client reconnects automatically on the next call.
- Connect flags are kept per object, as in the SDK: `get_rov_status()` before `connect_to_rov()` returns
  `'Please connect ROV first'`. `QyRovHighFreqRealTimeStatusManage.get_rov_status()` returns
  `10hz` and `50hz` packets alternately, paced to about 60 packets/s like a blocking stream read.
- Camera: `capture_video()` → `True`; `get_frame()` → `(True, BGR uint8 ndarray)` rendered from the
  simulated scene (640x360 `SUB_STREAM`, 1280x720 `MAIN_STREAM`); `get_w_h()` → `"640.0 * 360.0"`.
- `download_file()` renders the photo from the pose stored when it was taken and writes
  `<dir_path>/<file name>`. It returns `Preparing to download file`, then `get_download_status()` reports
  `File downloading` → `File downloaded successfully, file_size: … MB` (or `DownloadFile error: …`).
- `get_file_info_list()['text']` is the JSON string. It can also be indexed like the decoded list
  (`text[0]['path']`), which is what the vendor sample does.
- `qysea.sdk.service` / `qysea.sdk.lib` exist only so vendor-style imports succeed.

Tests: `cd simulator && python -m unittest tests.test_sdk_mock -v`
