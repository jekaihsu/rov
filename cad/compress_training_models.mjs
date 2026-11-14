/** Lossless meshopt packaging: retain floating-point positions and the complete authored graph. */
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS, EXTMeshoptCompression } from '@gltf-transform/extensions';
import { MeshoptEncoder, MeshoptDecoder } from 'meshoptimizer';

const root = fileURLToPath(new URL('../', import.meta.url));
await MeshoptEncoder.ready;
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
    'meshopt.encoder': MeshoptEncoder,
    'meshopt.decoder': MeshoptDecoder,
});
for (const model of ['falcon', 'bluerov2_heavy']) {
    const document = await io.read(`${root}.runtime/a3/${model}-materials.glb`);
    const original = await io.read(`${root}.runtime/a3/before/${model}.glb`);
    const originalNodes = new Map(original.getRoot().listNodes().map(node => [node.getName(), node]));
    for (const node of document.getRoot().listNodes()) {
        if (!node.getMesh()) continue;
        const oldPrimitives = originalNodes.get(node.getName()).getMesh().listPrimitives();
        for (const [index, primitive] of node.getMesh().listPrimitives().entries()) {
            const position = primitive.getAttribute('POSITION');
            const oldPosition = oldPrimitives[index].getAttribute('POSITION');
            if (position.getCount() !== oldPosition.getCount()) continue;
            const current = position.getArray();
            const previous = oldPosition.getArray();
            const delta = current.reduce((max, value, i) => Math.max(max, Math.abs(value - previous[i])), 0);
            // Curve tessellation differs at float-roundoff scale between the original Windows and Linux exports.
            // Restore only identically ordered vertices within 0.1 micrometre. Full triangle checks run afterward.
            if (delta > 0 && delta < 1e-7) {
                assert.deepEqual(primitive.getIndices().getArray(), oldPrimitives[index].getIndices().getArray());
                position.setArray(previous.slice());
            }
        }
    }
    for (const texture of document.getRoot().listTextures()) {
        const path = `${root}.runtime/a3/optimized/${model}/${texture.getName()}.png`;
        if (existsSync(path)) texture.setImage(readFileSync(path));
    }
    document.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({
        method: EXTMeshoptCompression.EncoderMethod.QUANTIZE,
    });
    // QUANTIZE selects the codec path; omitting the quantize() transform keeps original float values.
    // Do not weld, flatten, prune, join or simplify: animation and anchor names are runtime contracts.
    await io.write(`${root}simulator/viewer/models/${model}.glb`, document);
}
