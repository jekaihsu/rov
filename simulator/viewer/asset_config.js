// Visual distribution selection leaves physics IDs and SDK semantics intact.
const query = new URLSearchParams(location.search);
export const trainingAssets = query.get('assets') !== 'generic';
export const vehicleAssets = {
  x1: { slug: 'observation', name: 'Observation ROV' },
};
export function vehicleAsset(id, lod = 0) {
  return `models/${vehicleAssets[id].slug}-lod${Math.max(0, Math.min(2, lod))}.glb`;
}
