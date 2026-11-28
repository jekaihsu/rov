"""Viewer WebSocket resilience: bad packets, unknown types, reconnect and long ticks."""
import asyncio
import json
import unittest

from qysim.engine import Simulator
from qysim.server import SimHost, parse_viewer_message


class ParseViewerMessageTests(unittest.TestCase):
    def test_empty_and_valid(self):
        self.assertEqual(parse_viewer_message(""), (None, None))
        msg, err = parse_viewer_message('{"type":"join","name":"A"}')
        self.assertEqual(msg["type"], "join")
        self.assertIsNone(err)

    def test_bad_json_and_non_object(self):
        msg, err = parse_viewer_message("{")
        self.assertIsNone(msg)
        self.assertEqual(err["code"], "invalid_command")
        msg, err = parse_viewer_message("[1,2]")
        self.assertIsNone(msg)
        self.assertEqual(err["code"], "invalid_command")
        msg, err = parse_viewer_message(b"\xff\xfe")
        self.assertIsNone(msg)
        self.assertEqual(err["code"], "invalid_command")


class HandleViewerResilienceTests(unittest.TestCase):
    def setUp(self):
        self.host = SimHost(Simulator("open_water", 3))
        self.player = self.host.room.join("Pilot")

    def test_unknown_type_is_quietly_ignored(self):
        # Forward-compatible clients may send newer message types; the host must not reply invalid_command.
        reply = self.host.handle_viewer(
            {"type": "not_a_real_command"},
            room=self.host.room,
            player=self.player,
        )
        self.assertIsNone(reply)
        self.host.room.step(0.01)
        self.assertTrue(self.player.connected)

    def test_bad_rc_keeps_physics_alive(self):
        with self.assertRaises(ValueError):
            self.host.handle_viewer(
                {"type": "rc", "seq": 1, "rc": {"right_ud": float("nan")}},
                room=self.host.room,
                player=self.player,
            )
        self.host.room.step(0.01)
        self.assertTrue(all(
            __import__("numpy").isfinite(sim.vehicle.s.pos).all()
            for sim in self.host.room.vehicles.values()
        ))

    def test_long_run_ticks_do_not_diverge(self):
        import numpy as np
        for _ in range(500):
            self.host.room.step(0.01)
        state = self.host.viewer_state(self.host.room, self.player)
        self.assertGreater(state["t"], 4.0)
        self.assertTrue(np.isfinite(state["pos"]).all())


class WebSocketResilienceTests(unittest.IsolatedAsyncioTestCase):
    async def test_bad_packets_then_valid_join(self):
        import websockets

        host = SimHost(Simulator("open_water", 11))

        async def receive_type(ws, kind):
            for _ in range(2000):
                message = json.loads(await asyncio.wait_for(ws.recv(), 5.0))
                if message.get("type") == kind:
                    return message
            self.fail(f"No {kind} received")

        async with websockets.serve(host.viewer_handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            url = f"ws://127.0.0.1:{port}"
            async with websockets.connect(url) as ws:
                await receive_type(ws, "world")
                await ws.send("{")
                err = await receive_type(ws, "error")
                self.assertEqual(err["code"], "invalid_command")
                await ws.send("[]")
                err = await receive_type(ws, "error")
                self.assertEqual(err["code"], "invalid_command")
                await ws.send(json.dumps({"type": "totally_unknown"}))
                err = await receive_type(ws, "error")
                self.assertEqual(err["code"], "join_required")
                await ws.send(json.dumps({"type": "join", "name": "Recovered"}))
                session = await receive_type(ws, "session")
                self.assertIn("vehicle_id", session)
                self.assertIn("player_id", session)
                await ws.send(json.dumps({"type": "rc", "seq": 0, "rc": {"rc_lock": 0, "right_ud": 1700}}))
                await asyncio.sleep(0.1)
                self.assertEqual(host.room.vehicles[session["vehicle_id"]].rc.right_ud, 1700)
                await ws.send(json.dumps({"type": "nope"}))
                # Unknown types are ignored; no error reply and the seat stays connected.
                await asyncio.sleep(0.1)
                host.room.step(0.01)
                self.assertTrue(host.room.players[session["player_id"]].connected)
                self.assertEqual(host.room.vehicles[session["vehicle_id"]].rc.right_ud, 1700)

    async def test_disconnect_and_resume(self):
        import websockets

        host = SimHost(Simulator("open_water", 12))

        async def receive_type(ws, kind):
            for _ in range(2000):
                message = json.loads(await asyncio.wait_for(ws.recv(), 5.0))
                if message.get("type") == kind:
                    return message
            self.fail(f"No {kind} received")

        async with websockets.serve(host.viewer_handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            url = f"ws://127.0.0.1:{port}"
            async with websockets.connect(url) as first:
                await first.send(json.dumps({"type": "join", "name": "A"}))
                session = await receive_type(first, "session")
                token = session["resume_token"]
                vehicle = session["vehicle_id"]
                player_id = session["player_id"]
            # Allow the handler's finally block to mark the seat disconnected.
            for _ in range(50):
                if not host.room.players[player_id].connected:
                    break
                await asyncio.sleep(0.02)
            self.assertFalse(host.room.players[player_id].connected)
            async with websockets.connect(url) as second:
                await second.send(json.dumps({"type": "join", "resume_token": token}))
                restored = await receive_type(second, "session")
                self.assertEqual(restored["vehicle_id"], vehicle)
                self.assertGreater(restored["generation"], session["generation"])


if __name__ == "__main__":
    unittest.main()
