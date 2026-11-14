// Scenario rules for the acoustic search exercise: its target must be found by sonar, so neither the 3D objective
// marker nor the HUD map may reveal where it is.
const ACOUSTIC_SEARCH = 'sonar_search';

export function hidesTargets(world) {
  return world?.scenario?.key === ACOUSTIC_SEARCH;
}
