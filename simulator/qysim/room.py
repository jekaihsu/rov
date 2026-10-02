"""Authoritative shared-world room and exclusive pilot leases."""
from __future__ import annotations

from dataclasses import dataclass
import secrets
import time
import numpy as np

from .engine import Simulator
from .physics import q_conj, q_rot


@dataclass
class Player:
    id: str
    vehicle_id: str
    name: str
    token: str
    connected: bool = True
    last_input: float = 0.0
    disconnected_at: float = 0.0
    seq: int = -1
    generation: int = 1
    bridge_seq: int = -1


class Room:
    capacity = 3
    input_timeout = 0.6
    reconnect_grace = 30.0

    def __init__(self, sim: Simulator, room_id="training"):
        self.id = room_id
        sim.vehicle_id = "v1"
        self.vehicles = {"v1": sim}
        sim.room = self
        self.players: dict[str, Player] = {}
        self.host_id = None
        self.rng = np.random.default_rng(sim.scenario.seed)
        self.tick = 0
        self._snapshot = None
        self._snapshot_at = 0.
        self._snapshot_tick = -1

    @property
    def primary(self):
        return self.vehicles["v1"]

    @staticmethod
    def lock(sim):
        if not sim.input_latched:
            sim.control_generation += 1
        sim.input_latched = True
        for rc in (sim.rc_physical, sim.rc_sdk):
            rc.centre_sticks()
            rc.rc_lock = 1
            rc.photo = rc.record = 0
        sim.remote_control = False
        sim.nav.mode = "IDLE"
        sim.nav.hold = None
        if hasattr(sim, "operations"):
            sim.operations.target = sim.operations.joints.copy()
            sim.operations.grip_target = sim.operations.grip

    def join(self, name="Pilot", resume_token=None, model_id="x1", now=None):
        self._snapshot = None
        now = time.monotonic() if now is None else now
        self.expire(now)
        if resume_token:
            player = next((p for p in self.players.values() if secrets.compare_digest(p.token, str(resume_token))), None)
            if player is not None:
                player.connected = True
                player.generation += 1
                player.seq = -1
                player.last_input = now
                self.lock(self.vehicles[player.vehicle_id])
                if self.host_id is None:
                    self.host_id = player.id
                return player
        if len(self.players) >= self.capacity:
            raise ValueError("room_full")
        used = {p.vehicle_id for p in self.players.values()}
        vid = next(f"v{i}" for i in range(1, self.capacity + 1) if f"v{i}" not in used)
        if vid not in self.vehicles:
            base = self.primary
            sim = Simulator(base.scenario.key, base.scenario.seed, model_id=model_id,
                            vehicle_id=vid, shared_world=base.world)
            sim.t = base.t
            sim.paused = base.paused
            self.vehicles[vid] = sim
            sim.room = self
            self._spawn(sim, int(vid[1:]) - 1)
        elif self.vehicles[vid].model_id != model_id:
            self.select_model(vid, model_id)
        player = Player(secrets.token_hex(6), vid, str(name)[:32] or "Pilot", secrets.token_urlsafe(24), last_input=now)
        self.players[player.id] = player
        if self.host_id is None:
            self.host_id = player.id
        return player

    def _spawn(self, sim, index):
        if not index:
            return
        origin = np.asarray(sim.scenario.start_pos, float)
        # Spread deployment points; select a clear position for each hull.
        for ring in range(1, 9):
            candidate = origin + np.array([0.0, index * 2.0 * ring, 0.0])
            distance, _, _ = sim.world.sdf(candidate)
            if distance > 0.8 and all(np.linalg.norm(candidate - other.vehicle.s.pos) > 1.5
                                      for other in self.vehicles.values() if other is not sim):
                delta = candidate - sim.vehicle.s.pos
                sim.vehicle.s.pos[:] = candidate
                sim.tether.x[:] += delta
                sim.tether.x[0] = sim.tether.spool
                return

    def select_model(self, vehicle_id, model_id):
        self._snapshot = None
        from .vehicles import get_vehicle_definition
        get_vehicle_definition(model_id)  # validate before replacing anything
        sim = self.vehicles[vehicle_id]
        sim.operations.release()
        old_t, paused = sim.t, sim.paused
        world = sim.world
        sim.model_id = model_id
        sim.load_scenario(sim.scenario.key, sim.scenario.seed, shared_world=world)
        sim.t, sim.paused = old_t, paused
        self._spawn(sim, int(vehicle_id[1:]) - 1)

    def disconnect(self, player, generation, now=None):
        if player.generation != generation:
            return
        self._snapshot = None
        player.connected = False
        player.disconnected_at = time.monotonic() if now is None else now
        self.lock(self.vehicles[player.vehicle_id])
        self.vehicles[player.vehicle_id].operations.release()
        if self.host_id == player.id:
            self.host_id = next((p.id for p in self.players.values() if p.connected), None)

    def expire(self, now=None):
        now = time.monotonic() if now is None else now
        for pid, p in list(self.players.items()):
            if not p.connected and now - p.disconnected_at > self.reconnect_grace:
                self.vehicles[p.vehicle_id].operations.release()
                del self.players[pid]
                self._snapshot = None
                if p.vehicle_id != "v1":
                    del self.vehicles[p.vehicle_id]

    def input(self, player, seq, now=None, *, bridge=False):
        field = "bridge_seq" if bridge else "seq"
        if not isinstance(seq, int) or isinstance(seq, bool) or seq <= getattr(player, field):
            return False
        setattr(player, field, seq)
        player.last_input = time.monotonic() if now is None else now
        return True

    def check_timeouts(self, now=None, usb_vehicle=None):
        now = time.monotonic() if now is None else now
        self.expire(now)
        for p in self.players.values():
            if p.connected and now - p.last_input > self.input_timeout and p.vehicle_id != usb_vehicle:
                self.lock(self.vehicles[p.vehicle_id])

    def reset(self, key=None, seed=None):
        self._snapshot = None
        base = self.primary
        for sim in self.vehicles.values():
            sim.operations.release()
        base.load_scenario(key or base.scenario.key, base.scenario.seed if seed is None else seed)
        for vid, sim in self.vehicles.items():
            if sim is not base:
                sim.load_scenario(base.scenario.key, base.scenario.seed, shared_world=base.world)
                self._spawn(sim, int(vid[1:]) - 1)
        self.rng = np.random.default_rng(base.scenario.seed)
        self.tick = 0

    def step(self, dt):
        base = self.primary
        if base.paused:
            return
        world = base.world
        world.current.step_gust(dt, self.rng)
        self._vehicle_contacts()
        for sim in self.vehicles.values():
            sim.step(dt, update_world=False)
        world.step(dt, vehicles=[{"id": vid, "pos": sim.vehicle.s.pos, "vel": sim.vehicle.world_velocity(),
                                 "thrust": float(np.mean(np.abs(sim.vehicle.s.thrust)) / sim.vehicle.p.thruster_max)}
                                 for vid, sim in self.vehicles.items()])
        from .operations import step_objects
        step_objects(world, dt, base.t)
        self.tick += 1

    def _vehicle_contacts(self):
        sims = list(self.vehicles.values())
        for sim in sims:
            sim.tool_wrench = np.zeros(6)
        for i, a in enumerate(sims):
            for b in sims[i + 1:]:
                delta = a.vehicle.s.pos - b.vehicle.s.pos
                distance = float(np.linalg.norm(delta))
                radius = float(a.vehicle.definition.hull_radius + b.vehicle.definition.hull_radius + 0.5)
                if distance >= radius:
                    continue
                normal = delta / distance if distance > 1e-6 else np.array([0., 1., 0.])
                approach = float(np.dot(a.vehicle.world_velocity() - b.vehicle.world_velocity(), normal))
                force = normal * min(1500., max(0., 1800. * (radius - distance) - 150. * approach))
                a.tool_wrench[:3] += q_rot(q_conj(a.vehicle.s.q), force)
                b.tool_wrench[:3] -= q_rot(q_conj(b.vehicle.s.q), force)

    def session(self, player):
        return {"type": "session", "protocol": 2, "room_id": self.id, "player_id": player.id, "vehicle_id": player.vehicle_id,
                "resume_token": player.token, "generation": player.generation,
                "is_host": self.host_id == player.id, "capacity": self.capacity}

    def state(self, player=None):
        selected = self.vehicles[player.vehicle_id] if player else self.primary
        now = time.monotonic()
        # Range sensors and operations telemetry are expensive. All viewers of a
        # room share one immutable fleet snapshot per publication interval/tick.
        if self._snapshot is None or self._snapshot_tick != self.tick or now - self._snapshot_at >= 1 / 30:
            owners = {p.vehicle_id: p.id for p in self.players.values()}
            self._snapshot = [{**sim.viewer_state(), "id": vid, "owner_id": owners.get(vid)}
                              for vid, sim in self.vehicles.items()]
            self._snapshot_tick = self.tick
            self._snapshot_at = time.monotonic()
        state = dict(next(s for s in self._snapshot if s["id"] == selected.vehicle_id))
        state["vehicles"] = self._snapshot
        state["tick"] = self.tick
        state["room"] = {"id": self.id, "host_id": self.host_id, "capacity": self.capacity,
                         "players": [{"id": p.id, "vehicle_id": p.vehicle_id, "name": p.name,
                                      "connected": p.connected} for p in self.players.values()]}
        return state
