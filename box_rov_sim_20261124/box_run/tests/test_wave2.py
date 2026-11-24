"""Wave 2 tests: (1) radial deadzone + expo input shaping (Python + JS parity),
(2) CORR-ROV-01 brand subtraction (SDK identity, vehicle ids, brand gate)."""
import ast
import json
import math
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from rov01sim.input_shaping import (axis_deadzone_expo, expo_curve, radial_deadzone_expo, sanitize)
from rov01sim.wave1 import apply_deadzone_and_expo, shape_6dof_gamepad

BOX = Path(__file__).resolve().parents[1]
ROOT = BOX.parent


def old_wave1_axis(value, deadzone=0.08, expo=0.35):
    """Verbatim Wave 1 per-axis formula (regression reference)."""
    v = max(-1.0, min(1.0, float(value)))
    dz = max(0.0, min(0.45, float(deadzone)))
    ex = max(0.0, min(1.0, float(expo)))
    mag = abs(v)
    if mag <= dz:
        return 0.0
    u = (mag - dz) / max(1e-6, 1.0 - dz)
    shaped = (1.0 - ex) * u + ex * (u ** 3)
    return math.copysign(min(1.0, shaped), v)


class TestRadialDeadzoneExpo(unittest.TestCase):
    def test_inside_radial_deadzone_is_zero(self):
        self.assertEqual(radial_deadzone_expo(0.0, 0.0), (0.0, 0.0))
        self.assertEqual(radial_deadzone_expo(0.05, 0.05, 0.08, 0.35), (0.0, 0.0))   # r=0.0707
        self.assertEqual(radial_deadzone_expo(-0.079, 0.0, 0.08, 0.35), (0.0, 0.0))

    def test_radial_not_per_axis(self):
        # each axis below dz, but vector magnitude (0.0849) above it -> must pass through
        x, y = radial_deadzone_expo(0.06, 0.06, 0.08, 0.0)
        self.assertGreater(x, 0.0)
        self.assertAlmostEqual(x, y, places=12)
        # small diagonal keeps its direction (no snapping to an axis)
        x, y = radial_deadzone_expo(0.3, 0.1, 0.08, 0.35)
        self.assertAlmostEqual(math.atan2(y, x), math.atan2(0.1, 0.3), places=12)

    def test_continuous_at_deadzone_edge(self):
        for dz in (0.0, 0.05, 0.08, 0.2, 0.45):
            for ex in (0.0, 0.35, 1.0):
                just_out = radial_deadzone_expo(dz + 1e-9, 0.0, dz, ex)[0]
                self.assertLess(abs(just_out), 1e-6, (dz, ex))

    def test_monotonic_and_full_scale(self):
        for ex in (0.0, 0.35, 0.85, 1.0):
            prev = -1.0
            for i in range(0, 1001):
                v = i / 1000
                out = axis_deadzone_expo(v, 0.08, ex)
                self.assertGreaterEqual(out, prev - 1e-12)
                prev = out
            self.assertAlmostEqual(axis_deadzone_expo(1.0, 0.08, ex), 1.0, places=12)
            self.assertAlmostEqual(axis_deadzone_expo(-1.0, 0.08, ex), -1.0, places=12)

    def test_expo_blend(self):
        dz = 0.1
        v = dz + 0.5 * (1 - dz)               # u = 0.5
        self.assertAlmostEqual(axis_deadzone_expo(v, dz, 0.0), 0.5, places=12)
        self.assertAlmostEqual(axis_deadzone_expo(v, dz, 1.0), 0.125, places=12)
        self.assertAlmostEqual(axis_deadzone_expo(v, dz, 0.4), 0.6 * 0.5 + 0.4 * 0.125, places=12)
        self.assertAlmostEqual(expo_curve(2.0, 0.5), 1.0)

    def test_clamp_and_corner(self):
        x, y = radial_deadzone_expo(1.0, 1.0, 0.08, 0.35)    # square-gate corner r=1.414
        self.assertAlmostEqual(math.hypot(x, y), 1.0, places=12)
        for v in (x, y):
            self.assertLessEqual(abs(v), 1.0)
        x, y = radial_deadzone_expo(5.0, -7.0, 0.0, 0.0)
        self.assertLessEqual(max(abs(x), abs(y)), 1.0)

    def test_zero_params_are_legal_and_bad_input_safe(self):
        self.assertEqual(sanitize(0.0, 0.0), (0.0, 0.0))     # Wave 1 JS bug: 0 fell back to defaults
        self.assertAlmostEqual(axis_deadzone_expo(0.03, 0.0, 0.0), 0.03, places=12)
        self.assertEqual(sanitize(0.9, 3.0), (0.45, 1.0))
        self.assertEqual(radial_deadzone_expo(float("nan"), None), (0.0, 0.0))

    def test_wave1_path_uses_shared_function_without_regression(self):
        for dz in (0.0, 0.08, 0.3):
            for ex in (0.0, 0.35, 1.0):
                for i in range(-100, 101):
                    v = i / 100
                    self.assertAlmostEqual(apply_deadzone_and_expo(v, dz, ex), old_wave1_axis(v, dz, ex), places=12)
        s = shape_6dof_gamepad({"surge": 1.0, "heave": 0.03}, 0.08, 0.35)
        self.assertEqual(s["heave"], 0.0)
        self.assertEqual(s["surge"], 1.0)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_js_python_parity(self):
        pts = [(x / 10, y / 10, dz, ex) for x in range(-12, 13, 3) for y in range(-12, 13, 4)
               for dz in (0.0, 0.08, 0.3) for ex in (0.0, 0.35, 1.0)]
        js = ("import('" + (BOX / "viewer" / "input_shaping.js").as_uri() + "').then(m=>{"
              "const pts=JSON.parse(process.argv[1]);"
              "console.log(JSON.stringify(pts.map(p=>m.radialDeadzoneExpo(p[0],p[1],p[2],p[3]))));})")
        out = subprocess.run(["node", "-e", js, json.dumps(pts)], capture_output=True, text=True, check=True).stdout
        got = json.loads(out)
        self.assertEqual(len(got), len(pts))
        for p, g in zip(pts, got):
            ref = radial_deadzone_expo(*p)
            self.assertAlmostEqual(g[0], ref[0], places=12, msg=str(p))
            self.assertAlmostEqual(g[1], ref[1], places=12, msg=str(p))

    def test_gamepad_path_wired(self):
        app = (BOX / "viewer" / "app.js").read_text(encoding="utf-8")
        self.assertIn("radialDeadzoneExpo(gp.axes[0]", app)
        self.assertIn("radialDeadzoneExpo(gp.axes[2]", app)
        self.assertNotIn("Math.abs(v || 0) < .08", app)
        hud = (BOX / "viewer" / "wave1_hud.js").read_text(encoding="utf-8")
        self.assertIn("setShaping(", hud)
        self.assertNotIn("|| 0.08", hud)


