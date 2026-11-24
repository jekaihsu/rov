#!/usr/bin/env node
/**
 * Re-runnable Formal Verification & Mutation Harness for ROV 3D Simulator (#80)
 * Verifies:
 *   Wave 1 (M_06_rov_fault_and_sop_eval):
 *     1. 06_rov_fault_and_sop_eval.mmd parallel-region syntax & %% never rules
 *     2. M_06_rov_fault_and_sop_eval.tla via TLC + statechart.mjs (55 states, 83 transitions, 0 violations)
 *     3. M_06_rov_broken.tla via TLC + statechart.mjs (--expect-broken proves all 3 invariants fail on broken transitions)
 *     4. Renders /workspace/rov_sim/rov_fault_sop_statechart.png
 *   Wave 3 Autopilot & UT Sampling (M_07_rov_autopilot_and_ut_sampling):
 *     5. 07_rov_autopilot_and_ut_sampling.mmd parallel-region syntax & %% never rules
 *     6. M_07_rov_autopilot_and_ut_sampling.tla via TLC + statechart.mjs (27 states, 81 transitions, 0 violations)
 *     7. M_07_rov_autopilot_broken.tla via TLC + statechart.mjs (--expect-broken proves all 3 invariants fail with minimal counterexamples)
 *     8. Renders /workspace/rov_sim/rov_autopilot_ut_statechart.png
 *   Wave 3 Pipeline & Tether Physics (M_08_rov_pipeline_and_tether_physics):
 *     9. 08_rov_pipeline_and_tether_physics.mmd parallel-region syntax & %% never rules
 *    10. M_08_rov_pipeline_and_tether_physics.tla via TLC + statechart.mjs (32 states, 71 transitions, 0 violations)
 *    11. M_08_rov_pipeline_broken.tla via TLC + statechart.mjs (--expect-broken proves all 3 invariants fail with minimal counterexamples)
 *    12. Renders /workspace/rov_sim/rov_pipeline_physics_statechart.png
 */
import fs from "node:fs";
import { spawnSync } from "node:child_process";

const STATECHART_CLI = "/home/box/agent-data/plugins/pstack/pstack/skills/statechart/scripts/statechart.mjs";
const ENV = {
  ...process.env,
  TLA2TOOLS: "/home/box/.local/share/tla2tools.jar",
  JAVA: "/usr/bin/java",
};

function run(args) {
  const res = spawnSync(process.execPath, [STATECHART_CLI, ...args], {
    env: ENV,
    encoding: "utf8",
  });
  if (res.status !== 0) {
    throw new Error(`Command failed (${res.status}): node statechart.mjs ${args.join(" ")}\n${res.stderr}\n${res.stdout}`);
  }
  return res.stdout;
}

// Wave 1: M_06_rov_fault_and_sop_eval
run(["from-spec", "/workspace/pstack_verify/M_06_rov_fault_and_sop_eval.tla", "--png"]);
run([
  "from-spec",
  "/workspace/pstack_verify/M_06_rov_broken.tla",
  "--expect-broken",
  "Inv_NoCertWithThrusterFaultUnlessReturned,Inv_ThrusterFaultCapsAllocation,Inv_ZeroHullForcesAbort",
  "--png",
]);
run([
  "render",
  "/workspace/pstack_verify/06_rov_fault_and_sop_eval.mmd",
  "--out",
  "/workspace/rov_sim/rov_fault_sop_statechart.png",
]);

// Wave 3 (Model #2): M_07_rov_autopilot_and_ut_sampling
run(["from-spec", "/workspace/pstack_verify/M_07_rov_autopilot_and_ut_sampling.tla", "--png"]);
run([
  "from-spec",
  "/workspace/pstack_verify/M_07_rov_autopilot_broken.tla",
  "--expect-broken",
  "Inv_UtSampleRequiresCoupledAndStable,Inv_NoEmergencySurfaceWhenEntangled,Inv_CrushHazardForcesEmergencyOrHold",
  "--png",
]);
run([
  "render",
  "/workspace/pstack_verify/07_rov_autopilot_and_ut_sampling.mmd",
  "--out",
  "/workspace/rov_sim/rov_autopilot_ut_statechart.png",
]);

// Wave 3 (Model #3): M_08_rov_pipeline_and_tether_physics
run(["from-spec", "/workspace/pstack_verify/M_08_rov_pipeline_and_tether_physics.tla", "--png"]);
run([
  "from-spec",
  "/workspace/pstack_verify/M_08_rov_pipeline_broken.tla",
  "--expect-broken",
  "Inv_SequentialGateOrderForGold,Inv_StormCurrentRequiresDerateGuard,Inv_OverheatOrSnagForcesDisqualifyOrRecover",
  "--png",
]);
run([
  "render",
  "/workspace/pstack_verify/08_rov_pipeline_and_tether_physics.mmd",
  "--out",
  "/workspace/rov_sim/rov_pipeline_physics_statechart.png",
]);

