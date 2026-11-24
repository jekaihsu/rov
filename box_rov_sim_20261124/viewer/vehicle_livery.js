export const LIVERIES = {
  cyber_cyan: '#06B6D4',
  arctic_white: '#F8FAFC',
  stealth_titanium: '#1E293B',
  original: '#06B6D4',
  arctic: '#F8FAFC',
  teal: '#22D3EE',
};

export function applyVehicleLivery(vehicle, preset = 'cyber_cyan') {
  if (!vehicle || vehicle.liveryPreset === preset) return;
  const resolved = Object.hasOwn(LIVERIES, preset) ? preset : 'cyber_cyan';
  vehicle.liveryPreset = resolved;
  if (typeof vehicle.setLivery === 'function') {
    vehicle.setLivery(resolved === 'original' || resolved === 'teal' ? 'cyber_cyan' : resolved === 'arctic' ? 'arctic_white' : resolved);
  }
  vehicle.model.traverse(object => {
    if (!object.isMesh) return;
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      if (!material?.color) continue;
      if (!material.userData.rovOriginalColor) {
        const c = material.color;
        const shell = /buoyancy|buoy|shell/i.test(material.name) || ((c.b > c.r * 1.4 && c.g > c.r * 1.2) && material.metalness < 0.4);
        if (!shell || /label|cable|propeller|sticker/i.test(material.name)) continue;
        material.userData.rovOriginalColor = c.clone();
      }
      if (resolved === 'original' || resolved === 'cyber_cyan') {
        material.color.set('#06B6D4');
      } else {
        material.color.set(LIVERIES[resolved]);
      }
    }
  });
}
