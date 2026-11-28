"""Swept vehicle contact against the world's shared obstacle and terrain distance fields."""
from __future__ import annotations

import math

import numpy as np

from .physics import cross3, q_from_axis_angle, q_matrix, q_mul
from .world import ContactEvent

# Wet contact against the vehicle frame. Provisional simulation values (e, Coulomb mu).
MATERIALS = {
    "steel": (.22, .30),
    "concrete": (.12, .55),
    "net": (.0, .65),
    "sand": (.04, .55),
    "mud": (.0, .70),
    "biofouling": (.08, .45),
}
NET_TRAVEL = .065  # m; backing limit smaller than the smallest capsule radius
NET_K = 4500.0     # N/m assumed local panel stiffness
NET_C = 90.0       # N s/m
SKIN = 2e-5

# Escape directions for a legacy save or a teleport that starts inside overlapping solids.
_ESCAPE = np.array([(x, y, z) for z in (-1., 0., 1.) for x in (-1., 0., 1.)
                    for y in (-1., 0., 1.) if x or y or z])
_ESCAPE /= np.linalg.norm(_ESCAPE, axis=1)[:, None]


def material(world, index):
    if index < 0:
        bed = world.silt_field.seabed_type
        if bed == "rock":
            return "concrete"
        return "mud" if bed in ("mud", "silt", "fluff") else "sand"
    kind = world.obstacles[index].kind
    if kind in ("pen_net", "net"):
        return "net"
    if kind in ("wall", "pier", "caisson", "quay", "debris_block", "concrete", "pen_anchor", "scour"):
        return "concrete"
    if kind == "habitat" and world.obstacles[index].name.startswith("rock-"):
        return "concrete"
    if kind in ("habitat", "biofouling", "marine_growth"):
        return "biofouling"
    return "steel"


