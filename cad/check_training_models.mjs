/** Compare decoded shipped GLBs to pristine inputs: graph/extras/transforms and exact oriented triangles. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { statSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { MeshoptDecoder } from 'meshoptimizer';

const root = fileURLToPath(new URL('../', import.meta.url));
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
    'meshopt.decoder': MeshoptDecoder,
});

function graph(document) {
    return document.getRoot().listNodes().map(node => ({
        name: node.getName(),
        children: node.listChildren().map(child => child.getName()).sort(),
        extras: node.getExtras(),
        translation: node.getTranslation(),
        rotation: node.getRotation(),
        scale: node.getScale(),
    })).sort((a, b) => a.name.localeCompare(b.name));
}

function triangles(node) {
    const mesh = node.getMesh();
    if (!mesh) return null;
    const triangles = [];
    for (const primitive of mesh.listPrimitives()) {
        assert.equal(primitive.getMode(), 4, 'Expected triangle mesh');
        const positions = primitive.getAttribute('POSITION');
        const indices = primitive.getIndices();
        for (let index = 0; index < indices.getCount(); index += 3) {
            const corners = [0, 1, 2].map(offset => JSON.stringify(
                positions.getElement(indices.getScalar(index + offset), []),
            ));
            // Meshopt may rotate a triangle's starting corner, but must preserve winding.
            const rotations = [0, 1, 2].map(start => [...corners.slice(start), ...corners.slice(0, start)].join('|'));
            triangles.push(rotations.sort()[0]);
        }
    }
    return createHash('sha256').update(triangles.sort().join('\n')).digest('hex');
}

const results = [];
for (const model of ['falcon', 'bluerov2_heavy']) {
    const before = await io.read(`${root}.runtime/a3/before/${model}.glb`);
    const path = `${root}simulator/viewer/models/${model}.glb`;
    const after = await io.read(path);
    assert.deepEqual(graph(after), graph(before), `${model}: node contract changed`);
    const oldNodes = new Map(before.getRoot().listNodes().map(node => [node.getName(), node]));
    for (const node of after.getRoot().listNodes()) {
        assert.equal(triangles(node), triangles(oldNodes.get(node.getName())), `${model}: geometry ${node.getName()}`);
    }
    assert.deepEqual(
        after.getRoot().listScenes().map(scene => scene.listChildren().map(node => node.getName())),
        before.getRoot().listScenes().map(scene => scene.listChildren().map(node => node.getName())),
    );
    assert(after.getRoot().listExtensionsRequired().some(ext => ext.extensionName === 'EXT_meshopt_compression'));
    assert(statSync(path).size < 8_000_000, `${model}: exceeds 8 MB`);
    for (const texture of after.getRoot().listTextures()) {
        assert.deepEqual(texture.getSize(), [1024, 1024], `${model}: texture size`);
    }
    results.push({
        model, nodes: oldNodes.size,
        rotors: [...oldNodes.values()].filter(node => node.getExtras().role === 'rotor').length,
        originalBytes: statSync(`${root}.runtime/a3/before/${model}.glb`).size,
        finalBytes: statSync(path).size,
        textures: after.getRoot().listTextures().length,
        graphExtrasTransforms: 'exact match', orientedTrianglePositions: 'exact match',
    });
}
console.log(JSON.stringify(results, null, 2));
writeFileSync(`${root}.runtime/a3/asset-check.json`, JSON.stringify(results, null, 2) + '\n');
