#!/usr/bin/env python3
"""外部 AI 偵測整合：讀相機串流、簡單 OpenCV 偵測、回報 vision_results、釋放遠端控制。

偵測不需權重：在合成畫面上找偏亮／偏藍綠輪廓（水下色調），框以正規化 xywh 送出。
送出路徑依 PROTOCOL：viewer WebSocket ``{"type":"vision_results",...}``；
讀回可用模擬器擴充 ``get_sim_detections()``（非原廠 SDK）。

用法：

    cd simulator/sdk_mock
    PYTHONPATH=. python examples/vision_ai_detect.py --host 127.0.0.1 --ws-port 8765
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    STRINGS,
    add_host_args,
    get_status,
    make_bridge,
    print_result,
    release_remote,
    take_remote,
)


def detect_contours(frame_bgr, max_det: int = 8) -> list:
    """Weight-free detector: bright / cyan-ish blobs via OpenCV (or numpy fallback)."""
    try:
        import cv2
    except ImportError:
        cv2 = None

    h, w = frame_bgr.shape[:2]
    if cv2 is not None:
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        # Broad underwater / structure mask: higher value channel, moderate saturation.
        lower = np.array([0, 0, 140], dtype=np.uint8)
        upper = np.array([180, 80, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for contour in contours:
            x, y, bw, bh = cv2.boundingRect(contour)
            area = bw * bh
            if area < 80 or area > 0.6 * w * h:
                continue
            boxes.append((area, x / w, y / h, bw / w, bh / h))
        boxes.sort(reverse=True)
        out = []
        for area, x, y, bw, bh in boxes[:max_det]:
            score = float(min(1.0, area / (0.05 * w * h)))
            box = [round(x, 4), round(y, 4), round(bw, 4), round(bh, 4)]
            out.append({"cls": "blob", "score": score, "box": box})
        return out

    # Numpy-only fallback when OpenCV is unavailable.
    gray = frame_bgr.mean(axis=2)
    thresh = gray > (gray.mean() + 25)
    # Coarse grid cells as pseudo-detections.
    detections = []
    gy, gx = 4, 6
    cell_h, cell_w = h // gy, w // gx
    for iy in range(gy):
        for ix in range(gx):
            tile = thresh[iy * cell_h:(iy + 1) * cell_h, ix * cell_w:(ix + 1) * cell_w]
            frac = float(tile.mean()) if tile.size else 0.0
            if frac < 0.15:
                continue
            detections.append({
                "cls": "blob",
                "score": float(min(1.0, frac)),
                "box": [round(ix / gx, 4), round(iy / gy, 4), round(1 / gx, 4), round(1 / gy, 4)],
            })
    detections.sort(key=lambda d: d["score"], reverse=True)
    return detections[:max_det]


def run(bridge, seconds: float = 30.0, dt: float = 0.2) -> dict:
    take_remote(bridge)
    # Gentle hold while detection loop runs.
    bridge.sdk("QYRovControllerManage", "set_right_joystick_up_down", 1500)

    reports = 0
    last_count = 0
    readbacks = 0
    t0 = bridge.sim_time()
    elapsed = 0.0
    acquired = True

    while elapsed < seconds:
        frame = bridge.get_frame_bgr()
        detections = detect_contours(np.asarray(frame))
        bridge.post_vision(detections)
        reports += 1
        last_count = len(detections)

        # Re-acquire remote each loop to show the take/release pattern once at end;
        # mid-run we only verify status stays unlocked under remote.
        status = get_status(bridge)
        if status["RC_Switch_Status"]["RC_Lock"] != "unlock":
            bridge.sdk("QYRovControllerManage", "set_rc_lock_button", 0)

        vision = bridge.get_vision()
        if vision.get("available"):
            readbacks += 1

        bridge.sleep_or_advance(dt)
        elapsed = bridge.sim_time() - t0

    release_remote(bridge)
    acquired = False
    final_vision = bridge.get_vision()
    return {
        "example": "vision_ai_detect",
        "seconds": round(elapsed, 2),
        "frames": reports,
        "last_detections": last_count,
        "vision_readbacks": readbacks,
        "remote_released": not acquired,
        "final_vision_available": bool(final_vision.get("available")),
        "note": STRINGS["remote_off"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Camera + OpenCV detect + vision_results")
    add_host_args(parser)
    args = parser.parse_args(argv)
    bridge = make_bridge(args)
    try:
        result = run(bridge, seconds=args.seconds)
    finally:
        if hasattr(bridge, "close"):
            bridge.close()
    print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
