"""Validate the shipped launch asset contract, compression and GPU/geometry budgets."""
import json
import struct
import unittest
from pathlib import Path


class SmallBoatAssetTests(unittest.TestCase):
    def test_asset_contract(self):
        path = Path(__file__).resolve().parents[1] / 'viewer/models/small_boat.glb'
        raw = path.read_bytes()
        length = struct.unpack_from('<I', raw, 12)[0]
        doc = json.loads(raw[20:20 + length])
        names = {node.get('name') for node in doc['nodes']}
        self.assertTrue({'rov_slot_0', 'rov_slot_1', 'menu_camera', 'menu_target',
                         'water_entry', 'TetherExit'} <= names)
        self.assertIn('EXT_meshopt_compression', doc['extensionsUsed'])
        self.assertIn('EXT_texture_webp', doc['extensionsUsed'])
        triangles = sum(doc['accessors'][p['indices']]['count'] // 3
                        for m in doc['meshes'] for p in m['primitives'])
        self.assertLessEqual(triangles, 60000)
        self.assertTrue(all(i['mimeType'] == 'image/webp' for i in doc['images']))
        # Decode image dimensions rather than trusting the checked-in asset report.
        from PIL import Image
        from io import BytesIO
        binary = raw[28 + length:]
        memory = 0
        for image in doc['images']:
            view = doc['bufferViews'][image['bufferView']]
            offset = view.get('byteOffset', 0)
            im = Image.open(BytesIO(binary[offset:offset + view['byteLength']]))
            memory += im.width * im.height * 4 * 4 / 3
        self.assertLessEqual(memory, 24 * 1024 * 1024)
