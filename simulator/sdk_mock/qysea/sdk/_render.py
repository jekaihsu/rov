"""Synthetic underwater camera for the mock SDK.

Renders the simulator scene described by a ``camera_view`` reply (see PROTOCOL.md)
by numpy sphere tracing at a low internal resolution, then upscales. Only numpy is
required; OpenCV (if installed) is used for smoother upscaling and the OSD text.

Frames: world NED, body FRD, camera looking along body +x, ~90 deg horizontal FOV.
"""

from __future__ import annotations

import math
import time

import numpy as np

try:                                    # optional
    import cv2                          # type: ignore
except Exception:                       # pragma: no cover - depends on environment
    cv2 = None

CAMERA_OFFSET = np.array([0.38, 0.0, 0.02])     # lens position in body FRD (m)
UP = np.array([0.0, 0.0, -1.0])

# albedo per obstacle kind, RGB 0..1 (marine-growth tinted)
ALBEDO = {
    "pile": (0.62, 0.58, 0.42), "monopile": (0.66, 0.60, 0.40), "jacket_leg": (0.60, 0.56, 0.44),
    "brace": (0.58, 0.55, 0.45), "mast": (0.50, 0.46, 0.40), "hull": (0.36, 0.38, 0.42),
    "wreck": (0.46, 0.36, 0.26), "wall": (0.58, 0.58, 0.54),
}
SAND = np.array([0.62, 0.57, 0.45])
WATER_SHALLOW = np.array([0.12, 0.45, 0.50])     # RGB
WATER_DEEP = np.array([0.015, 0.09, 0.15])
ABSORB = np.array([0.40, 0.10, 0.07])            # per metre, R G B (red dies first)
EXPOSURE_TARGET, MAX_GAIN = 0.30, 2.5
FOG_K = 2.5                                      # contrast at visibility_m ~ e^-2.5
LED_GAIN = {0: 0.0, 1: 0.9, 2: 1.8}


# ── geometry ──────────────────────────────────────────────────────────────
def q_to_matrix(q) -> np.ndarray:
    w, x, y, z = (float(v) for v in q)
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def yaw_matrix(yaw_deg: float) -> np.ndarray:
    a = math.radians(yaw_deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


class Scene:
    """Vectorised signed distance field of seabed + obstacles."""

    def __init__(self, view: dict):
        self.seabed = float(view.get("seabed_depth", 30.0))
        self.prims: list[tuple] = []          # (kind_name, fn(P) -> dist)
        for ob in view.get("obstacles", []) or []:
            t = ob.get("type")
            kind = ob.get("kind", t)
            if t == "cylinder":
                a, b = np.asarray(ob["p0"], float), np.asarray(ob["p1"], float)
                self.prims.append((kind, self._capsule(a, b, float(ob["radius"]))))
            elif t == "box":
                self.prims.append((kind, self._box(np.asarray(ob["center"], float),
                                                   np.asarray(ob["half"], float), float(ob.get("yaw_deg", 0)))))
            elif t == "wall":
                # finite slab behind the face, from `top` down past the seabed
                n_deg = float(ob.get("normal_deg", 0))
                a = math.radians(n_deg)
                n = np.array([math.cos(a), math.sin(a), 0.0])
                thick = 4.0
                top = float(ob.get("top", 0.0))
                bottom = self.seabed + 1.0
                p = np.asarray(ob["point"], float)
                c = p - n * thick / 2
                c[2] = (top + bottom) / 2
                half = np.array([thick / 2, float(ob.get("width", 60.0)) / 2, (bottom - top) / 2])
                self.prims.append((kind, self._box(c, half, n_deg)))

    @staticmethod
    def _capsule(a, b, r):
        ab = b - a
        inv = 1.0 / max(float(ab @ ab), 1e-12)

        def f(P):
            t = np.clip(((P - a) @ ab) * inv, 0.0, 1.0)
            d = P - (a + t[:, None] * ab)
            return np.sqrt(np.einsum("ij,ij->i", d, d)) - r
        return f

    @staticmethod
    def _box(c, h, yaw_deg):
        R = yaw_matrix(yaw_deg)

        def f(P):
            q = np.abs((P - c) @ R) - h
            out = np.maximum(q, 0.0)
            return np.sqrt(np.einsum("ij,ij->i", out, out)) + np.minimum(q.max(axis=1), 0.0)
        return f

    def sdf(self, P: np.ndarray) -> np.ndarray:
        d = self.seabed - P[:, 2]
        for _, f in self.prims:
            d = np.minimum(d, f(P))
        return d

    def sdf_id(self, P: np.ndarray) -> np.ndarray:
        """Index of the nearest surface: -1 seabed, else obstacle index."""
        best = self.seabed - P[:, 2]
        idx = np.full(len(P), -1)
        for i, (_, f) in enumerate(self.prims):
            d = f(P)
            closer = d < best
            best = np.where(closer, d, best)
            idx[closer] = i
        return idx

    def normals(self, P: np.ndarray, e: float = 0.01) -> np.ndarray:
        k = np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], float)
        n = sum(k[i] * self.sdf(P + k[i] * e)[:, None] for i in range(4))
        return n / np.maximum(np.linalg.norm(n, axis=1), 1e-9)[:, None]


