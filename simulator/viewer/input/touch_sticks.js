// Sole owner of whether the on-screen sticks are shown. They are a touch control: visible only while
// touch is the device in use and the pilot has not switched them off, hidden again on key or pad input.
// Markup starts hidden; style sheets only lay the sticks out and never decide their visibility.

// element: the sticks container. preference: the "on-screen sticks" checkbox. events: where
// `pointerdown` and `rov-input-device` are observed. coarse: whether touch is the primary pointer.
export function installTouchSticks({ element, preference, events = document, coarse = primaryTouch() }) {
  let touching = coarse;
  function render() {
    element.hidden = !(touching && preference.checked);
  }
  function setTouching(value) {
    if (touching === value) return;
    touching = value;
    render();
  }
  events.addEventListener("pointerdown", function pointerKind(event) {
    setTouching(event.pointerType === "touch");
  });
  // The input layer announces every keyboard, gamepad and stick interaction with this event.
  events.addEventListener("rov-input-device", function deviceKind(event) {
    setTouching(event.detail === "touch");
  });
  preference.addEventListener("change", render);
  render();
  return {
    get visible() {
      return !element.hidden;
    },
  };
}

function primaryTouch() {
  return typeof matchMedia === "function" && matchMedia("(pointer: coarse)").matches;
}