class TestCorrRov01BrandSubtraction(unittest.TestCase):
    ENGINE = BOX / "rov01sim" / "engine.py"

    def _sdk_methods(self):
        tree = ast.parse(self.ENGINE.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("_sdk_"):
                names.add(node.name)
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id.startswith("_sdk_"):
                        names.add(t.id)
        return names

    def test_sdk_identity_strings_are_rov01(self):
        src = self.ENGINE.read_text(encoding="utf-8")
        self.assertIn('return ok("ROV01-SIM-00001")', src)
        self.assertIn('return ok("ROV01_SIM_SDK_V1.2.1")', src)
        self.assertNotIn("X1SIM", src)
        self.assertNotIn("QY_SDK", src)

    def test_sdk_methods_neutral_and_vendor_names_still_routable(self):
        from rov01sim.sdk_vendor_adapter import normalize_class
        names = self._sdk_methods()
        self.assertGreaterEqual(len([n for n in names if "__" in n[5:]]), 80)
        self.assertFalse([n for n in names if n.lower().startswith("_sdk_qy")])
        classes = {n[5:].split("__")[0] for n in names if "__" in n[5:]}
        vendor = ["QYRovControllerManage", "QYRovParameterManage", "QYRovCalibrationManage", "QYRovAddOnsManage",
                  "QYRovCheckManage", "QYSDKInfoManage", "QYRovRealTimeStatusManage",
                  "QyRovHighFreqRealTimeStatusManage", "QYRovNavigationManage", "QYRovVCCMManage",
                  "QyCameraInitManage", "QYCameraWorkModeManage", "QYCameraActionManage",
                  "QYCameraStorageFileManage", "QYCameraSystemManage"]
        for v in vendor:
            self.assertIn(normalize_class(v), classes, v)
        self.assertEqual(normalize_class("RovParameterManage"), "RovParameterManage")
        src = self.ENGINE.read_text(encoding="utf-8")
        self.assertIn("cls = _normalize_sdk_class(cls)", src)
        self.assertIn("except ImportError", src)

    def test_vehicle_ids_have_no_legacy_alias(self):
        from rov01sim.vehicles import VEHICLE_DEFINITIONS, get_vehicle_definition, vehicle_catalogue
        self.assertNotIn("x1", VEHICLE_DEFINITIONS)
        self.assertEqual(get_vehicle_definition().id, "rov01")
        self.assertEqual(get_vehicle_definition("ROV-01").id, "rov01")
        self.assertEqual(get_vehicle_definition("rov01").public()["name"], "ROV-01")
        self.assertNotIn("x1", [c["id"] for c in vehicle_catalogue()])
        cat = json.loads((BOX / "viewer" / "tool_catalogue.json").read_text(encoding="utf-8"))
        self.assertNotIn("x1", cat["vehicles"])
        self.assertIn("rov01", cat["vehicles"])

    def test_brand_gate_passes(self):
        r = subprocess.run([sys.executable, str(ROOT / "brand_gate.py"), "--root", str(ROOT)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])
        self.assertIn("RESULT=PASS", r.stdout)


if __name__ == "__main__":
    unittest.main()
