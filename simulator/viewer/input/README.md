# Input layer

Open controller settings with F8, the sidebar button, or controller Back + Start.
D-pad up/down moves focus; left/right adjusts sliders and selects options; primary
button activates, secondary returns. Focus a binding field and move an axis or
press a button to capture a binding, or enter `a0`, `-a1`, `b7`, `b7~` (digital
threshold), or `b7,b6` (positive minus negative). Reset restores defaults.

F cycles assist 0/1/2; G cycles cine/normal/sport. Default assist is 2 and profile
normal; both fields are omitted until telemetry advertises an assist object. Selecting the drone preset also selects
UAV_USA channel interpretation; current selects ROV_USA. No PWM meaning changes.

Unknown controllers are neutral until calibrated. In the wizard move the first
four requested controls in the positive directions (right/down/right/down), then
press each requested standard button. Release between steps. Extra axes and
buttons may be assigned to any requested control; optional buttons may be skipped.
The profile is saved by device ID. Calibrate again when changing driver/browser:
SDL indices vary across platforms, especially hat switches. The compact database
contains Linux axis records; unsupported SDL hat descriptors produce no action,
so calibrate a custom profile when the live display differs from the device.

Browser preferences use `rov.input.v1`; desktop mirrors them in the existing
userData/preferences.json mechanism and restores them across dynamic server ports.
No settings are sent to the physics engine except optional assist/profile fields.

Run `node --test simulator/tests/*.mjs` and `python simulator/tools/browser_input_smoke.py`
from the repository root. The latter expects the implementation on :8080 and writes
1600×900 evidence under simulator/output/t02. Pass `--before-url URL` only when a
comparison server is available; it is not required for input regression checks. Hardware feel and vibration require physical testing.
