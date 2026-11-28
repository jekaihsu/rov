// Pure enablement for deck-checklist pad/keyboard navigation and Esc → pause (intro_skip onMenuBack).

export function checklistNavigable({ hidden, phase, focusableCount }) {
  return !hidden && phase != null && phase !== 'diving' && focusableCount > 0;
}
