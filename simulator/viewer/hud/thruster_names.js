// Player-facing thruster names for the systems card and the engineering drawer. The simulator names each thruster
// "T<n> <POSITION>" (qysim/vehicles.py); the number stays, the internal position key becomes the player's word.
const STRINGS = {
  positions: {
    PORT_FRONT: '左前',
    STBD_FRONT: '右前',
    PORT_AFT: '左後',
    STBD_AFT: '右後',
    PORT_LONG: '左縱',
    STBD_LONG: '右縱',
    HORIZONTAL: '水平',
    VERTICAL: '垂直',
  },
  thruster: '推進器',
};

export function thrusterLabel(name) {
  const [number, position] = String(name).split(' ');
  if (!position) return `${STRINGS.thruster} ${number}`;
  return `${number} ${STRINGS.positions[position] || STRINGS.thruster}`;
}
