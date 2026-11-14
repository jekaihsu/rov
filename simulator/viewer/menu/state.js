// Block flight input while the frontend is open and until held controls return to neutral on exit.
import { pollMenuDevices } from "./devices.js";
export const FRONTEND_OPEN_EVENT = "rov-frontend-open";
let waitingForRelease = false;
export function finishFrontendInput() {
  waitingForRelease = true;
}
export function frontendInputBlocked() {
  if (document.querySelector(".pause-menu[open]")) return true;
  if (waitingForRelease) {
    const { snapshot } = pollMenuDevices();
    waitingForRelease = Boolean(snapshot && (
      snapshot.buttons.some(value => value > 0.5) ||
      snapshot.axes.slice(0, 4).some(value => Math.abs(value) > 0.2)
    ));
  }
  return waitingForRelease;
}
