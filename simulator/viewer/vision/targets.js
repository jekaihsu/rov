// Register rendered engineering objects and the cable without changing photo evidence targets.
export function visionTargets(state, fleet, cable) {
  const targets = (state?.operations?.objects || []).map(object => ({
    entity_id: object.id,
    category: 'engineering',
    mesh: fleet.objects.get(object.id),
  })).filter(target => target.mesh);
  if (cable?.mesh) {
    cable.mesh.geometry.computeBoundingBox();
    targets.push({entity_id: 'tether', category: 'cable', mesh: cable.mesh});
  }
  return targets;
}
