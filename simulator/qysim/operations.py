"""Shared work objects, bounded manipulator mechanics and inspection commands.

Arm linkage and hydrodynamic coefficients are training approximations, not a
manufacturer-calibrated robot model. Coordinates are FRD/NED, lengths metres.
"""
from __future__ import annotations

import math
import time
import numpy as np

from .physics import G, q_rot, q_conj
from .navigation import Waypoint

ARM_BASE = np.array([.30, -.12, .40])
ARM_LENGTHS = (.32, .30, .12)
JOINT_LIMITS = ((-95., 95.), (-65., 75.), (-120., 120.), (-100., 100.))
PAINT_COLORS = frozenset(("#f0c75e", "#ee704f", "#62cfe2", "#eef3e8"))
STICKERS = frozenset(("none", "hazard", "dive", "number"))
MAX_PAINT_MARKS = 300


def finite_vector(value, count):
    a = np.asarray(value, dtype=float)
    if a.shape != (count,) or not np.isfinite(a).all():
        raise ValueError(f"需要 {count} 個有限數值")
    return a


def arm_points(joints):
    yaw, shoulder, elbow, wrist = np.radians(joints)
    points = [ARM_BASE.copy()]
    angle = shoulder
    for length, bend in zip(ARM_LENGTHS, (0., elbow, wrist)):
        angle += bend
        points.append(points[-1] + length * np.array([
            math.cos(angle) * math.cos(yaw), math.cos(angle) * math.sin(yaw), math.sin(angle)]))
    return np.asarray(points)


def ensure_objects(sim):
    world = sim.world
    if hasattr(world, "work_objects"):
        return world.work_objects
    objects = {}
    origin = np.asarray(sim.scenario.start_pos, float)
    for i, (label, mass, buoyancy) in enumerate((("樣品容器", 2., 1.5), ("回收工具", 4., 1.), ("重型回收物", 14., 2.))):
        for offset in range(20):
            p = origin + np.array([2. + i * 1.1, (offset - 10) * .5, 0.])
            depth = world.depth_at(p) if hasattr(world, "depth_at") else world.seabed_depth
            p[2] = depth - .15
            if world.sdf(p)[0] >= .12:
                break
        else:
            continue
        key = f"work-{i}"
        objects[key] = dict(id=key, label=label, pos=p, vel=np.zeros(3), mass=mass,
                            buoyancy_kg=buoyancy, radius=.12, held_by=None)
    world.work_objects = objects
    return objects


def step_objects(world, dt, t):
    """Called once per room tick, never once per vehicle."""
    for ob in getattr(world, "work_objects", {}).values():
        if ob["held_by"] is not None or ob.get("anchored"):
            continue
        pos, vel = ob["pos"], ob["vel"]
        current = world.current.sample(pos, world.seabed_depth, t) if hasattr(world.current, "sample") else world.current.at(pos[2], world.seabed_depth)
        relative = vel - current
        force = -3. * relative * np.linalg.norm(relative)
        force[2] += (ob["mass"] - ob["buoyancy_kg"]) * G
        vel += force / (ob["mass"] + 1.) * dt
        proposed = pos + vel * dt
        distance, normal, _ = world.sdf(proposed)
        if distance < ob["radius"]:
            proposed += normal * (ob["radius"] - distance)
            vel -= min(0., float(np.dot(vel, normal))) * normal
            vel *= math.exp(-8. * dt)
        ob["pos"] = proposed


