// Hangar controls inspect shipped LODs, PBR channels and authoritative collision spheres.
import * as THREE from 'three';
import {vehicleAssets} from './asset_config.js';
const STRINGS = {
  wire:'Wireframe', proxy:'Collision proxy', camera:'Camera tilt', lamp:'Lamp tilt',
  channels:['PBR','Base color','Normal','Roughness','Metalness','AO'],
};
export function installInspector(select, getModel) {
  const panel = document.createElement('div');
  document.querySelector('aside').append(panel);
  for (const [key, index] of [['camera', 0], ['lamp', 1]]) {
    const label = document.createElement('label');
    label.textContent = STRINGS[key];
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.min = -60;
    slider.max = 60;
    slider.value = 0;
    slider.oninput = () => {
      const angles = [0, 0];
      angles[index] = +slider.value;
      getModel().updatePivots(...angles);
    };
    label.append(slider);
    panel.append(label);
  }
  const lod = document.createElement('select');
  for (let i = 0; i < 3; i++) lod.add(new Option(`LOD ${i}`, i));
  panel.append(lod);
  lod.onchange = () => select(getModel().definition.id, +lod.value);
  const wire = document.createElement('button');
  wire.textContent = STRINGS.wire;
  panel.append(wire);
  let wireframe = false;
  wire.onclick = () => {
    wireframe = !wireframe;
    getModel().model.traverse(o => {
      if (o.isMesh) o.material.wireframe = wireframe;
    });
  };
  const channel = document.createElement('select');
  STRINGS.channels.forEach((name, i) => channel.add(new Option(name, i)));
  panel.append(channel);
  channel.onchange = () => getModel().model.traverse(o => {
    if (!o.isMesh) return;
    o.userData.pbr ??= o.material;
    if (o.material !== o.userData.pbr) o.material.dispose();
    const pbr = o.userData.pbr;
    const maps = [null, pbr.map, pbr.normalMap, pbr.roughnessMap, pbr.metalnessMap, pbr.aoMap];
    o.material = +channel.value ? new THREE.MeshBasicMaterial({map:maps[+channel.value]}) : pbr;
    o.material.wireframe = wireframe;
  });
  const proxy = document.createElement('button');
  proxy.textContent = STRINGS.proxy;
  panel.append(proxy);
  proxy.onclick = async () => {
    const model = getModel();
    const existing = model.root.getObjectByName('collision');
    if (existing) {
      existing.visible = !existing.visible;
      return;
    }
    const asset = vehicleAssets[model.definition.id];
    if (!asset) return;
    const slug = asset.slug;
    const data = await (await fetch(`models/${slug}-collision.json`)).json();
    const group = new THREE.Group();
    group.name = 'collision';
    for (const [p, r] of data.spheres) {
      const mesh = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12),
        new THREE.MeshBasicMaterial({color:0x55ffaa, wireframe:true}));
      mesh.position.set(-p[1], -p[2], p[0]);
      group.add(mesh);
    }
    model.root.add(group);
  };
}
