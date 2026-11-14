// Block flight input while the frontend is open and until held controls return to neutral on exit.
import { CHANNELS, BUTTONS } from "../input/actions.js";
import { menuDevicesActive } from "./devices.js";
export const FRONTEND_OPEN_EVENT = "rov-frontend-open";
export const FRONTEND_PAUSE_EVENT = "rov-frontend-pause";
const STRINGS = { pause: "暫停選單" };
let waitingForRelease = false;
export function registerFrontendActions(input) {
  input.registerActions({
    frontendPause: {
      label: STRINGS.pause,
      binding: "b9",
      enabled(snapshot, value) {
        return (
          Boolean(snapshot && document.querySelector(".pause-menu")) &&
          !document.querySelector("dialog[open]") &&
          value > 0.5
        );
      },
      consume: [...CHANNELS, ...Object.keys(BUTTONS), "arm"],
      run() {
        dispatchEvent(new Event(FRONTEND_PAUSE_EVENT));
      },
    },
  });
  document.getElementById("inputSettings")?.addEventListener("close", finishFrontendInput);
}
export function finishFrontendInput() {
  waitingForRelease = true;
}
export function frontendInputBlocked() {
  if (document.querySelector(".pause-menu[open]")) return true;
  if (waitingForRelease) {
    waitingForRelease = menuDevicesActive();
  }
  return waitingForRelease;
}
