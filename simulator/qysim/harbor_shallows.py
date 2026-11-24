"""Harbour shallows: a calm in-port training site for the directed prologue.

Real ROV teams often run first watches inside a sheltered harbour rather than in a pool. This site is ordinary
scenario data for the existing physics (AGENTS.md): piles, quay fittings and debris reuse the same builders as
``harbor_inspection``; currents, visibility and holding forces are provisional presentation choices, not surveys.

Layout (NED metres, origin at the launch lane):

* seabed 6 m (within the 4–8 m training band), clear morning, slack tide, visibility 8 m;
* three concrete piles on a short jetty face, pile 2 dead ahead and inside the start visibility cone;
* a floating pontoon with buoy, anchor chain and a mid-depth shackle (the last photo station);
* a crab pot, a tyre, cut cable and rubble on the bed; mussel/barnacle fouling comes from the pile materials;
* fish schools parked between the piles (a jetty is an artificial reef);
* the spool sits south of the start so the tether rises aft of the camera when the pilot faces the piles —
  the photo stations do not put the umbilical across the lens;
* a light northward current (0.25 kn) drifts an unlocked vehicle toward pile 2 when the sticks are released, so
  the coast / hold beats teach depth hold and trim against a real force without changing the vehicle model.
"""
from __future__ import annotations

from . import site_dressing as dressing
from .scenarios import TI_SHELTERED, Objective, Scenario
from .world import Box, CurrentProfile, Cylinder, SnagFeature, Wall

STRINGS = {
    "name": "港內避風淺水區",
    "brief": "晴天上午、平潮的港內淺水訓練：先認樁、蟹籠與浮碼頭錨鏈，不出港。",
    "pile_2": "2 號樁編號牌",
    "crab_pot": "海底蟹籠",
    "shackle": "浮碼頭錨鏈卸扣",
    "surface": "回投放點",
}

SEABED = 6.0
VISIBILITY_M = 8.0
START = (0.0, 0.0, 1.8)
START_HEADING = 0.0
# Spool aft of the vehicle (south when the bow faces the piles) so the umbilical rises behind the camera.
SPOOL = (-5.0, 0.0, 0.0)
TETHER_LENGTH = 22.0
# Slack-water northward set: enough to drift toward pile 2 in a few seconds with sticks released.
CURRENT_KN = 0.25
CURRENT_DIR = 0.0
# Photo / look-at stations (origin-radial, so BeatRun.photo_matches stand-off stays valid).
# Pile 2 sits ~5.5 m ahead so it is readable inside the 8 m visibility from the start pose.
PILE_2 = (5.5, 0.0, 2.8)
CRAB_POT = (4.5, 2.8, 5.2)
SHACKLE = (7.0, -2.8, 2.8)
FISH = (
    {"home": (4.0, -1.8, 2.8), "count": 48},
    {"home": (5.5, 1.6, 2.6), "count": 56},
    {"home": (3.2, 0.4, 3.4), "count": 40},
)


def _piles(sea: float) -> list:
    """Three short jetty piles; pile 2 sits on the approach centreline inside the start visibility cone."""
    specs = (
        ("Harbor pile 1", 5.0, -3.2, 0.55),
        ("Harbor pile 2", 6.0, 0.0, 0.65),
        ("Harbor pile 3", 5.0, 3.2, 0.55),
    )
    obs = []
    for name, north, east, radius in specs:
        obs.append(Cylinder(name, (north, east, -1.2), (north, east, sea), radius, "pile"))
    obs.append(Box("Jetty deck", (5.5, 0.0, -1.5), (2.8, 5.0, 0.35), 0, "deck"))
    return obs