const prod06Summary = JSON.parse(
  fs.readFileSync("/workspace/pstack_verify/M_06_rov_fault_and_sop_eval-statechart/summary.json", "utf8"),
);
const broken06Summary = JSON.parse(
  fs.readFileSync("/workspace/pstack_verify/M_06_rov_broken-statechart/summary.json", "utf8"),
);
const prod07Summary = JSON.parse(
  fs.readFileSync("/workspace/pstack_verify/M_07_rov_autopilot_and_ut_sampling-statechart/summary.json", "utf8"),
);
const broken07Summary = JSON.parse(
  fs.readFileSync("/workspace/pstack_verify/M_07_rov_autopilot_broken-statechart/summary.json", "utf8"),
);
const prod08Summary = JSON.parse(
  fs.readFileSync("/workspace/pstack_verify/M_08_rov_pipeline_and_tether_physics-statechart/summary.json", "utf8"),
);
const broken08Summary = JSON.parse(
  fs.readFileSync("/workspace/pstack_verify/M_08_rov_pipeline_broken-statechart/summary.json", "utf8"),
);

const totalProductionStates =
  prod06Summary.modelStates + prod07Summary.modelStates + prod08Summary.modelStates;
const totalProductionTransitions =
  prod06Summary.modelTransitions + prod07Summary.modelTransitions + prod08Summary.modelTransitions;
const totalProductionViolations =
  prod06Summary.chartStatus.wrong + prod07Summary.chartStatus.wrong + prod08Summary.chartStatus.wrong;
const totalNegativeStates =
  broken06Summary.modelStates + broken07Summary.modelStates + broken08Summary.modelStates;
const totalNegativeTransitions =
  broken06Summary.modelTransitions + broken07Summary.modelTransitions + broken08Summary.modelTransitions;
const totalCaughtBugClasses =
  broken06Summary.classes.length + broken07Summary.classes.length + broken08Summary.classes.length;

