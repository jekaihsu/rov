// Replaceable, language-neutral screen art and the project's own rendered site postcards.
// No photographic sources: previews are simulator renders already shipped with the menu.
import * as THREE from 'three';

export async function dressBoatSurfaces(boat) {
  const textures = [];
  function mount(name, texture, luminous = false) {
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.flipY = false;
    textures.push(texture);
    const node = boat.getObjectByName(name);
    node.material = new THREE.MeshStandardMaterial({
      map: texture, roughness: .68, side: THREE.DoubleSide,
      emissive: luminous ? 0xffffff : 0x000000, emissiveMap: luminous ? texture : null,
      emissiveIntensity: luminous ? .25 : 0,
    });
  }
  function canvas(kind) {
    const c = document.createElement('canvas');
    c.width = 512;
    c.height = 384;
    const ctx = c.getContext('2d');
    ctx.fillStyle = kind === 'chart' ? '#091f2e' : '#d7d1b9';
    ctx.fillRect(0, 0, 512, 384);
    ctx.strokeStyle = kind === 'chart' ? '#3c7480' : '#8c988f';
    ctx.lineWidth = 2;
    if (kind === 'chart') {
      for (let row = 0; row < 11; row++) {
        ctx.beginPath();
        for (let x = 0; x <= 512; x += 8) {
          const y = row * 40 + Math.sin(x * .012 + row * .3) * 20;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
      ctx.strokeStyle = '#f59845';
      ctx.beginPath();
      ctx.moveTo(90, 310);
      ctx.lineTo(240, 220);
      ctx.lineTo(330, 90);
      ctx.stroke();
      for (const [x, y] of [[90, 310], [240, 220], [330, 90]]) {
        ctx.strokeRect(x - 8, y - 8, 16, 16);
      }
    } else {
      ctx.strokeRect(20, 20, 472, 344);
      for (let y = 95; y < 310; y += 28) {
        ctx.beginPath();
        ctx.moveTo(55, y);
        ctx.lineTo(450, y);
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(256, 60, 20, 0, Math.PI * 2);
      ctx.stroke();
    }
    return new THREE.CanvasTexture(c);
  }
  mount('screen_main', canvas('chart'), true);
  mount('screen_log', canvas('log'));
  mount('frame_licence', canvas('licence'));
  const sites = ['harbor_inspection', 'coral_reef', 'jacket_inspection',
    'aquaculture_pen', 'wreck_survey', 'monopile_current'];
  await Promise.all(sites.map(async function postcard(site, i) {
    const texture = await new THREE.TextureLoader().loadAsync(`menu/previews/${site}.jpg`);
    mount(`photo_wall_${i}`, texture);
  }));
  return function dispose() {
    textures.forEach(function release(texture) { texture.dispose(); });
  };
}
