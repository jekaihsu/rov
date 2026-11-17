// Decode EXT_meshopt_compression into a plain GLB on stdout.
// Used by tests that read float accessors (scan rocks). The viewer decoder is
// the same file the page loads; this script does not add a dependency.
import { readFileSync } from 'node:fs';
import { MeshoptDecoder } from '../viewer/vendor/three/examples/jsm/libs/meshopt_decoder.module.js';

await MeshoptDecoder.ready;

const data = readFileSync(process.argv[2]);
const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
if (view.getUint32(0, true) !== 0x46546c67) throw new Error('not a GLB');
const jsonLength = view.getUint32(12, true);
const document = JSON.parse(new TextDecoder().decode(data.subarray(20, 20 + jsonLength)));
const binAt = 20 + jsonLength;
const binLength = view.getUint32(binAt, true);
const binary = data.subarray(binAt + 8, binAt + 8 + binLength);

const packed = [];
let cursor = 0;
for (const bufferView of document.bufferViews || []) {
  const ext = bufferView.extensions && bufferView.extensions.EXT_meshopt_compression;
  let bytes;
  if (ext) {
    const source = binary.subarray(ext.byteOffset || 0, (ext.byteOffset || 0) + ext.byteLength);
    bytes = new Uint8Array(ext.count * ext.byteStride);
    MeshoptDecoder.decodeGltfBuffer(bytes, ext.count, ext.byteStride, source, ext.mode, ext.filter || 'NONE');
    delete bufferView.extensions.EXT_meshopt_compression;
    if (Object.keys(bufferView.extensions).length === 0) delete bufferView.extensions;
  } else {
    const off = bufferView.byteOffset || 0;
    bytes = binary.subarray(off, off + bufferView.byteLength);
  }
  const pad = (4 - (cursor % 4)) % 4;
  cursor += pad;
  bufferView.byteOffset = cursor;
  bufferView.byteLength = bytes.byteLength;
  packed.push({ pad, bytes });
  cursor += bytes.byteLength;
}
for (const listName of ['extensionsUsed', 'extensionsRequired']) {
  if (!document[listName]) continue;
  document[listName] = document[listName].filter((name) => name !== 'EXT_meshopt_compression');
  if (document[listName].length === 0) delete document[listName];
}
if (document.buffers && document.buffers[0]) document.buffers[0].byteLength = cursor;

const json = new TextEncoder().encode(JSON.stringify(document));
const jsonPad = (4 - (json.length % 4)) % 4;
const binPad = (4 - (cursor % 4)) % 4;
const total = 12 + 8 + json.length + jsonPad + 8 + cursor + binPad;
const out = new Uint8Array(total);
const header = new DataView(out.buffer);
header.setUint32(0, 0x46546c67, true);
header.setUint32(4, 2, true);
header.setUint32(8, total, true);
header.setUint32(12, json.length + jsonPad, true);
header.setUint32(16, 0x4E4F534A, true);
out.set(json, 20);
out.fill(0x20, 20 + json.length, 20 + json.length + jsonPad);
let at = 20 + json.length + jsonPad;
header.setUint32(at, cursor + binPad, true);
header.setUint32(at + 4, 0x004E4942, true);
at += 8;
for (const piece of packed) {
  at += piece.pad;
  out.set(piece.bytes, at);
  at += piece.bytes.byteLength;
}
process.stdout.write(out);
