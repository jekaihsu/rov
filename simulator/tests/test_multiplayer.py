"""Room integration tests: ownership, world clock, reconnect and transport."""
import asyncio
import json
import time
import unittest
from unittest.mock import patch

import numpy as np

from qysim.engine import Simulator
from qysim.room import Room
from qysim.server import SimHost, dumps


class TestRoom(unittest.TestCase):
    def setUp(self):
        self.host = SimHost(Simulator("open_water", 42))
        self.room = self.host.room
        self.a = self.room.join("Alpha")
        self.b = self.room.join("Bravo")

    def test_shared_world_and_exclusive_inputs(self):
        a, b = self.room.vehicles[self.a.vehicle_id], self.room.vehicles[self.b.vehicle_id]
        self.assertIs(a.world, b.world)
        self.assertIsNot(a.tether, b.tether)
        self.host.handle_viewer({"type": "rc", "seq": 1, "vehicle_id": self.b.vehicle_id,
                                 "rc": {"right_ud": 1900, "rc_lock": 0}}, room=self.room, player=self.a)
        self.assertEqual(a.rc.right_ud, 1900)
        self.assertEqual(b.rc.right_ud, 1500)
        stale = self.host.handle_viewer({"type": "rc", "seq": 1, "rc": {"right_ud": 1100}}, room=self.room, player=self.a)
        self.assertEqual(stale["code"], "stale_input")
        self.assertEqual(a.rc.right_ud, 1900)

    def test_room_world_advances_once_and_snapshots_agree(self):
        world = self.room.primary.world
        with patch.object(world.current, "step_gust", wraps=world.current.step_gust) as gust, \
             patch.object(world, "step", wraps=world.step) as step:
            self.room.step(.01)
            gust.assert_called_once()
            step.assert_called_once()
        sa, sb = self.room.state(self.a), self.room.state(self.b)
        self.assertEqual(sa["t"], sb["t"])
        self.assertEqual(sa["vehicles"], sb["vehicles"])
        self.assertEqual(sa["environment"], sb["environment"])
        self.assertTrue(all(np.isfinite(sim.vehicle.s.pos).all() for sim in self.room.vehicles.values()))

    def test_only_host_can_reset_and_pause(self):
        self.room.step(.01)
        denied = self.host.handle_viewer({"type": "reset"}, room=self.room, player=self.b)
        self.assertEqual(denied["code"], "host_only")
        self.assertGreater(self.room.primary.t, 0.)
        self.host.handle_viewer({"type": "pause"}, room=self.room, player=self.a)
        self.assertTrue(all(sim.paused for sim in self.room.vehicles.values()))
        self.host.handle_viewer({"type": "reset"}, room=self.room, player=self.a)
        self.assertTrue(all(sim.t == 0 and sim.rc.rc_lock for sim in self.room.vehicles.values()))
        self.assertIs(self.room.vehicles["v1"].world, self.room.vehicles["v2"].world)

    def test_only_host_changes_mission_but_every_player_can_take_mission_photo(self):
        change = {"type": "operation", "action": "mission_mode", "mode": "inspection_coop"}
        for player in (None, self.b):
            denied = self.host.handle_viewer(change, room=self.room, player=player)
            self.assertEqual(denied["code"], "host_only")
        host_operations = self.room.vehicles[self.a.vehicle_id].operations
        with patch.object(host_operations, "command", return_value={"ok": True}) as command:
            self.assertTrue(self.host.handle_viewer(change, room=self.room, player=self.a)["ok"])
            command.assert_called_once_with(change)
        guest_operations = self.room.vehicles[self.b.vehicle_id].operations
        photo = {"type": "operation", "action": "mission_photo"}
        with patch.object(guest_operations, "command", return_value={"ok": True}) as command:
            self.assertTrue(self.host.handle_viewer(photo, room=self.room, player=self.b)["ok"])
            command.assert_called_once_with(photo)

    def test_mission_mode_changes_shared_run_and_guest_photo_uses_own_vehicle(self):
        change = {"type": "operation", "action": "mission_mode", "mode": "inspection_coop"}
        result = self.host.handle_viewer(change, room=self.room, player=self.a)
        self.assertTrue(result["ok"])
        shared = self.room.primary.world.mission_run
        self.assertEqual(shared.mode, "inspection_coop")
        denied = self.host.handle_viewer({**change, "mode": "free_explore"}, room=self.room, player=self.b)
        self.assertEqual(denied["code"], "host_only")
        self.assertIs(self.room.primary.world.mission_run, shared)
        a, b = (self.room.vehicles[p.vehicle_id] for p in (self.a, self.b))
        self.assertIs(a.world.mission_run, b.world.mission_run)
        photos = (len(a.camera.files), len(b.camera.files))
        result = self.host.handle_viewer({"type": "operation", "action": "mission_photo"}, room=self.room, player=self.b)
        self.assertTrue(result["ok"])
        self.assertEqual((len(a.camera.files), len(b.camera.files)), (photos[0], photos[1] + 1))
        self.assertEqual(shared.last_photo["vehicle_id"], self.b.vehicle_id)

    def test_disconnect_timeout_and_reconnect_generation(self):
        sim = self.room.vehicles[self.a.vehicle_id]
        self.room.input(self.a, 1, now=10.)
        sim.rc.rc_lock = 0
        sim.rc.right_ud = 1900
        self.room.check_timeouts(now=11.)
        self.assertEqual((sim.rc.rc_lock, sim.rc.right_ud), (1, 1500))
        self.assertTrue(sim.input_latched)
        generation_after_timeout = sim.control_generation
        self.host.handle_viewer({"type": "rc", "seq": 2, "rc": {"rc_lock": 0, "right_ud": 1900}}, room=self.room, player=self.a)
        self.assertEqual(sim.rc.rc_lock, 1, "A delayed unlocked heartbeat must not undo timeout")
        self.assertTrue(sim.input_latched)
        self.assertEqual(sim.control_generation, generation_after_timeout)
        self.host.handle_viewer({"type": "rc", "seq": 3, "rc": {"rc_lock": 1}}, room=self.room, player=self.a)
        self.assertFalse(sim.input_latched)
        self.assertEqual(sim.rc.rc_lock, 1)
        self.host.handle_viewer({"type": "rc", "seq": 4, "rc": {"rc_lock": 0}}, room=self.room, player=self.a)
        self.assertEqual(sim.rc.rc_lock, 0, "A later deliberate unlock works after locked acknowledgement")
        generation = self.a.generation
        self.room.disconnect(self.a, generation)
        self.assertEqual(self.room.host_id, self.b.id)
        resumed = self.room.join(resume_token=self.a.token)
        self.assertIs(resumed, self.a)
        self.assertEqual(resumed.generation, generation + 1)
        self.room.disconnect(self.a, generation)  # superseded socket must not evict new one
        self.assertTrue(self.a.connected)
        self.assertEqual(sim.rc.rc_lock, 1)

    def test_capacity_model_and_room_isolation(self):
        self.room.join("C", model_id="falcon")
        with self.assertRaisesRegex(ValueError, "room_full"):
            self.room.join("D", model_id="bluerov2_heavy")
        self.room.step(.01)
        self.assertEqual(len(self.room.state()["vehicles"]), 3)
        self.assertEqual(len(self.room.vehicles["v3"].health), 5)
        session = self.host.join_viewer(object(), {"room_id": "other", "name": "Elsewhere"})
        self.assertEqual(session["room_id"], "other")
        self.assertIsNot(self.host.rooms["other"].primary.world, self.room.primary.world)


