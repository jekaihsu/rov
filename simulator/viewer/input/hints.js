// Render on-screen key hints from the binding table so displayed keys cannot drift from the real ones.
import { hintItems } from "./bindings.js";

const STRINGS = { separator: " · ", pad: "手把 " };

// Fill an element with <kbd> captions for every key and pad source of the listed contexts.
export function renderKeyHints(element, options = {}) {
  if (!element) return;
  element.replaceChildren();
  const items = hintItems({ axes: true, ...options });
  items.forEach(function appendItem(item, index) {
    if (index) element.append(STRINGS.separator);
    for (const key of item.keys) {
      const cap = document.createElement("kbd");
      cap.textContent = key;
      element.append(cap);
    }
    const pad = item.pad ? `${item.keys.length ? " / " : ""}${STRINGS.pad}${item.pad}` : "";
    const note = item.note ? `（${item.note}）` : "";
    element.append(`${pad} ${item.label}${note}`);
  });
}