class VehicleOperations:
    def __init__(self, sim):
        self.sim = sim
        self.joints = np.array([0., -15., 30., -15.])
        self.target = self.joints.copy()
        self.grip = self.grip_target = 1.
        self.held = None
        self.status = "就緒"
        self.markers = []
        self.waypoints = []
        self.altitude = None
        ensure_objects(sim)

    @property
    def vehicle_id(self):
        return str(getattr(self.sim, "vehicle_id", "local"))

    @property
    def has_arm(self):
        return getattr(self.sim, "model_id", "x1") == "falcon"

    def release(self):
        objects = ensure_objects(self.sim)
        if self.held in objects:
            expedition = getattr(self.sim.world, "expedition", None)
            if expedition:
                expedition.release(self.sim, self.held)
            objects[self.held]["held_by"] = None
            objects[self.held]["vel"] = self.sim.vehicle.world_velocity().copy()
        self.held = None

    def command(self, msg):
        action = msg.get("action")
        sim = self.sim
        try:
            if action == "mission_mode":
                from .mission_modes import MissionRun
                if msg.get("mode") == "expedition" and getattr(sim.world, "mission_run", None).mode == "expedition":
                    return {"ok": True, "action": action, "mission": sim.world.mission_run.state(sim)}
                sim.world.mission_run = MissionRun(sim, msg.get("mode"))
                return {"ok": True, "action": action, "mission": sim.world.mission_run.state(sim)}
            elif action in ("expedition_start", "expedition_cancel", "observation_photo", "expedition_mark"):
                from .expedition import ensure_expedition
                if sim.world.mission_run.mode != "expedition":
                    raise ValueError("請先進入海洋探索與工程模式")
                return ensure_expedition(sim).command(sim, action, msg)
            elif action == "mission_photo":
                from .mission_modes import ensure_mission
                photo = sim._take_photo()
                return {"ok": True, "action": action, "file": photo, "mission": ensure_mission(sim).state(sim)}
            elif action == "paint":
                return self._paint(msg)
            elif action == "appearance":
                sticker = msg.get("sticker")
                if not isinstance(sticker, str) or sticker not in STICKERS:
                    raise ValueError("Unknown sticker")
                sim.appearance = {"sticker": sticker}
            elif action == "arm":
                if not self.has_arm:
                    raise ValueError("此機型未安裝機械臂")
                values = finite_vector(msg.get("joints", self.target), 4)
                grip = float(msg.get("grip", self.grip_target))
                if not math.isfinite(grip):
                    raise ValueError("夾爪數值無效")
                self.target = np.clip(values, np.array(JOINT_LIMITS)[:, 0], np.array(JOINT_LIMITS)[:, 1])
                self.grip_target = float(np.clip(grip, 0., 1.))
            elif action == "mark":
                if len(self.markers) >= 500:
                    raise ValueError("巡檢標記已達 500 個")
                self.markers.append(dict(id=f"{self.vehicle_id}-m{len(self.markers)+1}",
                    label=str(msg.get("label") or "巡檢點")[:80], t=sim.t,
                    vehicle_id=self.vehicle_id, pos=sim.vehicle.s.pos.tolist(), q=sim.vehicle.s.q.tolist()))
            elif action == "waypoint":
                p = finite_vector(msg.get("pos", sim.vehicle.s.pos), 3)
                if len(self.waypoints) >= 200 or sim.world.sdf(p)[0] < .4 or p[2] < .4:
                    raise ValueError("航點過多或太接近障礙／水面")
                self.waypoints.append(p.tolist())
            elif action == "coverage":
                width = float(msg.get("width", 8.))
                length = float(msg.get("length", 10.))
                spacing = float(msg.get("spacing", 2.))
                if not all(math.isfinite(x) for x in (width, length, spacing)) or not (1 <= width <= 50 and 1 <= length <= 50 and .5 <= spacing <= 10):
                    raise ValueError("覆蓋範圍需為 1–50 m，間隔 0.5–10 m")
                origin = sim.vehicle.s.pos.copy()
                yaw = sim.yaw
                fwd, right = np.array([math.cos(yaw), math.sin(yaw), 0]), np.array([-math.sin(yaw), math.cos(yaw), 0])
                route = []
                for i, offset in enumerate(np.linspace(0., width, math.ceil(width / spacing)+1)):
                    for along in ((0., length) if i % 2 == 0 else (length, 0.)):
                        route.append((origin + right * offset + fwd * along).tolist())
                self._validate_route(route)
                self.waypoints = route
            elif action == "route_start":
                if not self.waypoints:
                    raise ValueError("請先加入航點或產生覆蓋航線")
                self._validate_route([sim.vehicle.s.pos.tolist(), *self.waypoints])
                self.altitude = None
                sim.nav.route = [Waypoint(*p, sim.yaw) for p in self.waypoints]
                sim.nav.route_i = 0
                sim.nav.mode, sim.nav.nav_status, sim.nav.paused = "V_NAVI", 1, False
            elif action == "route_stop":
                sim.nav.stop()
                self.altitude = None
            elif action == "route_clear":
                sim.nav.stop()
                self.waypoints = []
            elif action == "altitude":
                value = msg.get("metres")
                if value is None:
                    self.altitude = None
                else:
                    value = float(value)
                    if not math.isfinite(value) or not .5 <= value <= 30:
                        raise ValueError("定高需為 0.5–30 m")
                    sim.nav.stop()
                    self.altitude = value
                    sim.rc.keep_depth = 1
            else:
                raise ValueError("未知作業指令")
            return {"ok": True, "action": action}
        except (ValueError, TypeError, OverflowError) as exc:
            return {"ok": False, "action": action, "message": str(exc)}

    def _paint(self, msg):
        """Validate a client surface hit; store bounded, shared room artwork.

        Client raycasts use the rendered mesh. Server physics uses coarser
        habitat proxies, so it checks reach/depth rather than mesh coincidence.
        Wall-clock limiting also applies while the simulation is paused.
        """
        pos = finite_vector(msg.get("pos"), 3)
        normal = finite_vector(msg.get("normal"), 3)
        radius = float(msg.get("radius", .12))
        color = msg.get("color")
        length = float(np.linalg.norm(normal))
        if not math.isfinite(radius) or not .03 <= radius <= .3:
            raise ValueError("Paint radius must be 0.03 to 0.3 metres")
        if not isinstance(color, str) or color not in PAINT_COLORS:
            raise ValueError("Unknown paint color")
        if not .99 <= length <= 1.01:
            raise ValueError("Paint normal must be a unit vector")
        if pos[2] <= 0 or np.linalg.norm(pos - self.sim.vehicle.s.pos) > 3.:
            raise ValueError("Paint surface must be underwater and within 3 metres")
        world = self.sim.world
        now = time.monotonic()
        last = world.paint_last_at.get(self.vehicle_id, -math.inf)
        if now - last < .1 - 1e-9:
            raise ValueError("Paint rate is limited to 10 marks per second")
        world.paint_serial += 1
        mark = dict(id=f"paint-{world.paint_serial}", pos=pos.tolist(),
                    normal=(normal / length).tolist(), radius=radius,
                    color=color, owner_id=self.vehicle_id)
        world.paint_marks.append(mark)
        del world.paint_marks[:-MAX_PAINT_MARKS]
        world.paint_last_at[self.vehicle_id] = now
        return {"ok": True, "action": "paint", "id": mark["id"]}

    def _validate_route(self, route):
        for a, b in zip(route, route[1:]):
            a, b = np.asarray(a), np.asarray(b)
            for p in np.linspace(a, b, max(2, math.ceil(np.linalg.norm(b-a)/.3)+1)):
                if p[2] < .4 or self.sim.world.sdf(p)[0] < .4:
                    raise ValueError("航線穿越障礙或太接近海床，請縮小範圍或調整深度")

    def step(self, dt):
        sim, vehicle = self.sim, self.sim.vehicle
        wrench = np.zeros(6)
        if self.altitude is not None:
            depth = sim.world.depth_at(vehicle.s.pos) if hasattr(sim.world, "depth_at") else sim.world.seabed_depth
            sim.controller.depth_hold = max(.4, depth - self.altitude)
            sim.rc.keep_depth = 1
        if not self.has_arm:
            self.release()
            return wrench
        # A lost controller freezes the requested joints; locked thrusters do not disable tools.
        candidate = self.joints + np.clip(self.target-self.joints, -25.*dt, 25.*dt)
        objects = ensure_objects(sim)
        points = arm_points(candidate)
        world_points = vehicle.s.pos + np.array([q_rot(vehicle.s.q, p) for p in points])
        # The complete linkage fits inside this sphere. Most flight takes place
        # clear of structures, so avoid eighteen surface queries per arm per tick.
        envelope = float(np.linalg.norm(ARM_BASE)) + sum(ARM_LENGTHS) + .15
        near_surface = sim.world.sdf(vehicle.s.pos)[0] < envelope
        blocked = near_surface and any(sim.world.sdf(p)[0] < .035 for a,b in zip(world_points, world_points[1:]) for p in np.linspace(a,b,6))
        if near_surface and self.held in objects:
            blocked = blocked or sim.world.sdf(world_points[-1])[0] < objects[self.held]["radius"]
        if not blocked:
            self.joints = candidate
            self.status = "夾持中" if self.held else "就緒"
        else:
            self.status = "機械臂接觸障礙"
        self.grip += float(np.clip(self.grip_target-self.grip, -dt, dt))
        tip_body = arm_points(self.joints)[-1]
        tip = vehicle.s.pos + q_rot(vehicle.s.q, tip_body)
        if self.grip > .55:
            self.release()
        elif self.grip < .25 and self.held is None:
            for ob in objects.values():
                if ob.get("graspable") is False:
                    continue
                if ob["held_by"] is None and np.linalg.norm(ob["pos"]-tip) < ob["radius"] + .055:
                    if ob["mass"] > 10.:
                        self.status = "超過 10 kg 估算負載限制"
                        continue
                    ob["held_by"], self.held = self.vehicle_id, ob["id"]
                    expedition = getattr(sim.world, "expedition", None)
                    if expedition:
                        expedition.grasp(sim, ob["id"])
                    break
        if self.held in objects:
            ob = objects[self.held]
            distance, normal, _ = sim.world.sdf(tip)
            if distance < ob["radius"]:
                ob["pos"] = tip + normal * (ob["radius"] - distance)
                self.release()
                self.status = "載荷接觸障礙，物件已脫落"
                return wrench
            ob["pos"] = tip.copy()
            rel = vehicle.world_velocity() - vehicle.current_ned
            force = -3. * rel * np.linalg.norm(rel)
            force[2] += (ob["mass"]-ob["buoyancy_kg"]) * G
            body_force = q_rot(q_conj(vehicle.s.q), force)
            wrench[:3], wrench[3:] = body_force, np.cross(tip_body, body_force)
            if np.linalg.norm(force) > 100.:
                self.release()
                self.status = "超載，物件已脫落"
                wrench[:] = 0.
        return wrench

    def state(self):
        objects = ensure_objects(self.sim)
        return dict(arm=dict(available=self.has_arm, joints=self.joints.tolist(), grip=self.grip,
                    held=self.held, status=self.status, estimated=True),
                    objects=[{k: (v.tolist() if isinstance(v, np.ndarray) else v) for k,v in ob.items() if k != "vel"} for ob in objects.values()],
                    markers=self.markers, waypoints=self.waypoints, altitude=self.altitude)


def enu_to_ned(point):
    east, north, up = finite_vector(point, 3)
    return [float(north), float(east), float(-up)]


def ned_to_enu(point):
    north, east, down = finite_vector(point, 3)
    return [float(east), float(north), float(-down)]
