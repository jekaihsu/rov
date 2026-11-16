// Refresh existing literal labels without rebuilding menus or losing keyboard/gamepad focus.
// Composed sentences retain their normal lifecycle; the change notice explains this limitation.
export function refreshLabels(before, after, root = document.body) {
  const replacements = new Map();
  for (const [key, value] of before) {
    if (value !== after.get(key)) replacements.set(value, after.get(key));
  }
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement?.closest('script, style, textarea')) continue;
    const text = node.textContent.trim();
    if (replacements.has(text)) node.textContent = node.textContent.replace(text, replacements.get(text));
  }
  for (const node of root.querySelectorAll('[title], [aria-label], [placeholder]')) {
    for (const attribute of ['title', 'aria-label', 'placeholder']) {
      const text = node.getAttribute(attribute);
      if (replacements.has(text)) node.setAttribute(attribute, replacements.get(text));
    }
  }
}
