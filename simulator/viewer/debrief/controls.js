/* Gamepad / keyboard focus for the debrief panel via the menu rows in bindings.js. */
import {createMenuNavigator, loadControllerDatabase} from '../menu/navigator.js';
import {VIEW_GOD, VIEW_STUDENT} from './viewpoint.js';

export async function installDebriefControls({panel, viewpoint}) {
  if (!panel || !viewpoint) return null;
  const database = await loadControllerDatabase();
  const navigator = createMenuNavigator({
    database,
    root: panel,
    handlers: {
      scope() {
        return panel;
      },
      tab(delta) {
        const next = viewpoint.mode === VIEW_STUDENT ? VIEW_GOD : VIEW_STUDENT;
        if (delta) viewpoint.setMode(next);
      },
      back() {
        // Debrief stays open for the whole replay; back just returns focus to the play control.
        document.getElementById('rpPlay')?.focus({preventScroll: true});
      },
    },
  });
  navigator.setActive(true);
  navigator.start();
  navigator.focusFirst(panel);
  return navigator;
}
