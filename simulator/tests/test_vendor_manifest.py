"""Exercise npm addon recovery, runtime preservation and read-only validation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/vendor_manifest.py'
spec = importlib.util.spec_from_file_location('vendor_manifest', SCRIPT)
vendor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vendor)


class TestVendorManifest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.viewer = self.root / 'viewer'
        self.npm = self.root / 'npm'
        self.viewer.mkdir()
        self.npm.mkdir()
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_text(json.dumps({'modules': [], 'runtime': ['examples/jsm/libs/decoder.wasm']}))
        self.write('package.json', '{"version":"0.160.0"}')
        self.write('LICENSE', 'MIT')
        self.write('build/three.module.js', 'export const x = 1;')
        self.write('examples/jsm/postprocessing/EffectComposer.js', "export { x } from '../dep.js';")
        self.write('examples/jsm/dep.js', "export { x } from 'three';")
        self.write('examples/jsm/libs/decoder.wasm', 'binary fixture')
        (self.viewer / 'app.js').write_text("import 'three/addons/postprocessing/EffectComposer.js';")
        for name, value in [('VIEWER', self.viewer), ('NPM_THREE', self.npm), ('MANIFEST', self.manifest)]:
            context = patch.object(vendor, name, value)
            context.start()
            self.addCleanup(context.stop)

    def write(self, name, text):
        file = self.npm / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    def test_recover_recursive_addon_and_copy_runtime(self):
        data = vendor.manifest()
        self.assertIn('examples/jsm/dep.js', data['modules'])
        self.assertIn('build/three.module.js', data['modules'])
        self.assertEqual(data['runtime'], ['examples/jsm/libs/decoder.wasm'])
        unused = self.viewer / 'vendor/three/unused.js'
        unused.write_text('unused')
        vendor.prune_vendor(data)
        self.assertFalse(unused.exists())
        self.assertTrue((self.viewer / 'vendor/three/examples/jsm/libs/decoder.wasm').is_file())
        self.manifest.write_text(json.dumps(data))
        vendor.copy_vendor(self.root / 'showcase')
        self.assertEqual((self.root / 'showcase/three/examples/jsm/libs/decoder.wasm').read_text(),
                         'binary fixture')
        self.assertEqual(vendor.manifest(check=True), data)

    def test_check_reports_repair_command_without_writing(self):
        with self.assertRaisesRegex(ValueError, 'npm ci.*vendor_manifest.py --prune'):
            vendor.manifest(check=True)
        self.assertFalse((self.viewer / 'vendor').exists())

    def test_refuses_wrong_npm_version(self):
        self.write('package.json', '{"version":"0.999.0"}')
        with self.assertRaisesRegex(ValueError, 'three@0.160.0'):
            vendor.manifest()

    def test_runtime_cannot_escape_vendor(self):
        with self.assertRaisesRegex(ValueError, 'escapes'):
            vendor.vendor_file('../../outside.wasm')
