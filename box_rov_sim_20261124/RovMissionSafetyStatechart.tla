---------------- MODULE RovMissionSafetyStatechart ----------------
EXTENDS Naturals, TLC
CONSTANT Mutant
VARIABLE s
vars == <<s>>
Initial == [mode |-> "idle", hull |-> 100, thrusters |-> 6,
  allocation |-> 100, tether |-> "clear", crush |-> FALSE,
  coupled |-> FALSE, dwell |-> 0, sample |-> FALSE,
  ut_done |-> FALSE, certified |-> FALSE]
Init == s = Initial
Events == {"launch", "hold", "manual", "couple", "uncouple", "tick", "sample",
 "fault", "tension", "entangle", "untangle", "crush", "surface", "dock",
 "impact", "certify", "reset"}
Active(x) == x.mode \in {"manual", "hold", "degraded", "return", "surface"} /\ x.hull > 0
Step(x, a) == CASE
 a = "reset" /\ x.mode \in {"docked", "abort"} -> Initial
 [] a = "launch" /\ x.mode = "idle" -> [x EXCEPT !.mode = "manual"]
 [] a = "hold" /\ Active(x) /\ ~x.crush -> [x EXCEPT !.mode = "hold", !.sample = FALSE]
 [] a = "manual" /\ x.mode = "hold" /\ ~x.crush /\ x.thrusters = 6 ->
    [x EXCEPT !.mode = "manual", !.sample = FALSE, !.dwell = 0]
 [] a \in {"couple", "uncouple"} /\ x.mode = "hold" /\ ~x.crush /\ x.tether = "clear" ->
    [x EXCEPT !.coupled = (a = "couple"), !.dwell = 0, !.sample = FALSE]
 [] a = "tick" /\ x.mode = "hold" /\ x.coupled /\ x.tether = "clear" /\ ~x.crush ->
    [x EXCEPT !.dwell = IF @ < 3 THEN @ + 1 ELSE 3]
 [] a = "sample" /\ x.mode = "hold" /\ ~x.crush /\ x.tether = "clear"
    /\ (Mutant = "ut_bypass" \/ (x.coupled /\ x.dwell = 3)) ->
    [x EXCEPT !.sample = TRUE, !.ut_done = TRUE]
 [] a = "fault" /\ Active(x) /\ x.thrusters = 6 ->
    [x EXCEPT !.thrusters = 5, !.allocation = IF Mutant = "fault_full_thrust" THEN 100 ELSE 75,
     !.mode = IF x.tether = "entangled" THEN "hold" ELSE "return", !.sample = FALSE, !.dwell = 0]
 [] a = "tension" /\ Active(x) /\ x.tether = "clear" ->
    [x EXCEPT !.tether = "tension", !.sample = FALSE, !.dwell = 0]
 [] a = "entangle" /\ Active(x) /\ x.tether = "tension" ->
    [x EXCEPT !.tether = "entangled", !.mode = "hold", !.sample = FALSE, !.dwell = 0]
 [] a = "untangle" /\ Active(x) /\ x.tether = "entangled" -> [x EXCEPT !.tether = "clear"]
 [] a = "crush" /\ Active(x) ->
    [x EXCEPT !.crush = TRUE, !.mode = IF x.tether = "entangled" THEN "hold"
      ELSE IF x.thrusters = 5 THEN "return" ELSE "surface", !.sample = FALSE, !.dwell = 0]
 [] a = "surface" /\ Active(x) /\ x.thrusters = 6
    /\ (x.tether # "entangled" \/ Mutant = "tether_bypass") ->
    [x EXCEPT !.mode = "surface", !.sample = FALSE, !.dwell = 0]
 [] a = "dock" /\ Active(x) /\ x.tether # "entangled" ->
    [x EXCEPT !.mode = "docked", !.allocation = 0, !.crush = FALSE, !.sample = FALSE, !.dwell = 0]
 [] a = "impact" /\ Active(x) -> LET h == CASE x.hull = 100 -> 80 [] x.hull = 80 -> 50 [] OTHER -> 0
    IN [x EXCEPT !.hull = h, !.sample = FALSE, !.dwell = 0,
      !.mode = IF h = 0 THEN "abort" ELSE x.mode,
      !.allocation = IF h = 0 THEN 0 ELSE x.allocation, !.certified = FALSE]
 [] a = "certify" /\ x.mode = "docked" /\ (Mutant = "cert_bypass" \/ (x.ut_done /\ x.hull >= 80)) ->
    [x EXCEPT !.certified = TRUE]
 [] OTHER -> x
Next == \E a \in Events: s' = Step(s, a)
Spec == Init /\ [][Next]_vars
TypeOK == s \in [mode : {"idle", "manual", "hold", "degraded", "return", "surface", "docked", "abort"},
 hull : {0, 50, 80, 100}, thrusters : {5, 6}, allocation : {0, 75, 100},
 tether : {"clear", "tension", "entangled"}, crush : BOOLEAN, coupled : BOOLEAN,
 dwell : 0..3, sample : BOOLEAN, ut_done : BOOLEAN, certified : BOOLEAN]
\* INV-ROV-01: certification requires completed recovery, UT and hull >=80.
InvROV01 == s.certified => (s.mode = "docked" /\ s.ut_done /\ s.hull >= 80 /\ s.allocation = 0)
\* INV-ROV-02: single-thruster failure caps output and forces safe modes.
InvROV02 == s.thrusters = 5 => (s.allocation <= 75 /\ s.mode \in {"degraded", "hold", "return", "docked", "abort"})
\* INV-ROV-03: coupling abstracts normal angle <3 deg; dwell is seconds.
InvROV03 == s.sample => (s.mode = "hold" /\ s.coupled /\ s.dwell = 3 /\ s.tether = "clear" /\ ~s.crush)
\* INV-ROV-04: immediate hull, tether and crush protection at control commit.
InvROV04 == /\ (s.hull = 0 => (s.mode = "abort" /\ s.allocation = 0 /\ ~s.certified))
 /\ ~(s.mode = "surface" /\ s.tether = "entangled")
 /\ (s.crush => s.mode \in {"surface", "hold", "return", "abort"})
====================================================================
