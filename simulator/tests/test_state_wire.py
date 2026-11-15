"""Precision budget, full-snapshot compatibility and RFC7692 round trips."""
import json
import unittest
import zlib
from unittest.mock import patch

import numpy as np

from qysim.engine import Simulator
from qysim.server import SimHost
from qysim.state_wire import compact_state


class StateWireTests(unittest.TestCase):
    def test_precision_and_types_without_mutation(self):
        values = [1.23456789, -12345.6789, 0.000000123456789, 0.0]
        original = {'values': np.array(values), 'flag': True, 'id': 123456789,
                    'optional': None, 'text': '測試', 'q': [0.12345, 0.98765]}
        result = compact_state(original)
        for actual, expected in zip(result['values'], values):
            self.assertLessEqual(abs(actual - expected), abs(expected) * 5e-6)
        np.testing.assert_array_equal(original['values'], values)
        self.assertIs(result['flag'], True)
        self.assertIsNone(result['optional'])
        self.assertEqual(result['id'], original['id'])
        self.assertEqual(result['q'], original['q'])
        self.assertEqual(result['text'], original['text'])

    def test_exact_clock_and_selector_fields(self):
        for key in ('t', 'timestamp', 'start', 'end', 'since', 'seq', 'id'):
            value = {key: 123456789.1234567}
            self.assertEqual(compact_state(value), value)

    def test_low_frequency_fields_remain_complete_on_every_tick(self):
        host = SimHost(Simulator('open_water', 42))
        player = host.room.join('Pilot')
        compressor = zlib.compressobj(wbits=-12, memLevel=5)
        decompressor = zlib.decompressobj(wbits=-12)
        previous_seq = None
        for tick in range(33):
            # Cross 0.5 s and 1 s boundaries without changing physics/SDK objects.
            if tick == 3:
                host.sim.power.tripped = True
                host.sim.thermal.injected_c = 100
            host.sim.t = tick / 30
            host.room.tick += 1
            state = host.viewer_state(host.room, player)
            raw = host.viewer_payload(host.room, player).encode()
            encoded = compressor.compress(raw) + compressor.flush(zlib.Z_SYNC_FLUSH)
            restored = decompressor.decompress(encoded[:-4] + b'\x00\x00\xff\xff')
            self.assertEqual(restored, raw)
            decoded = json.loads(raw)
            for field in ('flow_field', 'power', 'thermal'):
                self.assertIn(field, decoded)
                self.assertEqual(decoded[field], state[field])
            for vehicle in decoded['vehicles']:
                self.assertIn('power', vehicle)
                self.assertIn('thermal', vehicle)
            if tick >= 3:
                self.assertTrue(decoded['power']['tripped'])
                self.assertIn('motor_hot', decoded['thermal']['warnings'])
            if tick == 1:
                self.assertEqual(decoded['flow_field']['seq'], previous_seq)
            previous_seq = decoded['flow_field']['seq']

    def test_sdk_native_telemetry_is_unmodified(self):
        sim = Simulator('open_water', 42)
        host = SimHost(sim)
        with patch('qysim.engine.time.time', return_value=1700000000):
            before = sim.sdk_call('QYRovNavigationManage', 'get_rov_data', [], {})
            host.viewer_payload()
            after = sim.sdk_call('QYRovNavigationManage', 'get_rov_data', [], {})
        self.assertEqual(before, after)


class CompressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_negotiated_deflate_and_uncompressed_client(self):
        import websockets
        host = SimHost(Simulator('open_water', 42))
        async with websockets.serve(host.viewer_handler, '127.0.0.1', 0, compression='deflate') as server:
            port = server.sockets[0].getsockname()[1]
            for compression in ('deflate', None):
                async with websockets.connect(f'ws://127.0.0.1:{port}', compression=compression) as ws:
                    protocol = getattr(ws, 'protocol', ws)
                    extensions = protocol.extensions
                    self.assertEqual(bool(extensions), compression == 'deflate')
                    self.assertEqual(json.loads(await ws.recv())['type'], 'world')
                    self.assertEqual(json.loads(await ws.recv())['type'], 'state')