class HullContact:
    def __init__(self, vehicle):
        definition = vehicle.definition
        # Two longitudinal rounded pontoons. Cover each capsule by overlapping
        # balls enlarged for the half-spacing at the seam (conservative cover).
        radius = definition.hull_radius * .78
        lateral = definition.hull_radius * .52
        half = max(abs(c[0]) for c in definition.hull_centres)
        xs = np.linspace(-half, half, math.ceil(2 * half / (.6 * radius)) + 1)
        cover = math.hypot(radius, (xs[1] - xs[0]) / 2)
        balls = [((x, y, 0.), cover) for x in xs for y in (-lateral, lateral)]
        balls.extend(definition.hull_extra)
        self.points = np.array([p for p, _ in balls])
        self.radii = np.array([r for _, r in balls])
        self.extent = float(np.max(np.linalg.norm(self.points, axis=1) + self.radii))
        self.spacing = .35 * float(min(self.radii))
        self.active = set()
        self.net_load = None

    def resolve(self, world, vehicle, start, q0, dt, t, vehicle_id):
        self.net_load = None
        s = vehicle.s
        end, q1 = s.pos, s.q
        lo = np.minimum(start, end) - self.extent
        hi = np.maximum(start, end) + self.extent
        candidates = world.near(lo, hi, self.spacing)
        relief = world.terrain.relief if world.terrain else 0.
        if not candidates and hi[2] < world.seabed_depth - relief - SKIN:
            self.active.clear()
            return
        hit = self.first_contact(world, candidates, start, end, q0, q1, s.omega, dt)
        if hit is None:
            self.active.clear()
            return
        pos, q, previous_pos, previous_q, penetration, normals, ids = hit
        rotation = q_matrix(q)
        s.pos, s.q = pos.copy(), q
        velocity_before = s.vel.copy()
        touched = set()
        for index in np.unique(ids[penetration >= -SKIN]):
            mask = ids == index
            depth = penetration[mask].max()
            k = int(np.argmax(np.where(mask, penetration, -np.inf)))
            normal = normals[k]
            # Coplanar support points share a resultant through their centroid.
            length = float(np.linalg.norm(normal))
            if length < 1e-6:
                # A distance-field medial axis has no defined normal. Stop the
                # sweep on its last clear pose instead of inventing a direction.
                self.recover(world, s, previous_pos, previous_q)
                return
            normal = normal / length
            face = mask & (penetration >= depth - SKIN) & ((normals @ normal) > .999 * np.linalg.norm(normals, axis=1))
            arm = (self.points[face] - self.radii[face, None] * (normal @ rotation)).mean(axis=0)
            mat = material(world, index)
            impulse, speed = self.respond(vehicle, arm, normal @ rotation, mat, depth, dt,
                                          index not in self.active)
            name = "seabed" if index < 0 else world.obstacles[index].name
            point = pos + rotation @ arm
            if mat == "net" and depth > 0:
                deflection = min(NET_TRAVEL, depth)
                self.net_load = {"point": (point + normal * depth).tolist(),
                                 "offset": (-normal * deflection).tolist()}
            if index not in self.active:
                severe = bool(speed > .8 and impulse >= 3.)
                severity = "severe" if severe else "hard" if speed > .3 and impulse >= 1. else "touch"
                where = "front" if arm[0] > .15 else "rear" if arm[0] < -.15 else "mid"
                where += "-stbd" if arm[1] > .1 else "-port" if arm[1] < -.1 else ""
                world.events.append(ContactEvent(round(t, 2), name, round(speed, 2), severity, where,
                                                 vehicle_id, mat, round(impulse, 3), severe))
                if index < 0:
                    world.silt_field.contact(point, speed, vehicle_id, impact=True)
            if index < 0:
                slide = np.linalg.norm(vehicle.world_velocity()[:2])
                world.silt_field.contact(point, slide, vehicle_id, impact=False)
            touched.add(index)
        s.accel += (s.vel - velocity_before) / dt
        self.active = touched
        if penetration.max() > 2 * self.spacing:
            # A normal swept step travels at most one sample spacing. Large
            # overlap is an invalid starting configuration (e.g. a saved pose).
            self.recover(world, s, previous_pos, previous_q)
            return
        # Re-query after each translation: another face can constrain the
        # same hull point at a corner. Revert if a jam cannot be projected.
        for _ in range(8):
            effective = penetration.copy()
            for index in np.unique(ids[penetration > 0]):
                if material(world, index) == "net":
                    effective[ids == index] -= NET_TRAVEL
            if np.any(effective != penetration):
                solid = [i for i in candidates if material(world, i) != "net"]
                dist, rigid_normals, _ = self.query(world, s.pos + self.points @ rotation.T, solid)
                rigid = self.radii - dist
                closer = rigid > effective
                effective[closer] = rigid[closer]
                normals[closer] = rigid_normals[closer]
            k = int(np.argmax(effective))
            if effective[k] <= 1e-9:
                return
            grad = normals[k]
            slope2 = grad @ grad
            if slope2 < 1e-8:
                break
            s.pos += (effective[k] + SKIN / 2) * grad / slope2
            if np.any(s.pos - self.extent < lo - self.spacing) or np.any(s.pos + self.extent > hi + self.spacing):
                candidates = world.near(s.pos - self.extent, s.pos + self.extent, self.spacing)
            dist, normals, ids = self.query(world, s.pos + self.points @ rotation.T, candidates)
            penetration = self.radii - dist
        self.recover(world, s, previous_pos, previous_q)

    def recover(self, world, state, pos, q):
        """Use the preceding clear pose, or locate free water around an embedded starting pose."""
        state.q = q
        cand = world.near(pos - self.extent, pos + self.extent, SKIN)
        dist, _, ids = self.query(world, pos + self.points @ q_matrix(q).T, cand)
        for i in np.unique(ids):
            if material(world, i) == "net":
                dist[ids == i] += NET_TRAVEL
        if np.all(dist >= self.radii):
            state.pos = pos.copy()
            return
        radius = self.extent + max(0., float(np.max(self.radii - dist)))
        for _ in range(24):
            trials = pos + radius * _ESCAPE
            trials[:, 2] = np.clip(trials[:, 2], 0., world.seabed_depth - self.extent - SKIN)
            cand = world.near(trials.min(axis=0), trials.max(axis=0), self.extent)
            # A clear bounding sphere guarantees the entire oriented proxy fits.
            clear = world.sdf_many(trials, cand, hull_contact=True)[0] > self.extent
            if clear.any():
                choices = trials[clear]
                state.pos = choices[np.argmin(np.linalg.norm(choices - pos, axis=1))]
                return
            radius *= 2
        raise ValueError("No free water for the vehicle collision envelope")

    @staticmethod
    def query(world, points, candidates):
        # An isolated surface above the bed is particularly common at a wreck
        # or alongside a ship. Avoid computing terrain and unrelated normals.
        relief = world.terrain.relief if world.terrain else 0.
        if len(candidates) == 1:
            index = candidates[0]
            ob = world.obstacles[index]
            dist, normal = getattr(ob, "contact_sdf_many", ob.sdf_many)(points)
            ids = np.full(len(points), index)
            if points[:, 2].max() >= world.seabed_depth - relief - 1.:
                if relief:
                    depth, up = world.terrain.sample_many(points)
                    bed = (depth - points[:, 2]) * -up[:, 2]
                else:
                    bed = world.seabed_depth - points[:, 2]
                floor = bed <= dist
                dist[floor] = bed[floor]
                normal[floor] = up[floor] if relief else (0., 0., -1.)
                ids[floor] = -1
            return dist, normal, ids
        return world.sdf_many(points, candidates, hull_contact=True)

    def first_contact(self, world, candidates, start, end, q0, q1, omega, dt):
        """Test translations and rotations in bounded batches and keep the first hit in time order."""
        delta = end - start
        angle = float(np.linalg.norm(omega)) * dt
        steps = max(1, math.ceil((np.linalg.norm(delta) + self.extent * angle) / self.spacing))
        if steps == 1:
            dist, normals, ids = self.query(world, end + self.points @ q_matrix(q1).T, candidates)
            pen = self.radii - dist
            if pen.max() >= -SKIN:
                return end, q1, start, q0, pen, normals, ids
            return None
        rotation = q_matrix(q0)
        offsets = self.points @ rotation.T
        if angle > 1e-12:
            axis = omega / np.linalg.norm(omega)
            parallel = (self.points @ axis)[:, None] * (rotation @ axis)
            radial = offsets - parallel
            tangent = np.cross(axis, self.points) @ rotation.T
        for first in range(1, steps + 1, 32):
            fractions = np.arange(first, min(first + 32, steps + 1)) / steps
            positions = start + fractions[:, None] * delta
            if angle > 1e-12:
                theta = angle * fractions[:, None, None]
                offsets = parallel + np.cos(theta) * radial + np.sin(theta) * tangent
            points = positions[:, None] + offsets
            dist, normals, ids = self.query(world, points.reshape(-1, 3), candidates)
            shape = points.shape[:2]
            pen = self.radii - dist.reshape(shape)
            hit = np.flatnonzero(pen.max(axis=1) >= -SKIN)
            if len(hit):
                i = hit[0]
                prior = (first + i - 1) / steps
                q = q1 if first + i == steps else q_mul(q0, q_from_axis_angle(omega, angle * fractions[i]))
                prior_q = q_mul(q0, q_from_axis_angle(omega, angle * prior))
                return (positions[i], q, start + prior * delta, prior_q, pen[i],
                        normals.reshape(points.shape)[i], ids.reshape(shape)[i])
        return None

    @staticmethod
    def respond(vehicle, arm, normal, mat, depth, dt, entering):
        s = vehicle.s
        restitution, friction = MATERIALS[mat]
        point_v = s.vel + cross3(s.omega, arm)
        vn = float(point_v @ normal)
        lever = cross3(arm, normal)
        inv_mass = float((normal / vehicle.M) @ normal + (lever / vehicle.I) @ lever)
        if inv_mass < 1e-12:
            return 0., 0.
        speed = max(0., -vn)
        impulse = speed / inv_mass
        if entering and speed > .08:
            impulse *= 1. + restitution
        if mat == "net":
            # Implicit damped spring, with an inelastic stop at full extension.
            gain = NET_C + dt * NET_K
            spring = dt * (NET_K * max(0., depth) - gain * vn) / (1. + dt * gain * inv_mass)
            impulse = max(0., spring, impulse if depth >= NET_TRAVEL else 0.)
        s.vel += impulse * normal / vehicle.M
        s.omega += impulse * lever / vehicle.I
        point_v = s.vel + cross3(s.omega, arm)
        tangent = point_v - normal * (point_v @ normal)
        vt = float(np.linalg.norm(tangent))
        if vt > 1e-9:
            tangent /= vt
            lever = cross3(arm, tangent)
            inv_t = (tangent / vehicle.M) @ tangent + (lever / vehicle.I) @ lever
            drag = min(friction * impulse, vt / inv_t)
            s.vel -= drag * tangent / vehicle.M
            s.omega -= drag * lever / vehicle.I
        return impulse, speed
