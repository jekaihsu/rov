#!/usr/bin/env python3
"""ROV-01 mission safety: exhaustive BFS and four single-defect mutants."""
from dataclasses import dataclass, replace
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pstack_verify"))
from statechart_exhaustive import run


@dataclass(frozen=True)
class State:
    mode: str = "idle"
    hull: int = 100
    thrusters: int = 6
    allocation: int = 100
    tether: str = "clear"
    crush: bool = False
    coupled: bool = False
    dwell: int = 0
    sample: bool = False
    ut_done: bool = False
    certified: bool = False


class Model:
    invariant_names = [f"INV-ROV-{i:02}" for i in range(1, 5)]
    tla_invariants = [f"InvROV{i:02}" for i in range(1, 5)]
    mutants = [("cert_bypass", invariant_names[0], tla_invariants[0]),
               ("fault_full_thrust", invariant_names[1], tla_invariants[1]),
               ("ut_bypass", invariant_names[2], tla_invariants[2]),
               ("tether_bypass", invariant_names[3], tla_invariants[3])]
    events = tuple((a, 0) for a in ("launch", "hold", "manual", "couple", "uncouple", "tick", "sample",
                                   "fault", "tension", "entangle", "untangle", "crush", "surface", "dock",
                                   "impact", "certify", "reset"))
    required_actions = [e[0] for e in events]
    metadata = {"ticket": "#80", "UT_dwell_seconds": 3, "fault_allocation_percent": 75,
                "invariant_mapping": dict(zip(invariant_names, ["safe certification after dock, UT and hull >=80",
                    "5-thruster fault: degraded mode and allocation <=75%", "UT sample: stable hold, coupling and 3s dwell",
                    "zero hull abort; entangled ascent block; crush protection"]))}

    @staticmethod
    def init(): return State()

    @staticmethod
    def type_ok(s):
        return (s.mode in {"idle", "manual", "hold", "degraded", "return", "surface", "docked", "abort"}
                and s.hull in {0, 50, 80, 100} and s.thrusters in {5, 6}
                and s.allocation in {0, 75, 100} and s.tether in {"clear", "tension", "entangled"}
                and s.dwell in range(4) and all(type(x) is bool for x in
                (s.crush, s.coupled, s.sample, s.ut_done, s.certified)))

    @staticmethod
    def invariants(s):
        return {"INV-ROV-01": not s.certified or (s.mode == "docked" and s.ut_done and s.hull >= 80 and s.allocation == 0),
                "INV-ROV-02": s.thrusters != 5 or (s.allocation <= 75 and s.mode in {"degraded", "hold", "return", "docked", "abort"}),
                "INV-ROV-03": not s.sample or (s.mode == "hold" and s.coupled and s.dwell == 3 and s.tether == "clear" and not s.crush),
                "INV-ROV-04": (s.hull != 0 or (s.mode == "abort" and s.allocation == 0 and not s.certified))
                    and not (s.mode == "surface" and s.tether == "entangled")
                    and (not s.crush or s.mode in {"surface", "hold", "return", "abort"})}

    @staticmethod
    def step(s, event, mutant="none"):
        a, _ = event
        active = s.mode in {"manual", "hold", "degraded", "return", "surface"} and s.hull > 0
        if a == "reset" and s.mode in {"docked", "abort"}: return State()
        if a == "launch" and s.mode == "idle": return replace(s, mode="manual")
        if a == "hold" and active and not s.crush: return replace(s, mode="hold", sample=False)
        if a == "manual" and s.mode == "hold" and not s.crush and s.thrusters == 6:
            return replace(s, mode="manual", sample=False, dwell=0)
        if a in {"couple", "uncouple"} and s.mode == "hold" and not s.crush and s.tether == "clear":
            return replace(s, coupled=a == "couple", dwell=0, sample=False)
        if a == "tick" and s.mode == "hold" and s.coupled and s.tether == "clear" and not s.crush:
            return replace(s, dwell=min(3, s.dwell + 1))
        if a == "sample" and s.mode == "hold" and not s.crush and s.tether == "clear":
            if mutant == "ut_bypass" or (s.coupled and s.dwell == 3): return replace(s, sample=True, ut_done=True)
        if a == "fault" and active and s.thrusters == 6:
            return replace(s, thrusters=5, allocation=100 if mutant == "fault_full_thrust" else 75,
                           mode="hold" if s.tether == "entangled" else "return", sample=False, dwell=0)
        if a == "tension" and active and s.tether == "clear":
            return replace(s, tether="tension", sample=False, dwell=0)
        if a == "entangle" and active and s.tether == "tension":
            return replace(s, tether="entangled", mode="hold", sample=False, dwell=0)
        if a == "untangle" and active and s.tether == "entangled": return replace(s, tether="clear")
        if a == "crush" and active:
            return replace(s, crush=True, mode="hold" if s.tether == "entangled" else
                           ("return" if s.thrusters == 5 else "surface"), sample=False, dwell=0)
        if a == "surface" and active and s.thrusters == 6:
            if s.tether != "entangled" or mutant == "tether_bypass":
                return replace(s, mode="surface", sample=False, dwell=0)
        if a == "dock" and active and s.tether != "entangled":
            return replace(s, mode="docked", allocation=0, crush=False, sample=False, dwell=0)
        if a == "impact" and active:
            hull = {100: 80, 80: 50, 50: 0}[s.hull]
            return replace(s, hull=hull, sample=False, dwell=0, mode="abort" if hull == 0 else s.mode,
                           allocation=0 if hull == 0 else s.allocation, certified=False)
        if a == "certify" and s.mode == "docked":
            if mutant == "cert_bypass" or (s.ut_done and s.hull >= 80): return replace(s, certified=True)
        return s


if __name__ == "__main__":
    sys.exit(run(Model(), Path(__file__).with_name("RovMissionSafetyStatechart.tla")))
