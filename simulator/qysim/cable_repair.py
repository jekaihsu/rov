"""Fictional shore approach after a cable break. Geometry uses local NED metres."""
import math

import numpy as np

from .ecology import SeabedTerrain
from .site_dressing import ship_hull
from .world import Box, Cylinder, CurrentProfile, SnagFeature


class RepairBed(SeabedTerrain):
    """Use the same sampled bed for collision, sensor returns and seabed dressing."""
    def __init__(self):
        self.origin = np.array([-12., -12.])
        self.spacing = .6
        axis = self.origin[0] + self.spacing * np.arange(41)
        n, e = np.meshgrid(axis, axis, indexing="ij")
        offset = e - .38 * n
        groove = np.exp(-(offset / .48)**2)
        berm = np.exp(-((abs(offset) - .83) / .43)**2)
        extent = np.clip((10 - abs(n)) / 1.4, 0, 1)
        self.depths = 13 + .035 * n + .047 * np.cos(3.2 * n + .6 * np.sin(e))
        self.depths += extent * (.32 * groove - .17 * berm)
        self.relief = 1.4

    def point(self, n, e, clearance=0.):
        depth = self.sample_many([[n, e, 0]])[0][0]
        return (float(n), float(e), float(depth - clearance))


def repair_site():
    from .scenarios import Objective, Scenario
    bed = RepairBed()
    items = ship_hull("recovery hull", (7., 9.), 0, 52., 11., 3.6)
    # Sample the two surviving runs independently, so the photographed gap is also clear to sonar.
    for side in (-1, 1):
        end = bed.point(0, side * .72, .29)
        for index in range(1, 11):
            e = side * (.72 + index)
            n = .18 * math.sin(e * .6)
            buried = side < 0 and index >= 8
            p = bed.point(n, e, -.19 if buried else .046)
            if not (buried and index > 8):
                segment = Cylinder(f"armoured run {side} {index}", end, p, .05, "repair_cable")
                if index == 1:
                    segment.snag_hold = (150., 300.)
                items.append(segment)
            end = p
        tip = bed.point(0, side * .72, .29)
        core_end = (tip[0], tip[1] - side * .075, tip[2])
        items.append(Cylinder(f"exposed core {side}", tip, core_end, .018, "repair_core"))
        for wire in range(12):
            angle = math.tau * wire / 12
            a = (tip[0] + .039 * math.cos(angle), tip[1], tip[2] + .039 * math.sin(angle))
            b = (tip[0] + .11 * math.cos(angle + .6), tip[1] - side * (.14 + .05 * math.cos(3 * angle)),
                 tip[2] + .11 * math.sin(angle + .6))
            items.append(Cylinder(f"armour strand {side} {wire}", a, b, .003, "repair_wire"))
    items.extend([
        Cylinder("shore conduit", bed.point(0, -8.8, -.12), bed.point(0, -6.8, .08), .14, "cable_protection"),
        Cylinder("joint sleeve", bed.point(0, 6.4, .10), bed.point(0, 7.6, .10), .12, "shaft"),
        Cylinder("chain remnant", bed.point(-2, -1, .09), bed.point(-4, -2.1, .09), .09, "mooring_chain"),
        Box("unidentified housing", bed.point(1.3, 2.1, .14), (.32, .21, .14), 19, "housing"),
        Box("housing lid", bed.point(1.3, 2.1, .29), (.33, .22, .017), 19, "housing"),
        Cylinder("recovery pennant", (3, 3.3, .1), (2, 2.9, 11.7), .026, "hawser"),
    ])
    # Four captive lid fasteners on a sealed box. No manipulator attachment points.
    yaw = math.radians(19)
    for x in (-.27, .27):
        for y in (-.16, .16):
            n = 1.3 + x * math.cos(yaw) - y * math.sin(yaw)
            e = 2.1 + x * math.sin(yaw) + y * math.cos(yaw)
            z = bed.point(1.3, 2.1, .307)[2]
            items.append(Cylinder(f"lid fastener {x} {y}", (n, e, z), (n, e, z - .009), .018, "repair_wire"))
    items.append(SnagFeature("reference outcrop", bed.point(1.55, 2.75), .27, .42, item="rock"))
    for i in range(16):
        n = -7.4 + i * .84
        e = .38 * n + (-1)**i * .78
        items.append(SnagFeature(f"spoil {i}", bed.point(n, e), .09 + i % 3 * .04, .13, item="rock"))
    return Scenario("cable_repair", "海纜修復現場", "沿犁溝核對兩端位置，從外側觀察回收繩。",
                    seabed_depth=14, biome="cable_repair", seabed_type="sand", water_type="shelf",
                    visibility_m=6, bnl_height_m=1.6, bnl_mg_l=1.8, obstacles=items,
                    current=CurrentProfile(.34, 85, .52, 85, .58, 85, .08),
                    start_pos=bed.point(-3.4, -1.2, .75), start_heading_deg=18,
                    spool_pos=(-4, 2, 0), tether_length=28, objectives=[
                        Objective("survey_photo", "拍攝岸側斷面", bed.point(-1., -.72, .72), target="shore_end"),
                        Objective("survey_photo", "拍攝海側斷面", bed.point(-1., .72, .72), target="sea_end"),
                        Objective("checkpoint", "確認回收繩位置", (1, 2, 11.6), 1.)])


