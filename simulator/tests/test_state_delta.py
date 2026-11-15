"""I2 static_once: legacy byte identity and merged equality across the catalogue."""
import json
import unittest

from qysim.engine import Simulator
from qysim.scenarios import LIBRARY
from qysim.server import SimHost, dumps
from qysim.state_wire import (
    STATIC_ONCE,
    STATIC_ONCE_FIELDS,
    STATIC_ONCE_VEHICLE_FIELDS,
    StaticOnceTracker,
    parse_caps,
)


class CapsParsingTests(unittest.TestCase):
    def test_unknown_caps_are_ignored(self):
        self.assertEqual(parse_caps(None), ())
        self.assertEqual(parse_caps([]), ())
        self.assertEqual(parse_caps(['static_once', 'nope', 'static_once']), (STATIC_ONCE,))
        with self.assertRaises(ValueError):
            parse_caps('static_once')
        with self.assertRaises(ValueError):
            parse_caps([1])


class LegacyCompatibilityTests(unittest.TestCase):
    def test_undeclared_payload_matches_full_snapshot_bytes(self):
        host = SimHost(Simulator('coral_reef', 42))
        players = [host.room.join(name, model_id=model)
                   for name, model in (('甲', 'x1'), ('乙', 'falcon'), ('丙', 'bluerov2_heavy'))]
        host.room.players.clear()
        for index, player in enumerate(players):
            player.id = f'{index + 1:012x}'
            host.room.players[player.id] = player
        host.room.host_id = players[0].id
        sock = object()
        # No caps on the socket: wire path must match the legacy encoder exactly.
        steps = 0
        for frame in range(45):
            target = round(frame * 100 / 30)
            while steps < target:
                for sim in host.room.vehicles.values():
                    sim.apply_viewer_rc({'rc_lock': 0, 'right_ud': 1600}, partial=True)
                host.room.step(.01)
                steps += 1
            for player in players + [None]:
                expected = host.viewer_payload(host.room, player)
                with_ws = host.viewer_payload(host.room, player, ws=sock)
                self.assertEqual(with_ws, expected)
                self.assertEqual(with_ws.encode('utf-8'), expected.encode('utf-8'))