def trace(scene: Scene, origin: np.ndarray, dirs: np.ndarray, tmax: float, steps: int = 72):
    """Sphere trace. Returns (t, hit mask)."""
    n = len(dirs)
    t = np.full(n, 0.02)
    hit = np.zeros(n, bool)
    alive = np.arange(n)
    for _ in range(steps):
        if alive.size == 0:
            break
        ta = t[alive]
        d = scene.sdf(origin + dirs[alive] * ta[:, None])
        h = d < 0.004 + 0.0015 * ta
        hit[alive[h]] = True
        keep = ~h
        alive = alive[keep]
        t[alive] = ta[keep] + np.maximum(d[keep] * 0.95, 0.01 + 0.004 * ta[keep])
        alive = alive[t[alive] < tmax]
    return t, hit


# ── shading ───────────────────────────────────────────────────────────────
def _ambient(depth):
    return np.clip(np.exp(-np.maximum(depth, 0.0) / 22.0), 0.03, 1.0)


def _hash2(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    h = np.sin(a * 127.1 + b * 311.7) * 43758.5453
    return h - np.floor(h)


def render(view: dict, width: int = 640, height: int = 360, internal: tuple = (160, 90),
           pose: dict | None = None, hfov_deg: float = 90.0, osd: bool = True,
           t_now: float | None = None) -> np.ndarray:
    """Render one BGR uint8 frame.

    ``pose`` (``{n, e, depth, yaw}``, yaw in degrees) overrides the live pose in ``view``
    (used for photos, which store only position and heading)."""
    if pose is not None:
        pos = np.array([pose.get("n", 0.0), pose.get("e", 0.0), pose.get("depth", 0.0)], float)
        R = yaw_matrix(float(pose.get("yaw", 0.0)))
    else:
        pos = np.asarray(view.get("pos", [0, 0, 0]), float)
        R = q_to_matrix(view.get("q", [1, 0, 0, 0]))
    scene = Scene(view)
    iw, ih = internal
    cam = pos + R @ CAMERA_OFFSET

    # ray directions (body FRD: x fwd, y right, z down) -> world NED
    tx = math.tan(math.radians(hfov_deg) / 2)
    ty = tx * ih / iw
    u = (np.arange(iw) + 0.5) / iw * 2 - 1
    v = (np.arange(ih) + 0.5) / ih * 2 - 1
    uu, vv = np.meshgrid(u * tx, v * ty)
    body = np.stack([np.ones_like(uu), uu, vv], axis=-1).reshape(-1, 3)
    body /= np.linalg.norm(body, axis=1)[:, None]
    D = body @ R.T

    silt = float(view.get("silt", 0.0) or 0.0)
    vis = max(0.5, float(view.get("visibility_m", 12.0) or 12.0) * (1.0 - 0.75 * min(1.0, silt)))
    led = LED_GAIN.get(int(view.get("led", 0) or 0), 0.0)
    zc = max(0.0, float(cam[2]))
    tmax = min(vis * 2.2, 60.0)

    t, hit = trace(scene, cam, D, tmax)
    # nothing is visible through the sea surface: hits beyond it become surface pixels
    dz = D[:, 2]
    ts = np.where(dz < -1e-3, max(float(cam[2]), 0.0) / np.maximum(-dz, 1e-3), np.inf)
    hit &= t < ts

    # water / background colour
    deep = 1.0 - math.exp(-zc / 20.0)
    water = (WATER_SHALLOW * (1 - deep) + WATER_DEEP * deep) * (0.25 + 0.75 * float(_ambient(zc)))
    if silt > 0:
        water = water * (1 - 0.5 * silt) + np.array([0.30, 0.28, 0.20]) * float(_ambient(zc)) * 0.5 * silt
    up = np.clip(-D[:, 2], -1.0, 1.0)
    bg = water[None, :] * (0.55 + 0.65 * np.clip(up, 0, 1) - 0.2 * np.clip(-up, 0, 1))[:, None]
    if led > 0:                                     # LED backscatter brightens the near water
        bg = bg + led * 0.05 * np.array([0.9, 0.95, 1.0])[None, :] * (1 + silt * 3)

    col = bg.copy()
    # sea surface seen from below (Snell's window), for rays that miss everything
    miss = ~hit
    if cam[2] > 0:
        surf = miss & (ts < tmax)
        if surf.any():
            fs = np.exp(-FOG_K * ts[surf] / vis)[:, None]
            P = cam + D[surf] * ts[surf][:, None]
            ripple = 0.85 + 0.15 * np.sin(P[:, 0] * 1.3 + P[:, 1] * 0.7 + (t_now or time.time()) * 1.5)
            sky = np.array([0.55, 0.80, 0.85])[None, :] * ripple[:, None]
            col[surf] = sky * fs + bg[surf] * (1 - fs)

    if hit.any():
        th = t[hit]
        P = cam + D[hit] * th[:, None]
        N = scene.normals(P)
        ids = scene.sdf_id(P)
        alb = np.empty((len(P), 3))
        sea = ids < 0
        if sea.any():
            ps = P[sea]
            pattern = 0.80 + 0.12 * np.sin(ps[:, 0] * 1.7) * np.sin(ps[:, 1] * 2.3) \
                + 0.10 * _hash2(np.floor(ps[:, 0] * 3), np.floor(ps[:, 1] * 3))
            alb[sea] = SAND[None, :] * pattern[:, None]
        for i, (kind, _) in enumerate(scene.prims):
            m = ids == i
            if m.any():
                base = np.array(ALBEDO.get(kind, (0.5, 0.5, 0.5)))
                pm = P[m]
                streak = 0.88 + 0.12 * _hash2(np.floor(pm[:, 2] * 2), np.floor((pm[:, 0] + pm[:, 1]) * 2))
                alb[m] = base[None, :] * streak[:, None]
        sun = _ambient(P[:, 2]) * (0.55 + 0.65 * np.clip(N @ UP, 0, 1))
        light = sun
        if led > 0:
            facing = np.clip(-np.einsum("ij,ij->i", N, D[hit]), 0, 1)
            light = light + led * facing / (1.0 + 0.22 * th * th)
        c = alb * light[:, None] * np.exp(-ABSORB[None, :] * th[:, None])
        f = np.exp(-FOG_K * th / vis)[:, None]
        col[hit] = c * f + bg[hit] * (1 - f)

    # camera auto-exposure with limited gain: deep water stays dark without the LED
    luma = float((col @ np.array([0.3, 0.59, 0.11])).mean())
    col = col * min(MAX_GAIN, max(1.0, EXPOSURE_TARGET / max(luma, 1e-4)))
    img = np.clip(col.reshape(ih, iw, 3)[:, :, ::-1] * 255.0, 0, 255).astype(np.uint8)   # RGB -> BGR
    img = _upscale(img, width, height)
    _particles(img, silt, led, t_now)
    if osd:
        _osd(img, cam, R, t_now)
    return img


def _upscale(img: np.ndarray, width: int, height: int) -> np.ndarray:
    ih, iw = img.shape[:2]
    if (iw, ih) == (width, height):
        return img
    if cv2 is not None:
        return cv2.resize(img, (width, height), interpolation=cv2.INTER_LINEAR)
    yi = (np.arange(height) * ih // height).clip(0, ih - 1)
    xi = (np.arange(width) * iw // width).clip(0, iw - 1)
    return np.ascontiguousarray(img[yi][:, xi])


def _particles(img: np.ndarray, silt: float, led: float, t_now) -> None:
    """Marine snow: a few bright specks, more with silt and when the LED is on."""
    h, w = img.shape[:2]
    rng = np.random.default_rng(int((t_now or time.time()) * 10) & 0xFFFFFFFF)
    n = int((25 + 350 * silt) * (1 + led) * (w * h) / (640 * 360))
    if n <= 0:
        return
    ys = rng.integers(0, h - 1, n)
    xs = rng.integers(0, w - 1, n)
    val = (40 + 60 * min(1.0, led + 0.3)) * rng.random(n)
    for dy in (0, 1):
        for dx in (0, 1):
            px = img[ys + dy, xs + dx].astype(np.int16) + val[:, None].astype(np.int16)
            img[ys + dy, xs + dx] = np.clip(px, 0, 255).astype(np.uint8)


def _osd(img: np.ndarray, cam: np.ndarray, R: np.ndarray, t_now) -> None:
    if cv2 is None:
        return
    fwd = R[:, 0]
    hdg = math.degrees(math.atan2(fwd[1], fwd[0])) % 360
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t_now or time.time()))
    text = f"D {max(0.0, float(cam[2])):5.1f} m   HDG {hdg:05.1f}   {stamp}"
    h, w = img.shape[:2]
    scale = max(0.35, w / 1600)
    cv2.putText(img, text, (int(10 * scale / 0.4), h - int(12 * scale / 0.4)), cv2.FONT_HERSHEY_SIMPLEX,
                scale, (200, 210, 210), 1, cv2.LINE_AA)


# ── file output ───────────────────────────────────────────────────────────
class EncoderUnavailable(RuntimeError):
    pass


def write_jpeg(path: str, img_bgr: np.ndarray, quality: int = 90) -> None:
    """Write a JPEG with OpenCV, else Pillow; raise EncoderUnavailable if neither is installed."""
    if cv2 is not None:
        if cv2.imwrite(path, img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality]):
            return
        raise OSError(f"cv2.imwrite failed for {path}")
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        raise EncoderUnavailable("no JPEG encoder: install opencv-python-headless or pillow") from None
    Image.fromarray(np.ascontiguousarray(img_bgr[:, :, ::-1])).save(path, "JPEG", quality=quality)


def write_video(path: str, frames: list, fps: float = 10.0) -> None:
    """Write an MP4 (mp4v). Needs OpenCV."""
    if cv2 is None:
        raise EncoderUnavailable("no video encoder: install opencv-python-headless")
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not vw.isOpened():
        raise OSError(f"cannot open video writer for {path}")
    try:
        for f in frames:
            vw.write(f)
    finally:
        vw.release()
