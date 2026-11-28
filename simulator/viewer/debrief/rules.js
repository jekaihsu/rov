// Instructor calibration table. Research basis: docs/reference/real-rov-research.md,
// structure inspection and tether management. Numeric approach limits are provisional.
export const approach = {kind: 'pile', clearanceM: 2, targetMps: 0.3};
export const rules = [
  {metric: 'collisions', above: 0, message: 'impact'},
  {metric: 'collisions', atMost: 0, message: 'clear'},
  {metric: 'approach', above: approach.targetMps, message: 'slow'},
  {metric: 'approach', atMost: approach.targetMps, message: 'steady'},
  {metric: 'loaded', above: 0, message: 'ease'},
  {metric: 'recoveries', above: 0, message: 'recovered'},
];