class TestIdleGate(unittest.TestCase):
    def test_empty_default_sleeps_but_sdk_and_pending_work_keep_it_running(self):
        host = SimHost(Simulator("open_water", 42))
        self.assertFalse(host.should_step_room(host.room))
        host.rpc_connections = 1  # includes read-only SDK status/camera clients
        self.assertTrue(host.should_step_room(host.room))
        host.rpc_connections = 0
        host.sim.remote_control = True
        self.assertTrue(host.should_step_room(host.room))
        host.sim.remote_control = False
        host.sim.nav.mode = "H_NAVI"
        self.assertTrue(host.should_step_room(host.room))
        host.sim.nav.mode = "IDLE"
        host.sim.camera.recording_since = 0.
        self.assertTrue(host.should_step_room(host.room))
        host.sim.camera.recording_since = None
        host.qirc_enabled = True
        self.assertTrue(host.should_step_room(host.room))
        host.qirc_enabled = False
        host.room.join("Pilot")
        self.assertTrue(host.should_step_room(host.room))


class TestStateEncoding(unittest.TestCase):
    def setUp(self):
        self.host = SimHost(Simulator("coral_reef", 42))
        self.room = self.host.room
        self.players = [self.room.join(name, model_id=model)
                        for name, model in (("甲 Alpha", "x1"), ("Bravo", "falcon"),
                                            ("Charlie", "bluerov2_heavy"))]

    def assert_payload_matches(self, player=None):
        expected = json.loads(dumps({"type": "state", **self.host.viewer_state(self.room, player)}))
        actual = json.loads(self.host.viewer_payload(self.room, player))
        self.assertEqual(actual, expected)
        return actual

    def test_full_protocol_preserved_and_fleet_encoded_once(self):
        # Freeze only cache age, not simulator behavior or encoder output.
        with patch("qysim.room.time.monotonic", return_value=100.):
            self.room.state(self.players[0])
            with patch("qysim.server.dumps", wraps=dumps) as encode:
                for player in self.players:
                    self.host.viewer_payload(self.room, player)
                vehicle_encodings = [call for call in encode.call_args_list
                                     if "vehicle_id" in call.args[0]]
                self.assertEqual(len(vehicle_encodings), 3)
            for player in self.players:
                state = self.assert_payload_matches(player)
                self.assertEqual(state["vehicle_id"], player.vehicle_id)
                self.assertEqual(len(state["vehicles"]), 3)
                self.assertTrue(all("environment" in item and "paint_marks" in item
                                    for item in state["vehicles"]))
            self.assert_payload_matches()  # legacy spectator has primary telemetry

    def test_cache_refreshes_after_tick_reset_model_change_and_disconnect(self):
        self.assert_payload_matches(self.players[0])
        self.room.primary.vehicle.s.pos[0] += 1.
        self.room.tick += 1
        self.assert_payload_matches(self.players[0])
        self.room.select_model("v1", "falcon")
        self.assertEqual(self.assert_payload_matches(self.players[0])["model_id"], "falcon")
        self.room.reset("open_water", 7)
        self.assert_payload_matches(self.players[0])
        self.room.disconnect(self.players[0], self.players[0].generation)
        state = self.assert_payload_matches(self.players[1])
        self.assertEqual(state["room"]["host_id"], self.players[1].id)

    def test_controller_metadata_is_not_cached_with_fleet(self):
        self.host.qirc_enabled = True
        self.host.controller_revision = 1
        a = self.assert_payload_matches(self.players[0])
        self.host.controller_revision = 2
        self.host.sim.rc_physical.left_lr = 1700
        b = self.assert_payload_matches(self.players[0])
        self.assertEqual(a["controller"]["revision"], 1)
        self.assertEqual(b["controller"]["revision"], 2)
        self.assertEqual(b["controller"]["axes"]["left_lr"], 1700)
        self.assertNotIn("controller", self.assert_payload_matches(self.players[1]))

    def test_adapter_override_keeps_exact_state_without_duplicate_keys(self):
        state = self.host.viewer_state(self.room, self.players[0])
        state["battery"] = 17.5
        with patch.object(self.host, "viewer_state", return_value=dict(state)):
            payload = self.host.viewer_payload(self.room, self.players[0])
        decoded = json.loads(payload)
        self.assertEqual(decoded["battery"], 17.5)
        self.assertEqual(decoded, json.loads(dumps({"type": "state", **state})))


