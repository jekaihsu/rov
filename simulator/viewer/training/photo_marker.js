// A painted inspection sphere at the active photo station, lit and obscured by the scene like other props.
export function createPhotoMarker(THREE, scene) {
  let marker = null;

  function dispose() {
    if (!marker) return;
    marker.removeFromParent();
    marker.geometry.dispose();
    marker.material.dispose();
    marker = null;
  }

  function update(target) {
    if (!scene || target?.kind !== 'photo') {
      dispose();
      return;
    }
    if (!marker) {
      marker = new THREE.Mesh(
        new THREE.SphereGeometry(0.18, 16, 12),
        new THREE.MeshStandardMaterial({color:0xeac361, roughness:0.8})
      );
      scene.add(marker);
    }
    const [north, east, down] = target.point;
    marker.position.set(-east, -down, north);
  }

  return {update, dispose};
}