def perimeter_site():
    from .scenarios import Objective
    site = repair_site()
    bed = RepairBed()
    site.key = "cable_perimeter"
    site.name = "海纜外圍複查"
    site.brief = "以岩面為基準，從外側記錄灰殼的位置。"
    site.start_pos = bed.point(-.65, 2.55, .76)
    site.start_heading_deg = 0
    site.objectives = [Objective("survey_photo", "記錄地貌與灰殼", site.start_pos, target="housing")]
    return site


def record_survey_photo(sim, filename, photo_id=None):
    """Identify a visible subject nearest the optical axis. Positions are simulation-local NED."""
    from .physics import q_rot
    pos = sim.vehicle.s.pos
    forward = q_rot(sim.vehicle.s.q, np.array([1., 0., 0.]))
    candidates = []
    for ob in sim.scenario.obstacles:
        if ob.name == "housing lid" and sim.scenario.key == "cable_perimeter":
            point = np.array(ob.center) - [0, 0, ob.half[2]]
            subject = "housing"
        elif sim.scenario.key == "cable_repair" and ob.name in ("armoured run -1 1", "armoured run 1 1"):
            point = np.array(ob.p0)
            subject = "shore_end" if ob.name == "armoured run -1 1" else "sea_end"
        else:
            continue
        delta = point - pos
        distance = np.linalg.norm(delta)
        if not .35 < distance < min(3., sim.world.visibility_at(pos)):
            continue
        alignment = np.dot(forward, delta) / distance
        if alignment < .94:
            continue
        hit = sim.world.raycast(pos, delta, max_range=distance)
        if hit < distance - .10:
            hit_name = sim.world.sdf(pos + delta * (hit / distance))[2]
            if subject != "housing" or hit_name not in ("housing lid", "unidentified housing"):
                continue
        if subject == "shore_end":
            ridge = sim.world.terrain.point(-.3, -.19, .04)
            context = np.asarray(ridge) - pos
            span = np.linalg.norm(context)
            if span < .1 or np.dot(forward, context) / span < .75:
                continue
            if sim.world.raycast(pos, context, max_range=span) < span - .12:
                continue
        candidates.append((alignment, subject, point))
    if candidates:
        _, subject, point = max(candidates, key=lambda candidate: candidate[0])
        observation = dict(photo=filename, depth_m=round(sim.depth, 2), t=round(sim.t, 2))
        if subject == "housing":
            rock = next(ob for ob in sim.scenario.obstacles if ob.name == "reference outcrop")
            reference = np.array(rock.p1)
            offset = reference - pos
            distance = np.linalg.norm(offset)
            if (distance < .5 or distance > sim.world.visibility_at(pos) or
                    np.dot(forward, offset) / distance < .84 or
                    sim.world.raycast(pos, offset, max_range=distance) < distance - rock.radius - .10):
                return
            observation["from_rock_ned_m"] = (point - reference).round(2).tolist()
        else:
            observation["reference_od_m"] = .10
            observation["pos_ned_m"] = point.round(3).tolist()
        if photo_id:
            observation["collection_id"] = photo_id
        sim.repair_evidence[subject] = observation


def survey_report(sim):
    records = sim.repair_evidence
    report = {"observations": dict(records)}
    if sim.deck_fix_interval:
        report["deck_fix_interval_s"] = list(sim.deck_fix_interval)
    if sim.scenario.key == "cable_repair":
        report["recovery_seen"] = sim.scenario.objectives[-1].done
    if "shore_end" in records and "sea_end" in records:
        delta = np.array(records["shore_end"]["pos_ned_m"]) - records["sea_end"]["pos_ned_m"]
        report["end_separation_m"] = round(float(np.linalg.norm(delta)), 3)
    return report