const report = {
  ticket: "#80",
  suiteTotals: {
    modelsVerified: [
      "M_06_rov_fault_and_sop_eval",
      "M_07_rov_autopilot_and_ut_sampling",
      "M_08_rov_pipeline_and_tether_physics",
    ],
    negativeModelsVerified: [
      "M_06_rov_broken",
      "M_07_rov_autopilot_broken",
      "M_08_rov_pipeline_broken",
    ],
    totalProductionStates,
    totalProductionTransitions,
    totalProductionViolations,
    totalNegativeStates,
    totalNegativeTransitions,
    totalCaughtBugClasses,
    allInvariantsVerifiedCount: 12,
  },
  model: "M_06_rov_fault_and_sop_eval",
  production: {
    distinctStates: prod06Summary.modelStates,
    transitions: prod06Summary.modelTransitions,
    works: prod06Summary.chartStatus.works,
    wrong: prod06Summary.chartStatus.wrong,
    codeLikeCount: prod06Summary.codeLike.length,
    invariantsVerified: [
      "TypeOK",
      "Inv_NoCertWithThrusterFaultUnlessReturned",
      "Inv_ThrusterFaultCapsAllocation",
      "Inv_ZeroHullForcesAbort",
    ],
  },
  negativeBrokenTest: {
    model: "M_06_rov_broken",
    distinctStates: broken06Summary.modelStates,
    transitions: broken06Summary.modelTransitions,
    works: broken06Summary.chartStatus.works,
    wrong: broken06Summary.chartStatus.wrong,
    caughtClasses: broken06Summary.classes.map((c) => ({
      n: c.n,
      invariant: c.invariant,
      readerSteps: c.readerSteps,
      endState: c.end,
      lastSteps: c.lastSteps,
    })),
  },
  wave3AutopilotAndUtSampling: {
    model: "M_07_rov_autopilot_and_ut_sampling",
    production: {
      distinctStates: prod07Summary.modelStates,
      transitions: prod07Summary.modelTransitions,
      works: prod07Summary.chartStatus.works,
      wrong: prod07Summary.chartStatus.wrong,
      codeLikeCount: prod07Summary.codeLike.length,
      invariantsVerified: [
        "TypeOK",
        "Inv_UtSampleRequiresCoupledAndStable",
        "Inv_NoEmergencySurfaceWhenEntangled",
        "Inv_CrushHazardForcesEmergencyOrHold",
      ],
    },
    negativeBrokenTest: {
      model: "M_07_rov_autopilot_broken",
      distinctStates: broken07Summary.modelStates,
      transitions: broken07Summary.modelTransitions,
      works: broken07Summary.chartStatus.works,
      wrong: broken07Summary.chartStatus.wrong,
      codeLikeCount: broken07Summary.codeLike.length,
      caughtClasses: broken07Summary.classes.map((c) => ({
        n: c.n,
        invariant: c.invariant,
        readerSteps: c.readerSteps,
        endState: c.end,
        lastSteps: c.lastSteps,
      })),
    },
    artifacts: {
      mmd: "/workspace/pstack_verify/07_rov_autopilot_and_ut_sampling.mmd",
      tla: "/workspace/pstack_verify/M_07_rov_autopilot_and_ut_sampling.tla",
      cfg: "/workspace/pstack_verify/M_07_rov_autopilot_and_ut_sampling.cfg",
      map: "/workspace/pstack_verify/M_07_rov_autopilot_and_ut_sampling.map.mjs",
      brokenTla: "/workspace/pstack_verify/M_07_rov_autopilot_broken.tla",
      brokenCfg: "/workspace/pstack_verify/M_07_rov_autopilot_broken.cfg",
      brokenMap: "/workspace/pstack_verify/M_07_rov_autopilot_broken.map.mjs",
      statechartPng: "/workspace/rov_sim/rov_autopilot_ut_statechart.png",
      tlcGraphPng: "/workspace/pstack_verify/M_07_rov_autopilot_and_ut_sampling-statechart/chart.png",
      brokenTlcGraphPng: "/workspace/pstack_verify/M_07_rov_autopilot_broken-statechart/chart.png",
    },
  },
  wave3PipelineAndTetherPhysics: {
    model: "M_08_rov_pipeline_and_tether_physics",
    production: {
      distinctStates: prod08Summary.modelStates,
      transitions: prod08Summary.modelTransitions,
      works: prod08Summary.chartStatus.works,
      wrong: prod08Summary.chartStatus.wrong,
      codeLikeCount: prod08Summary.codeLike.length,
      invariantsVerified: [
        "TypeOK",
        "Inv_SequentialGateOrderForGold",
        "Inv_StormCurrentRequiresDerateGuard",
        "Inv_OverheatOrSnagForcesDisqualifyOrRecover",
      ],
    },
    negativeBrokenTest: {
      model: "M_08_rov_pipeline_broken",
      distinctStates: broken08Summary.modelStates,
      transitions: broken08Summary.modelTransitions,
      works: broken08Summary.chartStatus.works,
      wrong: broken08Summary.chartStatus.wrong,
      codeLikeCount: broken08Summary.codeLike.length,
      caughtClasses: broken08Summary.classes.map((c) => ({
        n: c.n,
        invariant: c.invariant,
        readerSteps: c.readerSteps,
        endState: c.end,
        lastSteps: c.lastSteps,
      })),
    },
    artifacts: {
      mmd: "/workspace/pstack_verify/08_rov_pipeline_and_tether_physics.mmd",
      tla: "/workspace/pstack_verify/M_08_rov_pipeline_and_tether_physics.tla",
      cfg: "/workspace/pstack_verify/M_08_rov_pipeline_and_tether_physics.cfg",
      map: "/workspace/pstack_verify/M_08_rov_pipeline_and_tether_physics.map.mjs",
      brokenTla: "/workspace/pstack_verify/M_08_rov_pipeline_broken.tla",
      brokenCfg: "/workspace/pstack_verify/M_08_rov_pipeline_broken.cfg",
      brokenMap: "/workspace/pstack_verify/M_08_rov_pipeline_broken.map.mjs",
      statechartPng: "/workspace/rov_sim/rov_pipeline_physics_statechart.png",
      tlcGraphPng: "/workspace/pstack_verify/M_08_rov_pipeline_and_tether_physics-statechart/chart.png",
      brokenTlcGraphPng: "/workspace/pstack_verify/M_08_rov_pipeline_broken-statechart/chart.png",
    },
  },
  artifacts: {
    mmd: "/workspace/pstack_verify/06_rov_fault_and_sop_eval.mmd",
    tla: "/workspace/pstack_verify/M_06_rov_fault_and_sop_eval.tla",
    cfg: "/workspace/pstack_verify/M_06_rov_fault_and_sop_eval.cfg",
    map: "/workspace/pstack_verify/M_06_rov_fault_and_sop_eval.map.mjs",
    brokenTla: "/workspace/pstack_verify/M_06_rov_broken.tla",
    brokenCfg: "/workspace/pstack_verify/M_06_rov_broken.cfg",
    brokenMap: "/workspace/pstack_verify/M_06_rov_broken.map.mjs",
    statechartPng: "/workspace/rov_sim/rov_fault_sop_statechart.png",
    tlcGraphPng: "/workspace/pstack_verify/M_06_rov_fault_and_sop_eval-statechart/chart.png",
  },
};

fs.writeFileSync("/workspace/rov_sim/verification_summary.json", JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 2));