class StaticOnceMergeTests(unittest.TestCase):
    @staticmethod
    def _fill(previous, incoming, fields):
        merged = dict(incoming)
        if previous:
            for field in fields:
                if field not in incoming and field in previous:
                    merged[field] = previous[field]
        return merged

    def _merge(self, previous, incoming):
        """Python mirror of viewer/state_merge.js for cross-check in server tests."""
        if not incoming.get('delta') or previous is None:
            merged = dict(incoming)
            merged.pop('delta', None)
            return merged
        merged = self._fill(previous, incoming, STATIC_ONCE_FIELDS)
        merged.pop('delta', None)
        if 'vehicles' in incoming:
            prior = {(v.get('vehicle_id') or v.get('id')): v for v in previous.get('vehicles', [])}
            merged['vehicles'] = [
                self._fill(prior.get(entry.get('vehicle_id') or entry.get('id')), entry,
                           STATIC_ONCE_VEHICLE_FIELDS)
                for entry in incoming['vehicles']]
        return merged

    def test_removed_allowlisted_field_sends_unmarked_full_state(self):
        tracker = StaticOnceTracker()
        base = {'t': 0, 'vehicle': {'id': 'x1'}, 'remote_control': {'owner': 'sdk'},
                'vehicles': [{'vehicle_id': 'v1', 'vehicle': {'id': 'x1'}}]}
        tracker.strip(base)
        second = tracker.strip({**base, 't': 1})
        self.assertTrue(second['delta'])
        self.assertNotIn('remote_control', second)
        removed = {key: value for key, value in base.items() if key != 'remote_control'}
        third = tracker.strip({**removed, 't': 2})
        self.assertNotIn('delta', third)
        self.assertIn('vehicle', third)
        merged = self._merge(self._merge(base, second), third)
        self.assertNotIn('remote_control', merged)

    def test_departed_seat_forces_full_state(self):
        tracker = StaticOnceTracker()
        seat = {'vehicle_id': 'v2', 'vehicle': {'id': 'falcon'}}
        tracker.strip({'t': 0, 'vehicles': [{'vehicle_id': 'v1'}, seat]})
        left = tracker.strip({'t': 1, 'vehicles': [{'vehicle_id': 'v1'}]})
        self.assertNotIn('delta', left)
        back = tracker.strip({'t': 2, 'vehicles': [{'vehicle_id': 'v1'}, seat]})
        self.assertEqual(back['vehicles'][1]['vehicle'], {'id': 'falcon'})

    def test_new_explicit_null_is_forwarded(self):
        tracker = StaticOnceTracker()
        tracker.strip({'t': 0, 'vehicle': {'id': 'x1'}})
        second = tracker.strip({'t': 1, 'vehicle': {'id': 'x1'}, 'depth_hold': None})
        self.assertIn('depth_hold', second)
        self.assertIsNone(second['depth_hold'])

    def test_non_allowlisted_key_removal_is_not_retained(self):
        previous = {'type': 'state', 'vehicle': {'id': 'x1'}, 'procedure': {'phase': 'checks'}}
        merged = self._merge(previous, {'type': 'state', 'delta': True, 't': 1})
        self.assertEqual(merged['vehicle'], {'id': 'x1'})
        self.assertNotIn('procedure', merged)

    def test_caps_are_per_socket(self):
        host = SimHost(Simulator('open_water', 42))
        pilot = host.room.join('Pilot')
        declared = object()
        legacy = object()
        host.remember_caps(declared, {'caps': [STATIC_ONCE]})
        host.remember_caps(legacy, {})
        for _ in range(5):
            host.room.step(.01)
            host.viewer_payload(host.room, pilot, ws=declared)
            wire = json.loads(host.viewer_payload(host.room, pilot, ws=legacy))
            self.assertNotIn('delta', wire)
            self.assertIn('vehicle', wire)

    def test_tracker_omits_unchanged_allowlisted_fields(self):
        host = SimHost(Simulator('open_water', 42))
        player = host.room.join('Pilot')
        sock = object()
        host.remember_caps(sock, {'caps': [STATIC_ONCE]})
        first = json.loads(host.viewer_payload(host.room, player, ws=sock))
        for field in ('vehicle', 'campaign', 'power', 'thermal', 'flow_field'):
            self.assertIn(field, first)
        host.room.step(.01)
        host.room.tick += 1
        second = json.loads(host.viewer_payload(host.room, player, ws=sock))
        self.assertNotIn('vehicle', second)
        self.assertNotIn('campaign', second)
        merged = self._merge(first, second)
        full = json.loads(host.viewer_payload(host.room, player))
        self.assertEqual(merged['vehicle'], full['vehicle'])
        self.assertEqual(merged['campaign'], full['campaign'])

    def test_world_change_forces_full_snapshot(self):
        host = SimHost(Simulator('open_water', 42))
        player = host.room.join('Pilot')
        sock = object()
        host.remember_caps(sock, {'caps': [STATIC_ONCE]})
        json.loads(host.viewer_payload(host.room, player, ws=sock))
        host.room.step(.01)
        json.loads(host.viewer_payload(host.room, player, ws=sock))
        host.static_once[sock].reset()
        restored = json.loads(host.viewer_payload(host.room, player, ws=sock))
        self.assertIn('vehicle', restored)
        self.assertIn('campaign', restored)

    def test_catalogue_merged_equals_full_for_600_ticks(self):
        keys = [*LIBRARY, 'random']
        self.assertEqual(len(keys), 18)
        for key in keys:
            with self.subTest(scenario=key):
                host = SimHost(Simulator(key, 42))
                player = host.room.join('Pilot')
                tracker = StaticOnceTracker()
                previous = None
                steps = 0
                for frame in range(600):
                    target = frame  # one physics tick per compared state
                    while steps < target:
                        host.sim.apply_viewer_rc({'rc_lock': 0, 'right_ud': 1600}, partial=True)
                        host.room.step(.01)
                        steps += 1
                    host.room._snapshot = None
                    full = json.loads(dumps({'type': 'state', **host.viewer_state(host.room, player)}))
                    delta = tracker.strip(full)
                    # strip may return the same dict on a forced full frame; copy before merge mutates ideas.
                    wire = json.loads(dumps(delta))
                    merged = self._merge(previous, wire)
                    self.assertEqual(merged, full, f'{key} frame {frame}')
                    previous = merged


class SessionCapsTests(unittest.IsolatedAsyncioTestCase):
    async def test_join_and_hello_echo_caps(self):
        import websockets
        host = SimHost(Simulator('open_water', 42))
        async with websockets.serve(host.viewer_handler, '127.0.0.1', 0, compression=None) as server:
            port = server.sockets[0].getsockname()[1]
            async with websockets.connect(f'ws://127.0.0.1:{port}') as ws:
                self.assertEqual(json.loads(await ws.recv())['type'], 'world')
                self.assertEqual(json.loads(await ws.recv())['type'], 'state')
                await ws.send(dumps({'type': 'hello', 'caps': [STATIC_ONCE, 'unknown']}))
                ack = json.loads(await ws.recv())
                self.assertEqual(ack, {'type': 'hello_ack', 'caps': [STATIC_ONCE]})
                await ws.send(dumps({'type': 'join', 'room_id': 'training', 'name': 'Pilot',
                                     'model_id': 'x1', 'caps': [STATIC_ONCE]}))
                session = json.loads(await ws.recv())
                self.assertEqual(session['type'], 'session')
                self.assertEqual(session['caps'], [STATIC_ONCE])
                first = None
                for _ in range(8):
                    message = json.loads(await ws.recv())
                    if message['type'] == 'state':
                        first = message
                        break
                self.assertIsNotNone(first)
                self.assertIn('vehicle', first)
                self.assertIn('campaign', first)
                await ws.send(dumps({'type': 'join', 'room_id': 'training', 'name': 'Pilot',
                                     'model_id': 'x1'}))
                while True:
                    legacy_session = json.loads(await ws.recv())
                    if legacy_session['type'] == 'session':
                        break
                self.assertNotIn('caps', legacy_session)


if __name__ == '__main__':
    unittest.main()