class TestWebSocket(unittest.IsolatedAsyncioTestCase):
    async def test_two_clients_join_control_and_reconnect(self):
        import websockets
        host = SimHost(Simulator("open_water", 9))

        async def receive_type(ws, kind):
            for _ in range(2000):
                message = json.loads(await asyncio.wait_for(ws.recv(), 5.))
                if message.get("type") == kind:
                    return message
            self.fail(f"No {kind} received")

        async with websockets.serve(host.viewer_handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            url = f"ws://127.0.0.1:{port}"
            async with websockets.connect(url) as a, websockets.connect(url) as b:
                await a.send(json.dumps({"type": "join", "name": "A"}))
                sa = await receive_type(a, "session")
                await b.send(json.dumps({"type": "join", "name": "B"}))
                sb = await receive_type(b, "session")
                self.assertNotEqual(sa["vehicle_id"], sb["vehicle_id"])
                await b.send(json.dumps({"type": "reset"}))
                self.assertEqual((await receive_type(b, "error"))["code"], "host_only")
                await a.send(json.dumps({"type": "rc", "seq": 0, "rc": {"rc_lock": 0, "right_ud": 1800}}))
                await asyncio.sleep(.1)
                self.assertEqual(host.room.vehicles[sa["vehicle_id"]].rc.right_ud, 1800)
                self.assertEqual(host.room.vehicles[sb["vehicle_id"]].rc.right_ud, 1500)
                async with websockets.connect(url) as bridge:
                    await bridge.send(json.dumps({"type": "attach_controller", "room_id": "training",
                                                   "resume_token": sa["resume_token"]}))
                    self.assertEqual((await receive_type(bridge, "controller_session"))["vehicle_id"], sa["vehicle_id"])
                    await bridge.send(json.dumps({"type": "rc", "seq": 0, "rc": {"right_ud": 1950}}))
                    await asyncio.sleep(.05)
                    await a.send(json.dumps({"type": "rc", "seq": 1, "rc": {"right_ud": 1500}}))
                    await asyncio.sleep(.05)
                    self.assertEqual(host.room.vehicles[sa["vehicle_id"]].rc.right_ud, 1950)
                    await bridge.send(json.dumps({"type": "reset"}))
                    self.assertEqual((await receive_type(bridge, "error"))["code"], "controller_only")
                    self.assertEqual(len(host.room.players), 2)
                async with websockets.connect(url) as reconnect:
                    await reconnect.send(json.dumps({"type": "join", "resume_token": sa["resume_token"]}))
                    restored = await receive_type(reconnect, "session")
                    self.assertEqual(restored["vehicle_id"], sa["vehicle_id"])
                    await a.send(json.dumps({"type": "rc", "seq": 2, "rc": {"rc_lock": 0}}))
                    self.assertEqual((await receive_type(a, "error"))["code"], "session_replaced")


if __name__ == "__main__":
    unittest.main()