def _pontoon_and_chain(sea: float) -> list:
    """Floating pontoon, surface buoy, anchor chain and a mid-depth shackle (photo station C)."""
    obs = [
        Box("Pontoon float", (7.8, -2.8, -0.35), (2.2, 1.3, 0.45), 15, "deck"),
        Cylinder("Pontoon buoy", (7.8, -2.8, -0.9), (7.8, -2.8, 0.35), 0.28, "bollard"),
        Cylinder("Pontoon chain upper", (7.0, -2.8, 0.2), (7.0, -2.8, 2.6), 0.045, "debris_pipe"),
        Cylinder("Pontoon chain lower", (7.0, -2.8, 3.0), (7.0, -2.8, sea - 0.15), 0.045, "debris_pipe"),
        Box("Pontoon shackle", SHACKLE, (0.28, 0.2, 0.22), 35, "debris_block"),
        Box("Pontoon anchor block", (7.0, -2.8, sea - 0.25), (0.55, 0.45, 0.25), 10, "debris_block"),
    ]
    dressing.snaggable(obs[-2:], dressing.SNAG_HOLD_DEBRIS)
    return obs


def _bed_props(sea: float) -> list:
    """Crab pot, tyre, cut cable and rubble — visual waypoints and light snags, no new physics."""
    crab = Box("Harbor crab pot", (4.5, 2.8, sea - 0.28), (0.75, 0.6, 0.38), -20, "debris_block")
    tyre = Box("Harbor tyre", (3.5, -2.2, sea - 0.13), (0.45, 0.45, 0.13), 40, "tyre")
    cable = Cylinder("Harbor cut cable", (3.0, 1.2, sea - 0.08), (5.2, 0.3, sea - 0.08), 0.06, "debris_pipe")
    rubble = SnagFeature("Harbor rubble", (8.5, 1.2, sea), 0.35, 0.4, item="rock")
    rope = SnagFeature("Harbor rope tangle", (5.5, -1.6, sea), 0.22, 0.28, item="rope")
    return dressing.snaggable([crab, tyre, cable], dressing.SNAG_HOLD_DEBRIS) + [rubble, rope]


def harbor_obstacles_shallows(sea: float) -> list:
    """Compact sheltered quay: three piles, pontoon gear, bed props and the usual quay fittings."""
    quay = Wall("Quay", (12.0, 0.0, 0.0), 180, 28, -1.2, "quay")
    obs = [quay] + _piles(sea)
    obs += dressing.dress_quay(quay, sea, keep_clear=(0.0,))
    obs += dressing.quay_debris(quay, sea)
    obs += _pontoon_and_chain(sea)
    obs += _bed_props(sea)
    return obs


def harbor_shallows() -> Scenario:
    sea = SEABED
    return Scenario(
        "harbor_shallows", STRINGS["name"], STRINGS["brief"],
        seabed_depth=sea, biome="harbor", visibility_m=VISIBILITY_M, seabed_type="mud",
        water_type="harbour",
        bnl_height_m=1.0, bnl_mg_l=1.2,
        obstacles=harbor_obstacles_shallows(sea),
        current=CurrentProfile(
            CURRENT_KN, CURRENT_DIR,
            CURRENT_KN * 0.7, CURRENT_DIR,
            CURRENT_KN * 0.4, CURRENT_DIR,
            TI_SHELTERED,
        ),
        start_pos=START, start_heading_deg=START_HEADING, spool_pos=SPOOL,
        tether_length=TETHER_LENGTH,
        objectives=[
            Objective("inspect", STRINGS["pile_2"], PILE_2, 1.2, hold_s=3, face_point=(6.0, 0.0, 2.8)),
            Objective("inspect", STRINGS["crab_pot"], CRAB_POT, 1.2, hold_s=3, face_point=(4.5, 2.8, 5.5)),
            Objective("inspect", STRINGS["shackle"], SHACKLE, 1.2, hold_s=3, face_point=(7.0, -2.8, 2.8)),
            Objective("surface", STRINGS["surface"], (SPOOL[0] + 2.0, 0.0, 0.5), 3),
        ],
        fish_schools=[dict(spec) for spec in FISH],
        time_limit_s=1200,
    )
