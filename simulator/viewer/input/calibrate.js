// Pure calibration steps for non-standard pads. The settings dialog drives this; tests inject axes/buttons.
const STRINGS = {
  axes: ['leftx', 'lefty', 'rightx', 'righty']
};

export const AXIS_STEPS = [...STRINGS.axes];
export const BUTTON_COUNT = 17;
export const CALIBRATION_STEPS = [
  ...AXIS_STEPS,
  ...Array.from({length: BUTTON_COUNT}, function buttonStep(_, index) {
    return `b${index}`;
  })
];

// Returns the binding string for the current step, or null while waiting for a clear deflection / press.
export function captureCalibrationStep(stepIndex, axesDelta, pressedButton, {axisThreshold = 0.65} = {}) {
  if (stepIndex < 0 || stepIndex >= CALIBRATION_STEPS.length) return null;
  if (stepIndex < AXIS_STEPS.length) {
    const index = axesDelta.findIndex(function deflected(value) {
      return Math.abs(value) > axisThreshold;
    });
    if (index < 0) return null;
    return `${axesDelta[index] < 0 ? '-' : ''}a${index}`;
  }
  if (pressedButton >= 0) return `b${pressedButton}`;
  const axisIndex = axesDelta.findIndex(function deflected(value) {
    return Math.abs(value) > axisThreshold;
  });
  if (axisIndex < 0) return null;
  return `${axesDelta[axisIndex] < 0 ? '-' : ''}a${axisIndex}`;
}

export function buildCustomMapping(values) {
  return {
    axes: values.slice(0, AXIS_STEPS.length),
    buttons: values.slice(AXIS_STEPS.length, AXIS_STEPS.length + BUTTON_COUNT)
  };
}

export function isNeutral(axesDelta, pressedButton, {axisThreshold = 0.65} = {}) {
  return pressedButton < 0 && axesDelta.every(function quiet(value) {
    return Math.abs(value) <= axisThreshold;
  });
}
