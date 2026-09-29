// glTF loading shared by the viewer modules.
// * meshopt-compressed models (models/rov.glb) need the decoder
// * hosts that refuse to serve .glb (e.g. claude.ai artifacts) get a sibling "<name>.glb.json"
//   ({"glb": "<base64>"}, written by tools/build_showcase.py) which is decoded in memory
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
const isGlb = (buf) => buf.byteLength > 12 && new TextDecoder().decode(new Uint8Array(buf, 0, 4)) === 'glTF';

async function fetchGlb(url) {
  try {
    const r = await fetch(url);
    if (r.ok) { const buf = await r.arrayBuffer(); if (isGlb(buf)) return buf; }
  } catch (e) { /* fall through to the JSON copy */ }
  const r = await fetch(url + '.json');
  if (!r.ok) throw new Error(`cannot load ${url}`);
  const b64 = (await r.json()).glb;
  const bin = atob(b64), out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
}

/** Load the first URL that works; resolves to the parsed glTF ({scene, animations, ...}). */
export async function loadGLTF(...urls) {
  let err;
  for (const url of urls) {
    try { return await loader.parseAsync(await fetchGlb(url), ''); } catch (e) { err = e; }
  }
  throw err;
}
